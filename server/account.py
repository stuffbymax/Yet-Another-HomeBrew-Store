"""Email verification, password reset, 2FA, abuse reports, audit log."""
import hashlib
import logging
import time

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user
from itsdangerous import BadSignature, URLSafeTimedSerializer

import totp
from extensions import db, limiter
from forms import (ConfirmForm, ForgotForm, PasswordForm, ReportForm, ResetForm, TotpForm)
from mailer import send_mail
from models import AuditLog, HomebrewApp, Report, User, utcnow

log = logging.getLogger("yahbs")


def audit(action, target="", actor=None):
    who = actor or (current_user.username if current_user.is_authenticated else "anonymous")
    db.session.add(AuditLog(actor=who, action=action, target=str(target)[:120]))
    db.session.commit()
    log.info("audit actor=%s action=%s target=%s", who, action, target)


def _ser():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def make_token(payload, salt):
    return _ser().dumps(payload, salt=salt)


def read_token(token, salt, max_age):
    try:
        return _ser().loads(token, salt=salt, max_age=max_age)
    except BadSignature:  # includes SignatureExpired
        return None


def _fingerprint(user):  # changes whenever the password changes => reset links are single-use
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def _link(endpoint, **kw):
    path = url_for(endpoint, **kw)
    base = current_app.config["PUBLIC_BASE_URL"].rstrip("/")
    return (base + path) if base else url_for(endpoint, _external=True, **kw)


def send_verification(user):
    link = _link("verify_email", token=make_token(user.id, "verify"))
    send_mail(current_app.config, user.email, "Verify your YAHBS email",
              f"Hi {user.username},\n\nConfirm your email to start uploading:\n{link}\n\n"
              "The link is valid for 48 hours. If this wasn't you, ignore this email.")


def require_verified():
    if not current_user.email_verified:
        flash("Verify your email address before uploading. Check your inbox (or resend below).", "error")
        return redirect(url_for("dashboard"))


def admin_gate():
    """None if allowed. Admins must have 2FA on. Non-admins see 404."""
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(404)
    if not current_user.totp_enabled:
        flash("Admins must enable two-factor authentication first.", "error")
        return redirect(url_for("totp_setup"))


