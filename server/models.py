from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Valid hash used to equalise timing when a username does not exist.
_DUMMY_HASH = generate_password_hash("not-a-real-password", method="scrypt")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="creator")  # creator | admin
    active = db.Column(db.Boolean, nullable=False, default=True)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    totp_secret = db.Column(db.String(200), nullable=True)      # Fernet-encrypted
    totp_enabled = db.Column(db.Boolean, nullable=False, default=False)
    totp_last_step = db.Column(db.Integer, nullable=False, default=0)
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    apps = db.relationship("HomebrewApp", back_populates="owner", lazy="dynamic")

    @property
    def is_active(self):  # Flask-Login
        return self.active

    @property
    def is_admin(self):
        return self.role == "admin"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def dummy_check(password):
        check_password_hash(_DUMMY_HASH, password)

    def is_locked(self):
        return bool(self.locked_until and self.locked_until > utcnow())


class HomebrewApp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    platform = db.Column(db.String(3), nullable=False, index=True)  # ps3 | ps4 | ps5
    version = db.Column(db.String(20), nullable=False)
    title_id = db.Column(db.String(24), nullable=False, default="")
    short_desc = db.Column(db.String(140), nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    icon_file = db.Column(db.String(64), nullable=True)
    package_file = db.Column(db.String(64), nullable=False)
    package_sha256 = db.Column(db.String(64), nullable=False)
    package_size = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    downloads = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    owner = db.relationship("User", back_populates="apps")

    def can_edit(self, user):
        return user.is_authenticated and (user.id == self.owner_id or user.is_admin)

    def is_public(self):
        return self.status == "approved"


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.Integer, db.ForeignKey("homebrew_app.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    resolved = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    app = db.relationship("HomebrewApp")
    reporter = db.relationship("User")


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    actor = db.Column(db.String(32), nullable=False)
    action = db.Column(db.String(48), nullable=False)
    target = db.Column(db.String(120), nullable=False, default="")
