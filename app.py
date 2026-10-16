import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "login"

PLATFORMS = ("ps3", "ps4", "ps5")
ALLOWED_EXTENSIONS = {"zip", "pkg", "7z"}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    apps = db.relationship("App", backref="creator", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class App(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    platform = db.Column(db.String(10), nullable=False, index=True)
    version = db.Column(db.String(40), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_sha256 = db.Column(db.String(64), nullable=False)
    download_count = db.Column(db.Integer, default=0, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI="sqlite:///instance/store.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=512 * 1024 * 1024,
        UPLOAD_DIR="instance/uploads",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
    )
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'",
        )
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        print("Database initialized.")

    @app.get("/")
    def index():
        platform = request.args.get("platform")
        query = App.query.order_by(App.created_at.desc())
        if platform in PLATFORMS:
            query = query.filter_by(platform=platform)
        return render_template("index.html", apps=query.all(), platforms=PLATFORMS, selected=platform)

    @app.route("/register", methods=("GET", "POST"))
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if len(username) < 3 or len(username) > 80 or not username.replace("_", "").isalnum():
                flash("Username must be 3-80 letters, numbers, or underscores.", "error")
            elif "@" not in email or len(email) > 255:
                flash("Enter a valid email address.", "error")
            elif len(password) < 12:
                flash("Password must be at least 12 characters.", "error")
            elif User.query.filter((User.username == username) | (User.email == email)).first():
                flash("Username or email is already registered.", "error")
            else:
                user = User(username=username, email=email)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                return redirect(url_for("index"))
        return render_template("auth.html", title="Register")

    @app.route("/login", methods=("GET", "POST"))
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        if request.method == "POST":
            user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
            if user and user.check_password(request.form.get("password", "")):
                login_user(user, remember=False)
                return redirect(url_for("index"))
            flash("Invalid email or password.", "error")
        return render_template("auth.html", title="Log in")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.route("/apps/new", methods=("GET", "POST"))
    @login_required
    def create_app_route():
        if request.method == "POST":
            form_data = _read_app_form()
            error = _validate_app_form(form_data, request.files.get("package"))
            if error:
                flash(error, "error")
            else:
                package = request.files["package"]
                safe_name = secure_filename(package.filename)
                stored_name = f"{secrets.token_urlsafe(24)}-{safe_name}"
                path = Path(current_app.config["UPLOAD_DIR"]) / stored_name
                package.save(path)
                app_record = App(**form_data, filename=stored_name,
                                 file_sha256=_sha256(path), creator_id=current_user.id)
                db.session.add(app_record)
                db.session.commit()
                return redirect(url_for("index"))
        return render_template("app_form.html", app=None, platforms=PLATFORMS)

    @app.post("/apps/<int:app_id>/delete")
    @login_required
    def delete_app(app_id):
        app_record = db.get_or_404(App, app_id)
        _require_owner(app_record)
        path = Path(app.config["UPLOAD_DIR"]) / app_record.filename
        if path.is_file():
            path.unlink()
        db.session.delete(app_record)
        db.session.commit()
        return redirect(url_for("index"))

    @app.route("/apps/<int:app_id>/edit", methods=("GET", "POST"))
    @login_required
    def edit_app(app_id):
        app_record = db.get_or_404(App, app_id)
        _require_owner(app_record)
        if request.method == "POST":
            data = _read_app_form()
            if data["platform"] not in PLATFORMS or not all(data.values()):
                flash("All fields are required and the platform must be supported.", "error")
            elif App.query.filter(App.slug == data["slug"], App.id != app_id).first():
                flash("That slug is already in use.", "error")
            else:
                for key, value in data.items():
                    setattr(app_record, key, value)
                package = request.files.get("package")
                if package and package.filename:
                    extension = Path(package.filename).suffix.lower().lstrip(".")
                    if extension not in ALLOWED_EXTENSIONS:
                        flash("Only .zip, .pkg, and .7z packages are accepted.", "error")
                    else:
                        old_path = Path(current_app.config["UPLOAD_DIR"]) / app_record.filename
                        if old_path.is_file():
                            old_path.unlink()
                        safe_name = secure_filename(package.filename)
                        app_record.filename = f"{secrets.token_urlsafe(24)}-{safe_name}"
                        path = Path(current_app.config["UPLOAD_DIR"]) / app_record.filename
                        package.save(path)
                        app_record.file_sha256 = _sha256(path)
                        db.session.commit()
                        return redirect(url_for("index"))
                else:
                    db.session.commit()
                    return redirect(url_for("index"))
        return render_template("app_form.html", app=app_record, platforms=PLATFORMS)

    @app.get("/apps/<int:app_id>/download")
    def download_app(app_id):
        app_record = db.get_or_404(App, app_id)
        app_record.download_count += 1
        db.session.commit()
        extension = Path(app_record.filename).suffix.lower()
        return send_from_directory(app.config["UPLOAD_DIR"], app_record.filename,
                                   as_attachment=True, download_name=f"{app_record.slug}{extension}")

    return app


def _read_app_form():
    return {key: request.form.get(key, "").strip() for key in ("name", "slug", "description", "platform", "version")}


def _validate_app_form(data, package):
    if not all(data.values()) or len(data["description"]) > 10000:
        return "All fields are required and description must be at most 10,000 characters."
    if data["platform"] not in PLATFORMS:
        return "Unsupported platform."
    if not package or not package.filename:
        return "Choose a package to upload."
    extension = Path(package.filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        return "Only .zip, .pkg, and .7z packages are accepted."
    if App.query.filter_by(slug=data["slug"]).first():
        return "That slug is already in use."
    return None


def _require_owner(app_record):
    if app_record.creator_id != current_user.id:
        abort(403)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


app = create_app()
