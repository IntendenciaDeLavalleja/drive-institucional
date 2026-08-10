from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..audit import audit
from ..extensions import db
from ..models import Unit, User
from ..security import superadmin_required

bp = Blueprint("users", __name__, url_prefix="/admin/users")


@bp.get("/")
@login_required
@superadmin_required
def index():
    return render_template(
        "users.html",
        users=User.query.order_by(User.username).all(),
        units=Unit.query.order_by(Unit.name).all(),
    )


@bp.post("/")
@login_required
@superadmin_required
def create():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "admin")
    unit_id = request.form.get("unit_id", type=int)
    unit = db.session.get(Unit, unit_id) if unit_id else None
    if (
        len(username) < 3
        or "@" not in email
        or len(password) < 12
        or role not in {"admin", "superadmin"}
        or (role == "admin" and not unit)
    ):
        flash("Revisá los datos. Los admins deben tener una unidad y la contraseña al menos 12 caracteres.", "error")
        return redirect(url_for("users.index"))
    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash("El nombre o correo ya está en uso.", "error")
        return redirect(url_for("users.index"))
    user = User(username=username, email=email, role=role, unit_id=unit.id if role == "admin" else None, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    audit("USER_CREATE", f"{username} ({role})", "user", user.id)
    db.session.commit()
    flash("Usuario creado.", "success")
    return redirect(url_for("users.index"))


@bp.post("/<int:user_id>/update")
@login_required
@superadmin_required
def update(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    role = request.form.get("role", user.role)
    unit_id = request.form.get("unit_id", type=int)
    unit = db.session.get(Unit, unit_id) if unit_id else None
    active = request.form.get("is_active") == "on"
    if role not in {"admin", "superadmin"}:
        abort(400)
    if role == "admin" and not unit:
        flash("Los admins deben tener una unidad asignada.", "error")
        return redirect(url_for("users.index"))
    if user.id == current_user.id and (not active or role != "superadmin"):
        flash("No podés quitarte tus propios privilegios ni desactivar tu cuenta.", "error")
        return redirect(url_for("users.index"))
    if user.is_superadmin and (not active or role != "superadmin"):
        active_supers = User.query.filter_by(role="superadmin", is_active=True).count()
        if active_supers <= 1:
            flash("Debe quedar al menos un superadministrador activo.", "error")
            return redirect(url_for("users.index"))
    user.role = role
    user.unit_id = unit.id if role == "admin" else None
    user.is_active = active
    new_password = request.form.get("password", "")
    if new_password:
        if len(new_password) < 12:
            flash("La nueva contraseña debe tener al menos 12 caracteres.", "error")
            return redirect(url_for("users.index"))
        user.set_password(new_password)
    audit("USER_UPDATE", f"{user.username}: {role}, activo={active}", "user", user.id)
    db.session.commit()
    flash("Usuario actualizado.", "success")
    return redirect(url_for("users.index"))
