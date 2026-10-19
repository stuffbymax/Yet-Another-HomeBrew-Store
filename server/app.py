"""Yet Another HomeBrew Store - server.  Run: flask --app app run  (dev) / gunicorn 'app:create_app()'"""
import logging
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import urljoin, urlparse

import click
from flask import (Flask, Response, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from flask_migrate import Migrate
from flask_login import current_user, login_required, login_user, logout_user
from flask_talisman import Talisman
from sqlalchemy import or_, update
from werkzeug.middleware.proxy_fix import ProxyFix

from config import INSTANCE_DIR, Config
from extensions import csrf, db, limiter, login_manager
from account import (admin_gate, audit, register_account_routes, require_verified, send_verification)
from forms import AppForm, ConfirmForm, LoginForm, RegisterForm, ReportForm
from models import HomebrewApp, Report, User, utcnow
import signing
from scan import scan_file
from security import UploadError, delete_stored, save_icon, save_package

log = logging.getLogger("yahbs")
PLATFORM_LABEL = {"ps3": "PS3", "ps4": "PS4", "ps5": "PS5"}


def create_app(overrides=None):
    app = Flask(__name__, instance_path=str(INSTANCE_DIR))
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    if not app.config["SECRET_KEY"]:
        if app.config["ENV_NAME"] == "development":
            app.config["SECRET_KEY"] = secrets.token_hex(32)  # ephemeral
        else:
            raise RuntimeError("SECRET_KEY is not set. Refusing to start.")

    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    if app.config["PROXY_HOPS"]:
        n = app.config["PROXY_HOPS"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    app.config["RATELIMIT_ENABLED"] = app.config.get("RATELIMIT_ENABLED", True)
    db.init_app(app)
    Migrate(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.session_protection = "strong"
    login_manager.login_message = "Log in to continue."

    Talisman(
        app,
        force_https=app.config["FORCE_HTTPS"],
        strict_transport_security=app.config["FORCE_HTTPS"],
        strict_transport_security_max_age=31536000,
        session_cookie_secure=app.config["FORCE_HTTPS"],
        frame_options="DENY",
        referrer_policy="same-origin",
        content_security_policy={
            "default-src": "'none'",
            "script-src": "'self'",
            "style-src": "'self'",
            "img-src": "'self'",
            "form-action": "'self'",
            "base-uri": "'none'",
            "frame-ancestors": "'none'",
        },
    )

    @app.after_request
    def extra_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if request.endpoint in ("login", "register", "dashboard", "edit_app", "new_app", "admin"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @login_manager.user_loader
    def load_user(uid):
        user = db.session.get(User, int(uid)) if str(uid).isdigit() else None
        return user if user and user.active else None

    @app.template_filter("filesize")
    def filesize(n):
        n = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024

    app.jinja_env.globals.update(PLATFORM_LABEL=PLATFORM_LABEL)
    register_routes(app)
    register_account_routes(app)
    register_cli(app)
    if app.config["ENV_NAME"] == "development" or app.config.get("TESTING"):
        with app.app_context():
            db.create_all()      # production uses migrations: flask --app app db upgrade
    return app


def is_safe_next(target):
    if not target:
        return False
    ref, test = urlparse(request.host_url), urlparse(urljoin(request.host_url, target))
    return test.scheme == ref.scheme and test.netloc == ref.netloc and target.startswith("/")


def get_app_or_404(app_id):
    return db.get_or_404(HomebrewApp, app_id)


def visible_or_404(item):
    if item.is_public() or (current_user.is_authenticated and item.can_edit(current_user)):
        return item
    abort(404)  # do not reveal existence of unapproved apps


def public_query(platform=None):
    q = HomebrewApp.query.filter_by(status="approved")
    if platform in PLATFORM_LABEL:
        q = q.filter_by(platform=platform)
    return q


def app_to_dict(a):
    return {"id": a.id, "name": a.name, "platform": a.platform, "version": a.version,
            "title_id": a.title_id, "summary": a.short_desc, "creator": a.owner.username,
            "size": a.package_size, "sha256": a.package_sha256, "downloads": a.downloads,
            "updated": a.updated_at.isoformat() + "Z",
            "download_url": url_for("download", app_id=a.id, _external=True)}


def register_routes(app):
    cfg = app.config

    # ---------- public pages ----------
    @app.get("/")
    def index():
        platform = request.args.get("platform", "")
        q = (request.args.get("q") or "").strip()[:64]
        page = max(1, request.args.get("page", 1, type=int) or 1)
        query = public_query(platform)
        if q:
            query = query.filter(or_(HomebrewApp.name.contains(q, autoescape=True),
                                     HomebrewApp.short_desc.contains(q, autoescape=True)))
        pager = query.order_by(HomebrewApp.updated_at.desc()).paginate(
            page=page, per_page=cfg["APPS_PER_PAGE"], error_out=False)
        return render_template("index.html", pager=pager, platform=platform, q=q)

    @app.get("/app/<int:app_id>")
    def detail(app_id):
        item = visible_or_404(get_app_or_404(app_id))
        return render_template("detail.html", item=item, form=ConfirmForm(), report_form=ReportForm())

    @app.get("/app/<int:app_id>/icon")
    def icon(app_id):
        item = visible_or_404(get_app_or_404(app_id))
        if not item.icon_file:
            abort(404)
        return send_from_directory(cfg["UPLOAD_DIR"], item.icon_file, mimetype="image/png",
                                   max_age=3600)

    @app.get("/app/<int:app_id>/download")
    @limiter.limit("60 per hour")
    def download(app_id):
        item = visible_or_404(get_app_or_404(app_id))
        db.session.execute(update(HomebrewApp).where(HomebrewApp.id == item.id)
                           .values(downloads=HomebrewApp.downloads + 1))
        db.session.commit()
        ext = item.package_file.rsplit(".", 1)[-1]
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", item.name).strip("._") or "app"
        resp = send_from_directory(cfg["UPLOAD_DIR"], item.package_file, as_attachment=True,
                                   download_name=f"{safe}-{item.version}.{ext}",
                                   mimetype="application/octet-stream")
        resp.headers["X-Package-SHA256"] = item.package_sha256
        return resp

    @app.get("/rules")
    def rules():
        return render_template("rules.html")

    # ---------- console API (read-only, public) ----------
    @app.get("/api/v1/apps")
    @limiter.limit("120 per hour")
    def api_apps():
        apps = public_query(request.args.get("platform")).order_by(HomebrewApp.name).limit(500).all()
        return jsonify([app_to_dict(a) for a in apps])

    @app.get("/api/v1/apps/<int:app_id>")
    @limiter.limit("240 per hour")
    def api_app(app_id):
        item = get_app_or_404(app_id)
        if not item.is_public():
            abort(404)
        return jsonify(app_to_dict(item))

    @app.get("/api/v1/catalog.tsv")
    @limiter.limit("120 per hour")
    def api_catalog_tsv():
        """Tab-separated: id name version platform size sha256 - trivial to parse in C."""
        apps = public_query(request.args.get("platform")).order_by(HomebrewApp.name).limit(500).all()
        lines = [f"{a.id}\t{a.name}\t{a.version}\t{a.platform}\t{a.package_size}\t{a.package_sha256}\t{a.package_file.rsplit('.', 1)[-1]}"
                 for a in apps]  # names cannot contain control chars (form validator)
        plat = request.args.get("platform", "")
        if plat not in PLATFORM_LABEL:
            abort(400)
        if not cfg["SIGNING_KEY_HEX"]:
            abort(503)  # never serve an unsigned catalog
        return Response(signing.sign_catalog(cfg["SIGNING_KEY_HEX"], plat, lines), mimetype="text/plain")

    # ---------- auth ----------
    @app.route("/register", methods=["GET", "POST"])
    @limiter.limit("5 per hour", methods=["POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = RegisterForm()
        if form.validate_on_submit():
            username, email = form.username.data, form.email.data.lower()
            if User.query.filter(or_(User.username.ilike(username), User.email == email)).first():
                form.username.errors.append("That username or email is already taken.")
            else:
                user = User(username=username, email=email)
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.commit()
                send_verification(user)
                flash("Account created. Check your email for a verification link, then log in.", "ok")
                return redirect(url_for("login"))
        return render_template("auth.html", form=form, title="Create account")

    @app.route("/login", methods=["GET", "POST"])
    @limiter.limit("10 per minute", methods=["POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter(User.username.ilike(form.username.data)).first()
            generic = "Wrong username or password, or the account is temporarily locked."
            if not user:
                User.dummy_check(form.password.data)
                flash(generic, "error")
            elif user.is_locked() or not user.active:
                User.dummy_check(form.password.data)
                flash(generic, "error")
            elif user.check_password(form.password.data):
                nxt = request.args.get("next")
                nxt = nxt if is_safe_next(nxt) else None
                if user.totp_enabled:
                    session.clear()
                    session["pre2fa"] = {"id": user.id, "t": time.time(), "next": nxt}
                    return redirect(url_for("login_2fa"))
                user.failed_logins, user.locked_until = 0, None
                db.session.commit()
                session.clear()  # fresh session on privilege change (fixation defence)
                login_user(user)
                log.info("login ok user=%s ip=%s", user.username, request.remote_addr)
                return redirect(nxt or url_for("dashboard"))
            else:
                user.failed_logins += 1
                if user.failed_logins >= cfg["MAX_FAILED_LOGINS"]:
                    user.locked_until = utcnow() + timedelta(minutes=cfg["LOCKOUT_MINUTES"])
                    user.failed_logins = 0
                    audit("account_locked", user.username, actor=user.username)
                db.session.commit()
                log.warning("login failed user=%s ip=%s", user.username, request.remote_addr)
                flash(generic, "error")
        return render_template("auth.html", form=form, title="Log in")

    @app.post("/logout")
    def logout():
        if ConfirmForm().validate_on_submit():
            logout_user()
        return redirect(url_for("index"))

    # ---------- creator dashboard ----------
    @app.get("/dashboard")
    @login_required
    def dashboard():
        apps = current_user.apps.order_by(HomebrewApp.updated_at.desc()).all()
        return render_template("dashboard.html", apps=apps, form=ConfirmForm())

    def _apply(form, item, creating):
        """Validate uploads and write to item. Returns True on success."""
        upload_dir = cfg["UPLOAD_DIR"]
        pkg, ico = form.package.data, form.icon.data
        has_pkg, has_ico = bool(pkg and pkg.filename), bool(ico and ico.filename)
        if creating and not has_pkg:
            form.package.errors = ["A package file is required."]
            return False
        if creating and not form.accept.data:
            form.accept.errors = ["You must confirm this."]
            return False
        new_pkg = new_ico = None
        stage = form.package
        try:
            if has_pkg:
                new_pkg = save_package(pkg, form.platform.data, upload_dir)
                scan_file(upload_dir / new_pkg[0], cfg["CLAMD_ADDR"])
            if has_ico:
                stage = form.icon
                new_ico = save_icon(ico, upload_dir)
        except UploadError as e:
            if new_pkg:
                delete_stored(upload_dir, new_pkg[0])
            stage.errors = [str(e)]
            return False
        if not creating and not has_pkg and form.platform.data != item.platform:
            form.platform.errors = ["Upload a new package to change platform."]
            if new_ico:
                delete_stored(upload_dir, new_ico)
            return False

        item.name, item.platform, item.version = form.name.data.strip(), form.platform.data, form.version.data
        item.title_id, item.short_desc = form.title_id.data or "", (form.short_desc.data or "").strip()
        item.description = (form.description.data or "").replace("\r\n", "\n")
        if new_pkg:
            if not creating:
                delete_stored(upload_dir, item.package_file)
            item.package_file, item.package_sha256, item.package_size = new_pkg
            if not current_user.is_admin:
                item.status = "pending"  # re-review any new binary
        if new_ico:
            delete_stored(upload_dir, item.icon_file)
            item.icon_file = new_ico
        return True

    @app.route("/dashboard/new", methods=["GET", "POST"])
    @login_required
    @limiter.limit("10 per hour", methods=["POST"])
    def new_app():
        if (r := require_verified()): return r
        form = AppForm()
        if form.validate_on_submit():
            item = HomebrewApp(owner_id=current_user.id, package_file="", package_sha256="",
                               package_size=0,
                               status="approved" if current_user.is_admin else "pending")
            if _apply(form, item, creating=True):
                db.session.add(item)
                db.session.commit()
                audit("app_uploaded", f"app={item.id} sha256={item.package_sha256[:16]}")
                flash("Uploaded. It will appear in the store once a moderator approves it.", "ok")
                return redirect(url_for("dashboard"))
        return render_template("app_form.html", form=form, item=None)

    @app.route("/dashboard/<int:app_id>/edit", methods=["GET", "POST"])
    @login_required
    @limiter.limit("30 per hour", methods=["POST"])
    def edit_app(app_id):
        item = get_app_or_404(app_id)
        if not item.can_edit(current_user):
            abort(404)
        if (r := require_verified()): return r
        form = AppForm(obj=item) if request.method == "GET" else AppForm()
        if form.validate_on_submit():
            if _apply(form, item, creating=False):
                db.session.commit()
                flash("Saved." + (" New package is awaiting review." if item.status == "pending" else ""), "ok")
                return redirect(url_for("dashboard"))
            db.session.rollback()
        return render_template("app_form.html", form=form, item=item)

    @app.post("/dashboard/<int:app_id>/delete")
    @login_required
    def delete_app(app_id):
        item = get_app_or_404(app_id)
        if not item.can_edit(current_user) or not ConfirmForm().validate_on_submit():
            abort(404)
        delete_stored(cfg["UPLOAD_DIR"], item.package_file)
        delete_stored(cfg["UPLOAD_DIR"], item.icon_file)
        if item.owner_id != current_user.id:
            audit("app_deleted_by_admin", f"app={item.id} {item.name}")
        db.session.delete(item)
        db.session.commit()
        flash("Deleted.", "ok")
        return redirect(url_for("dashboard"))

    # ---------- moderation ----------
    @app.get("/admin")
    @login_required
    def admin():
        if (g := admin_gate()): return g
        pending = HomebrewApp.query.filter_by(status="pending").order_by(HomebrewApp.created_at).all()
        return render_template("admin.html", pending=pending, form=ConfirmForm())

    @app.post("/admin/<int:app_id>/<action>")
    @login_required
    def moderate(app_id, action):
        if (g := admin_gate()): return g
        if action not in ("approve", "reject") or not ConfirmForm().validate_on_submit():
            abort(404)
        item = get_app_or_404(app_id)
        item.status = "approved" if action == "approve" else "rejected"
        db.session.commit()
        audit(f"app_{action}", f"app={item.id} {item.name}")
        flash(f"{item.name}: {item.status}.", "ok")
        return redirect(url_for("admin"))

    # ---------- errors ----------
    for code, msg in {400: "Bad request.", 403: "Not allowed.", 404: "Not found.",
                      413: "That file is too large.", 429: "Too many requests. Slow down."}.items():
        app.register_error_handler(code, lambda e, code=code, msg=msg:
                                   (render_template("error.html", code=code, msg=msg), code))

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html", code=500, msg="Something went wrong on our side."), 500


def register_cli(app):
    app.cli.add_command(gen_signing_key)

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("email")
    def create_admin(username, email):
        """Create a moderator account:  flask --app app create-admin NAME EMAIL"""
        pw = click.prompt("Password (12+ chars)", hide_input=True, confirmation_prompt=True)
        if len(pw) < 12:
            raise click.ClickException("Password too short.")
        u = User(username=username, email=email.lower(), role="admin", email_verified=True)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        click.echo("Admin created.")


@click.command("gen-signing-key")
def gen_signing_key():
    """Generate the catalog signing key. Keep the seed secret; embed the public key in clients."""
    import signing
    seed, pub = signing.generate()
    click.echo(f"SIGNING_KEY_HEX={seed}\n# put the line above in your environment (secret!)")
    click.echo("// client/common/pubkey.h")
    click.echo("#define YAHBS_PUBKEY { " + ", ".join(f"0x{b:02x}" for b in pub) + " }")


if __name__ == "__main__":
    create_app().run()
