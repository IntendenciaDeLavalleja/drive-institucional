import hashlib
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask_login import UserMixin

from .extensions import db

ph = PasswordHasher()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="admin")
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id", ondelete="SET NULL"), index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)

    @property
    def is_superadmin(self):
        return self.role == "superadmin"

    def set_password(self, password):
        self.password_hash = ph.hash(password)

    def check_password(self, password):
        try:
            return ph.verify(self.password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False


class Unit(TimestampMixin, db.Model):
    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    quota_bytes = db.Column(db.BigInteger, nullable=False)

    users = db.relationship("User", backref="unit", lazy="dynamic")
    folders = db.relationship("Folder", backref="unit", lazy="dynamic")
    files = db.relationship("DriveFile", backref="unit", lazy="dynamic")


class StorageSettings(TimestampMixin, db.Model):
    __tablename__ = "storage_settings"

    id = db.Column(db.Integer, primary_key=True)
    total_quota_bytes = db.Column(db.BigInteger, nullable=False)


class TwoFactorCode(db.Model):
    __tablename__ = "two_factor_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    consumed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref=db.backref("two_factor_codes", cascade="all, delete-orphan"))

    @classmethod
    def issue(cls, user_id, code, ttl_minutes=10):
        return cls(
            user_id=user_id,
            code_hash=ph.hash(code),
            expires_at=utcnow() + timedelta(minutes=ttl_minutes),
        )

    def verify(self, code, max_attempts=5):
        if self.consumed_at or self.expires_at < utcnow() or self.attempts >= max_attempts:
            return False
        self.attempts += 1
        try:
            valid = ph.verify(self.code_hash, code)
        except (VerifyMismatchError, InvalidHashError):
            valid = False
        if valid:
            self.consumed_at = utcnow()
        return valid


class Folder(TimestampMixin, db.Model):
    __tablename__ = "folders"
    __table_args__ = (db.UniqueConstraint("parent_id", "name", "deleted_at", name="uq_folder_sibling_name"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("folders.id", ondelete="CASCADE"), index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id", ondelete="CASCADE"), index=True, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    parent = db.relationship("Folder", remote_side=[id], backref=db.backref("children", lazy="dynamic"))
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    @property
    def path_parts(self):
        parts, node = [], self
        while node:
            parts.append(node.name)
            node = node.parent
        return list(reversed(parts))


class DriveFile(TimestampMixin, db.Model):
    __tablename__ = "drive_files"

    id = db.Column(db.Integer, primary_key=True)
    folder_id = db.Column(db.Integer, db.ForeignKey("folders.id", ondelete="SET NULL"), index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id", ondelete="CASCADE"), index=True, nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    object_key = db.Column(db.String(512), unique=True, nullable=False)
    content_type = db.Column(db.String(255), nullable=False, default="application/octet-stream")
    size_bytes = db.Column(db.BigInteger, nullable=False)
    etag = db.Column(db.String(128))
    sha256 = db.Column(db.String(64))
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    folder = db.relationship("Folder", backref=db.backref("files", lazy="dynamic"))
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])
    deleted_by = db.relationship("User", foreign_keys=[deleted_by_id])


class ShareLink(TimestampMixin, db.Model):
    __tablename__ = "share_links"

    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    file_id = db.Column(db.Integer, db.ForeignKey("drive_files.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    password_hash = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime)
    max_downloads = db.Column(db.Integer)
    download_count = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_accessed_at = db.Column(db.DateTime)
    label = db.Column(db.String(255))

    file = db.relationship("DriveFile", backref=db.backref("share_links", cascade="all, delete-orphan"))
    created_by = db.relationship("User")

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def set_password(self, password):
        self.password_hash = ph.hash(password) if password else None

    def check_password(self, password):
        if not self.password_hash:
            return True
        try:
            return ph.verify(self.password_hash, password or "")
        except (VerifyMismatchError, InvalidHashError):
            return False

    @property
    def usable(self):
        return (
            self.is_active
            and not self.file.deleted_at
            and (not self.expires_at or self.expires_at > utcnow())
            and (self.max_downloads is None or self.download_count < self.max_downloads)
        )


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    username = db.Column(db.String(64))
    action = db.Column(db.String(64), nullable=False, index=True)
    target_type = db.Column(db.String(32))
    target_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    user = db.relationship("User")


class ShareAccessLog(db.Model):
    __tablename__ = "share_access_logs"

    id = db.Column(db.Integer, primary_key=True)
    share_link_id = db.Column(db.Integer, db.ForeignKey("share_links.id", ondelete="CASCADE"), nullable=False, index=True)
    event = db.Column(db.String(32), nullable=False)
    outcome = db.Column(db.String(32), nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    share_link = db.relationship("ShareLink", backref=db.backref("access_logs", cascade="all, delete-orphan"))
