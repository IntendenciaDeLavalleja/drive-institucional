from flask import request
from flask_login import current_user

from .extensions import db
from .models import AuditLog


def client_ip():
    return request.remote_addr


def audit(action, details=None, target_type=None, target_id=None, user=None):
    actor = user or (current_user if current_user.is_authenticated else None)
    db.session.add(
        AuditLog(
            user_id=getattr(actor, "id", None),
            username=getattr(actor, "username", None),
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=client_ip(),
            user_agent=(request.user_agent.string or "")[:255],
        )
    )
