from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..audit import audit
from ..extensions import db
from ..models import DriveFile, Folder, StorageSettings, Unit
from ..security import superadmin_required

bp = Blueprint("units", __name__, url_prefix="/admin/units")
DEFAULT_TOTAL_QUOTA_BYTES = 1024**4


def _quota_bytes(value):
    try:
        megabytes = int(value)
    except (TypeError, ValueError):
        return None
    return megabytes * 1024 * 1024 if megabytes > 0 else None


def _used_bytes(unit_id):
    from sqlalchemy import func

    return (
        db.session.query(func.coalesce(func.sum(DriveFile.size_bytes), 0))
        .filter_by(unit_id=unit_id, deleted_at=None)
        .scalar()
    )


def _storage_settings():
    settings = db.session.get(StorageSettings, 1)
    if not settings:
        settings = StorageSettings(id=1, total_quota_bytes=DEFAULT_TOTAL_QUOTA_BYTES)
        db.session.add(settings)
        db.session.flush()
    return settings


def _assigned_quota_bytes(exclude_unit_id=None):
    query = db.session.query(db.func.coalesce(db.func.sum(Unit.quota_bytes), 0))
    if exclude_unit_id is not None:
        query = query.filter(Unit.id != exclude_unit_id)
    return query.scalar()


@bp.get("/")
@login_required
@superadmin_required
def index():
    units = Unit.query.order_by(Unit.name).all()
    settings = _storage_settings()
    assigned_quota_bytes = _assigned_quota_bytes()
    return render_template(
        "units.html",
        units=units,
        used_bytes=_used_bytes,
        total_quota_bytes=settings.total_quota_bytes,
        assigned_quota_bytes=assigned_quota_bytes,
        minimum_total_quota_megabytes=max(1, (assigned_quota_bytes + 1024**2 - 1) // 1024**2),
    )


@bp.post("/settings")
@login_required
@superadmin_required
def update_settings():
    total_quota = _quota_bytes(request.form.get("total_quota_megabytes"))
    assigned_quota = _assigned_quota_bytes()
    if not total_quota:
        flash("Indicá un espacio total válido en megabytes.", "error")
        return redirect(url_for("units.index"))
    if total_quota < assigned_quota:
        flash("El espacio total no puede ser menor al ya asignado a las unidades.", "error")
        return redirect(url_for("units.index"))

    settings = _storage_settings()
    settings.total_quota_bytes = total_quota
    audit("STORAGE_SETTINGS_UPDATE", f"total={total_quota}", "storage_settings", settings.id)
    db.session.commit()
    flash("Espacio total actualizado.", "success")
    return redirect(url_for("units.index"))


@bp.post("/")
@login_required
@superadmin_required
def create():
    name = request.form.get("name", "").strip()
    quota = _quota_bytes(request.form.get("quota_megabytes"))
    if not name or len(name) > 255 or not quota:
        flash("Indicá un nombre y una cuota válida en megabytes.", "error")
        return redirect(url_for("units.index"))
    if Unit.query.filter_by(name=name).first():
        flash("Ya existe una unidad con ese nombre.", "error")
        return redirect(url_for("units.index"))
    settings = _storage_settings()
    if _assigned_quota_bytes() + quota > settings.total_quota_bytes:
        flash("La cuota supera el espacio total disponible para asignar.", "error")
        return redirect(url_for("units.index"))

    unit = Unit(name=name, quota_bytes=quota)
    db.session.add(unit)
    db.session.flush()
    db.session.add(Folder(name=name, unit_id=unit.id, created_by_id=current_user.id))
    audit("UNIT_CREATE", f"{name}; cuota={quota}", "unit", unit.id)
    db.session.commit()
    flash("Unidad creada.", "success")
    return redirect(url_for("units.index"))


@bp.post("/<int:unit_id>/update")
@login_required
@superadmin_required
def update(unit_id):
    unit = db.session.get(Unit, unit_id)
    if not unit:
        abort(404)
    name = request.form.get("name", "").strip()
    quota = _quota_bytes(request.form.get("quota_megabytes"))
    used_bytes = _used_bytes(unit.id)
    if not name or len(name) > 255 or not quota:
        flash("Indicá un nombre y una cuota válida en megabytes.", "error")
        return redirect(url_for("units.index"))
    if quota < used_bytes:
        flash("La cuota no puede ser menor al espacio actualmente utilizado.", "error")
        return redirect(url_for("units.index"))
    settings = _storage_settings()
    if _assigned_quota_bytes(exclude_unit_id=unit.id) + quota > settings.total_quota_bytes:
        flash("La cuota supera el espacio total disponible para asignar.", "error")
        return redirect(url_for("units.index"))
    duplicate = Unit.query.filter(Unit.name == name, Unit.id != unit.id).first()
    if duplicate:
        flash("Ya existe una unidad con ese nombre.", "error")
        return redirect(url_for("units.index"))

    old_name = unit.name
    unit.name = name
    unit.quota_bytes = quota
    root = Folder.query.filter_by(unit_id=unit.id, parent_id=None, name=old_name, deleted_at=None).first()
    if root:
        root.name = name
    audit("UNIT_UPDATE", f"{old_name} -> {name}; cuota={quota}", "unit", unit.id)
    db.session.commit()
    flash("Unidad actualizada.", "success")
    return redirect(url_for("units.index"))
