import random
import secrets

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..audit import audit
from ..extensions import db, limiter
from ..mailer import send_2fa_code
from ..models import TwoFactorCode, User, utcnow

bp = Blueprint("auth", __name__)


def _new_captcha():
    first = random.randint(1, 10)
    second = random.randint(1, 10)
    session["captcha_result"] = first + second
    return f"¿Cuánto es {first} + {second}?"


def _safe_next(value):
    return value if value and value.startswith("/") and not value.startswith("//") else None


@bp.route("/admin/login", methods=["GET", "POST"], endpoint="login")
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("drive.index"))
    next_url = _safe_next(request.form.get("next") or request.args.get("next"))
    captcha_question = session.get("captcha_question")
    if current_app.config.get("CAPTCHA_ENABLED") and not captcha_question:
        captcha_question = _new_captcha()
        session["captcha_question"] = captcha_question

    if request.method == "POST":
        if current_app.config.get("CAPTCHA_ENABLED"):
            expected = session.pop("captcha_result", None)
            session.pop("captcha_question", None)
            if expected is None or request.form.get("captcha", "").strip() != str(expected):
                flash("Captcha incorrecto. Intentá de nuevo.", "error")
                captcha_question = _new_captcha()
                session["captcha_question"] = captcha_question
                return render_template("login.html", captcha_question=captcha_question)
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.is_active and user.check_password(password):
            TwoFactorCode.query.filter_by(user_id=user.id, consumed_at=None).update(
                {"consumed_at": utcnow()}, synchronize_session=False
            )
            code = f"{secrets.randbelow(1_000_000):06d}"
            challenge = TwoFactorCode.issue(
                user.id, code, ttl_minutes=current_app.config["TWO_FACTOR_TTL_MINUTES"]
            )
            db.session.add(challenge)
            db.session.commit()
            try:
                send_2fa_code(
                    user.email,
                    code,
                    ttl_minutes=current_app.config["TWO_FACTOR_TTL_MINUTES"],
                )
            except Exception:
                current_app.logger.exception("No se pudo enviar el código 2FA")
                challenge.consumed_at = utcnow()
                db.session.commit()
                flash("No fue posible enviar el código. Contactá al administrador.", "error")
                captcha_question = _new_captcha() if current_app.config.get("CAPTCHA_ENABLED") else None
                if captcha_question:
                    session["captcha_question"] = captcha_question
                return render_template("login.html", captcha_question=captcha_question)
            session.clear()
            session["pending_2fa_user_id"] = user.id
            session["pending_2fa_code_id"] = challenge.id
            session["pending_next"] = next_url
            flash("Enviamos un código de seis dígitos a tu correo.", "info")
            return redirect(url_for("auth.verify_2fa"))
        audit("LOGIN_FAILED", details=f"Intento fallido para {email or '(vacío)'}")
        db.session.commit()
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("login.html", captcha_question=captcha_question)


@bp.route("/admin/2fa", methods=["GET", "POST"], endpoint="verify_2fa")
@limiter.limit("10 per minute")
def verify_2fa():
    user_id = session.get("pending_2fa_user_id")
    code_id = session.get("pending_2fa_code_id")
    if not user_id or not code_id:
        return redirect(url_for("auth.login"))
    user = db.session.get(User, user_id)
    challenge = db.session.get(TwoFactorCode, code_id)
    if not user or not challenge or challenge.user_id != user.id:
        session.clear()
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        valid = challenge.verify(
            request.form.get("code", "").strip(),
            max_attempts=current_app.config["TWO_FACTOR_MAX_ATTEMPTS"],
        )
        if valid:
            user.last_login_at = utcnow()
            login_user(user)
            session.pop("pending_2fa_user_id", None)
            session.pop("pending_2fa_code_id", None)
            next_url = session.pop("pending_next", None)
            session.permanent = True
            audit("LOGIN", "Inicio de sesión con 2FA", user=user)
            db.session.commit()
            return redirect(_safe_next(next_url) or url_for("drive.index"))
        db.session.commit()
        flash("Código incorrecto, vencido o sin intentos disponibles.", "error")
    return render_template("verify_2fa.html", email=user.email)


@bp.get("/admin/")
@bp.get("/admin/dashboard")
@login_required
def admin_dashboard():
    return redirect(url_for("drive.index"))


@bp.post("/admin/logout")
def logout():
    if current_user.is_authenticated:
        audit("LOGOUT", "Cierre de sesión manual")
        db.session.commit()
        logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