def register_account_routes(app):
    cfg = app.config

    @app.get("/verify/<token>")
    def verify_email(token):
        uid = read_token(token, "verify", 48 * 3600)
        user = db.session.get(User, uid) if isinstance(uid, int) else None
        if user:
            user.email_verified = True
            db.session.commit()
            flash("Email verified. You can upload now.", "ok")
        else:
            flash("That link is invalid or has expired.", "error")
        return redirect(url_for("dashboard" if current_user.is_authenticated else "login"))

    @app.post("/resend-verification")
    @login_required
    @limiter.limit("3 per hour")
    def resend_verification():
        if ConfirmForm().validate_on_submit() and not current_user.email_verified:
            send_verification(current_user)
        flash("If your address is unverified, a new link is on its way.", "ok")
        return redirect(url_for("dashboard"))

    @app.route("/forgot", methods=["GET", "POST"])
    @limiter.limit("5 per hour", methods=["POST"])
    def forgot():
        form = ForgotForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.lower()).first()
            if user and user.active:
                tok = make_token({"id": user.id, "f": _fingerprint(user)}, "reset")
                send_mail(cfg, user.email, "Reset your YAHBS password",
                          f"Reset link (valid 1 hour, single use):\n{_link('reset_password', token=tok)}\n\n"
                          "If you didn't ask for this, ignore it.")
            flash("If that email has an account, a reset link has been sent.", "ok")  # same answer either way
            return redirect(url_for("login"))
        return render_template("form_page.html", form=form, title="Forgot password", submit="Send reset link")

    @app.route("/reset/<token>", methods=["GET", "POST"])
    @limiter.limit("10 per hour", methods=["POST"])
    def reset_password(token):
        data = read_token(token, "reset", 3600)
        user = db.session.get(User, data["id"]) if isinstance(data, dict) and "id" in data else None
        if not user or data.get("f") != _fingerprint(user):
            flash("That reset link is invalid, expired or already used.", "error")
            return redirect(url_for("forgot"))
        form = ResetForm()
        if form.validate_on_submit():
            user.set_password(form.password.data)
            user.failed_logins, user.locked_until = 0, None
            db.session.commit()
            audit("password_reset", user.username, actor=user.username)
            flash("Password changed. Log in with the new password.", "ok")
            return redirect(url_for("login"))
        return render_template("form_page.html", form=form, title="Choose a new password", submit="Change password")

    # ---- 2FA ----
    @app.route("/login/2fa", methods=["GET", "POST"])
    @limiter.limit("10 per minute", methods=["POST"])
    def login_2fa():
        pend = session.get("pre2fa")
        if not pend or time.time() - pend["t"] > 300:
            session.pop("pre2fa", None)
            return redirect(url_for("login"))
        user = db.session.get(User, pend["id"])
        form = TotpForm()
        if user and form.validate_on_submit():
            secret = totp.decrypt(cfg["SECRET_KEY"], user.totp_secret or "")
            step = totp.verify(secret, form.code.data, user.totp_last_step) if secret and not user.is_locked() else None
            if step:
                user.totp_last_step = step
                user.failed_logins, user.locked_until = 0, None
                db.session.commit()
                session.pop("pre2fa", None)
                login_user(user)
                return redirect(pend.get("next") or url_for("dashboard"))
            user.failed_logins += 1
            if user.failed_logins >= cfg["MAX_FAILED_LOGINS"]:
                from datetime import timedelta
                user.locked_until = utcnow() + timedelta(minutes=cfg["LOCKOUT_MINUTES"])
                user.failed_logins = 0
                session.pop("pre2fa", None)
            db.session.commit()
            flash("Wrong code.", "error")
            if "pre2fa" not in session:
                return redirect(url_for("login"))
        return render_template("form_page.html", form=form, title="Two-factor code", submit="Verify",
                               note="Open your authenticator app and enter the current code.")

    @app.route("/account/2fa", methods=["GET", "POST"])
    @login_required
    @limiter.limit("20 per hour", methods=["POST"])
    def totp_setup():
        user = current_user
        if user.totp_enabled:
            return render_template("totp.html", enabled=True, form=PasswordForm(), uri=None, secret=None)
        if not user.totp_secret:
            user.totp_secret = totp.encrypt(cfg["SECRET_KEY"], totp.new_secret())
            db.session.commit()
        secret = totp.decrypt(cfg["SECRET_KEY"], user.totp_secret)
        form = TotpForm()
        if form.validate_on_submit():
            step = totp.verify(secret, form.code.data, 0)
            if step:
                user.totp_enabled, user.totp_last_step = True, step
                db.session.commit()
                audit("2fa_enabled", user.username)
                flash("Two-factor authentication is on.", "ok")
                return redirect(url_for("dashboard"))
            flash("That code didn't match. Check your phone's clock and try again.", "error")
        return render_template("totp.html", enabled=False, form=form, secret=secret,
                               uri=totp.uri(secret, user.username))

    @app.post("/account/2fa/disable")
    @login_required
    @limiter.limit("5 per hour")
    def totp_disable():
        form = PasswordForm()
        if current_user.is_admin:
            flash("Admins cannot disable two-factor authentication.", "error")
        elif form.validate_on_submit() and current_user.check_password(form.password.data):
            current_user.totp_enabled, current_user.totp_secret = False, None
            db.session.commit()
            audit("2fa_disabled", current_user.username)
            flash("Two-factor authentication is off.", "ok")
        else:
            flash("Wrong password.", "error")
        return redirect(url_for("totp_setup"))

    # ---- reports & audit ----
    @app.post("/app/<int:app_id>/report")
    @login_required
    @limiter.limit("5 per hour")
    def report_app(app_id):
        item = db.get_or_404(HomebrewApp, app_id)
        form = ReportForm()
        if not item.is_public():
            abort(404)
        if form.validate_on_submit():
            db.session.add(Report(app_id=item.id, reporter_id=current_user.id, reason=form.reason.data.strip()))
            db.session.commit()
            flash("Thanks. A moderator will look at it.", "ok")
        else:
            flash("Please describe the problem (10-500 characters).", "error")
        return redirect(url_for("detail", app_id=item.id))

    @app.get("/admin/reports")
    @login_required
    def admin_reports():
        gate = admin_gate()
        if gate: return gate
        reports = Report.query.filter_by(resolved=False).order_by(Report.created_at).all()
        return render_template("admin_reports.html", reports=reports, form=ConfirmForm())

    @app.post("/admin/reports/<int:rid>/<action>")
    @login_required
    def admin_report_action(rid, action):
        gate = admin_gate()
        if gate: return gate
        if action not in ("dismiss", "takedown") or not ConfirmForm().validate_on_submit():
            abort(404)
        rep = db.get_or_404(Report, rid)
        if action == "takedown":
            rep.app.status = "rejected"
        rep.resolved = True
        db.session.commit()
        audit(f"report_{action}", f"report={rid} app={rep.app_id}")
        flash("Done.", "ok")
        return redirect(url_for("admin_reports"))

    @app.get("/admin/audit")
    @login_required
    def admin_audit():
        gate = admin_gate()
        if gate: return gate
        rows = AuditLog.query.order_by(AuditLog.id.desc()).limit(200).all()
        return render_template("audit.html", rows=rows)
