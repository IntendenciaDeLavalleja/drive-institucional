from flask import current_app, render_template
from flask_mail import Message

from .extensions import mail


def send_2fa_code(recipient, code, ttl_minutes=10):
    if current_app.testing:
        current_app.extensions.setdefault("outbox", []).append({"to": recipient, "code": code})
        return
    message = Message(
        subject="Código de acceso — Drive Institucional",
        recipients=[recipient],
        body=render_template("emails/2fa.txt", code=code, ttl_minutes=ttl_minutes),
        html=render_template("emails/2fa.html", code=code, ttl_minutes=ttl_minutes),
    )
    mail.send(message)
