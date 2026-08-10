import secrets
from math import ceil
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename

from ..audit import audit
from ..extensions import db, limiter
from ..models import AuditLog, DriveFile, Folder, ShareAccessLog, ShareLink, Unit, utcnow
from ..security import file_content_type, safe_filename, superadmin_required
from ..storage import StorageError, storage

bp = Blueprint("drive", __name__, url_prefix="/drive")


def active_folder(folder_id):
    folder = db.session.get(Folder, folder_id)
    if not folder or folder.deleted_at:
        abort(404)
    if not current_user.is_superadmin and folder.unit_id != current_user.unit_id:
        abort(403)
    return folder


def active_file(file_id):
    item = db.session.get(DriveFile, file_id)
    if not item or item.deleted_at:
        abort(404)
    if not current_user.is_superadmin and item.unit_id != current_user.unit_id:
        abort(403)
    return item


def assigned_unit():
    if current_user.is_superadmin:
        return None
    if not current_user.unit_id:
        abort(403)
    unit = db.session.get(Unit, current_user.unit_id)
    if not unit:
        abort(403)
    return unit


def unit_root(unit, create=False):
    root = Folder.query.filter_by(unit_id=unit.id, parent_id=None, deleted_at=None).first()
    if root or not create:
        return root
    root = Folder(name=unit.name, unit_id=unit.id, created_by_id=current_user.id)
    db.session.add(root)
    db.session.flush()
    return root


def storage_used_bytes(unit_id):
    return (
        db.session.query(func.coalesce(func.sum(DriveFile.size_bytes), 0))
        .filter_by(unit_id=unit_id, deleted_at=None)
        .scalar()
    )


def stream_object(item, disposition="attachment"):
    try:
        stat = storage.stat(item.object_key)
    except StorageError:
        abort(503)
    total = stat.size
    range_header = request.headers.get("Range")
    offset, length, status = 0, total, 200
    headers = {"Accept-Ranges": "bytes"}
    if range_header and range_header.startswith("bytes="):
        try:
            start_text, end_text = range_header[6:].split("-", 1)
            offset = int(start_text) if start_text else 0
            end = int(end_text) if end_text else total - 1
            if offset < 0 or end < offset or end >= total:
                raise ValueError
            length = end - offset + 1
            status = 206
            headers["Content-Range"] = f"bytes {offset}-{end}/{total}"
        except ValueError:
            return Response(status=416, headers={"Content-Range": f"bytes */{total}"})
    response = storage.open(item.object_key, offset=offset, length=length)

    def generate():
        try:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            response.close()
            response.release_conn()

    ascii_name = secure_filename(item.display_name) or "archivo"
    headers["Content-Length"] = str(length)
    headers["Content-Disposition"] = f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{url_quote(item.display_name)}"
    return Response(
        stream_with_context(generate()),
        status=status,
        headers=headers,
        content_type=item.content_type,
        direct_passthrough=True,
    )


def url_quote(value):
    from urllib.parse import quote

    return quote(value, safe="")


@bp.get("/")
@login_required
def index():
    unit = assigned_unit()
    if unit:
        root = unit_root(unit, create=True)
        return browse(root.id)
    return browse(None)


@bp.get("/folder/<int:folder_id>")
@login_required
def browse(folder_id):
    folder = active_folder(folder_id) if folder_id else None
    unit = assigned_unit()
    q = request.args.get("q", "").strip()
    folder_query = Folder.query.filter_by(parent_id=folder_id, deleted_at=None)
    file_query = DriveFile.query.filter_by(folder_id=folder_id, deleted_at=None)
    if unit:
        folder_query = folder_query.filter_by(unit_id=unit.id)
        file_query = file_query.filter_by(unit_id=unit.id)
    if q:
        pattern = f"%{q}%"
        folder_query = folder_query.filter(Folder.name.ilike(pattern))
        file_query = file_query.filter(DriveFile.display_name.ilike(pattern))
    folders = folder_query.order_by(Folder.name.asc()).all()
    files = file_query.order_by(DriveFile.updated_at.desc()).all()
    breadcrumbs = []
    node = folder
    while node:
        breadcrumbs.append(node)
        node = node.parent
    breadcrumbs.reverse()
    recent_link = request.args.get("created_share")
    return render_template(
        "drive.html",
        current_folder=folder,
        folders=folders,
        files=files,
        breadcrumbs=breadcrumbs,
        q=q,
        recent_link=recent_link,
        unit=folder.unit if folder else None,
        used_bytes=storage_used_bytes(folder.unit_id) if folder else None,
        can_manage_content=folder is not None,
        retention_days=current_app.config["FILE_RETENTION_DAYS"],
    )


@bp.post("/folders")
@login_required
def create_folder():
    parent_id = request.form.get("parent_id", type=int)
    if parent_id:
        parent = active_folder(parent_id)
    elif current_user.is_superadmin:
        abort(403)
    else:
        parent = unit_root(assigned_unit(), create=True)
    try:
        name = safe_filename(request.form.get("name"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect_to_folder(parent.id)
    exists = Folder.query.filter_by(parent_id=parent.id, name=name, deleted_at=None).first()
    if exists:
        flash("Ya existe una carpeta con ese nombre.", "error")
        return redirect_to_folder(parent.id)
    folder = Folder(name=name, parent_id=parent.id, unit_id=parent.unit_id, created_by_id=current_user.id)
    db.session.add(folder)
    db.session.flush()
    audit("FOLDER_CREATE", name, "folder", folder.id)
    db.session.commit()
    flash("Carpeta creada.", "success")
    return redirect_to_folder(parent.id)


@bp.post("/folders/<int:folder_id>/rename")
@login_required
def rename_folder(folder_id):
    folder = active_folder(folder_id)
    if folder.parent_id is None:
        abort(403)
    try:
        new_name = safe_filename(request.form.get("name"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect_to_folder(folder.parent_id)
    duplicate = Folder.query.filter(
        Folder.parent_id == folder.parent_id,
        Folder.name == new_name,
        Folder.deleted_at.is_(None),
        Folder.id != folder.id,
    ).first()
    if duplicate:
        flash("Ya existe una carpeta con ese nombre.", "error")
    else:
        old = folder.name
        folder.name = new_name
        audit("FOLDER_RENAME", f"{old} → {new_name}", "folder", folder.id)
        db.session.commit()
        flash("Carpeta renombrada.", "success")
    return redirect_to_folder(folder.parent_id)


def folder_descendants(root):
    result, stack = [root], [root]
    while stack:
        children = Folder.query.filter_by(parent_id=stack.pop().id, deleted_at=None).all()
        result.extend(children)
        stack.extend(children)
    return result


@bp.post("/folders/<int:folder_id>/delete")
@login_required
def delete_folder(folder_id):
    folder = active_folder(folder_id)
    if folder.parent_id is None:
        abort(403)
    nodes = folder_descendants(folder)
    node_ids = [node.id for node in nodes]
    items = DriveFile.query.filter(DriveFile.folder_id.in_(node_ids), DriveFile.deleted_at.is_(None)).all()
    now = utcnow()
    failed = []
    for item in items:
        try:
            storage.delete(item.object_key)
            item.deleted_at = now
            item.deleted_by_id = current_user.id
        except StorageError:
            failed.append(item.display_name)
    if failed:
        db.session.rollback()
        flash("No se eliminó la carpeta: MinIO no pudo borrar todos los archivos.", "error")
        return redirect_to_folder(folder.parent_id)
    for node in nodes:
        node.deleted_at = now
        node.deleted_by_id = current_user.id
    audit("FOLDER_DELETE", f"{folder.name}; {len(items)} archivo(s)", "folder", folder.id)
    db.session.commit()
    flash("Carpeta y contenido eliminados.", "success")
    return redirect_to_folder(folder.parent_id)


@bp.post("/upload")
@login_required
@limiter.limit("30 per hour")
def upload():
    folder_id = request.form.get("folder_id", type=int)
    if folder_id:
        folder = active_folder(folder_id)
    elif current_user.is_superadmin:
        abort(403)
    else:
        folder = unit_root(assigned_unit(), create=True)
    uploads = request.files.getlist("files")
    uploads = [item for item in uploads if item and item.filename]
    if not uploads:
        flash("Seleccioná al menos un archivo.", "error")
        return redirect_to_folder(folder.id)
    created = []
    uploaded_keys = []
    try:
        unit = Unit.query.filter_by(id=folder.unit_id).populate_existing().with_for_update().one()
        used_bytes = storage_used_bytes(unit.id)
        for upload_item in uploads:
            display_name = safe_filename(upload_item.filename)
            stored = storage.upload(upload_item)
            uploaded_keys.append(stored.object_key)
            if used_bytes + stored.size_bytes > unit.quota_bytes:
                storage.delete(stored.object_key)
                uploaded_keys.pop()
                raise ValueError("La unidad no tiene espacio disponible para completar la carga.")
            item = DriveFile(
                folder_id=folder.id,
                unit_id=unit.id,
                display_name=display_name,
                object_key=stored.object_key,
                content_type=file_content_type(display_name, upload_item.mimetype),
                size_bytes=stored.size_bytes,
                etag=stored.etag,
                sha256=stored.sha256,
                uploaded_by_id=current_user.id,
            )
            db.session.add(item)
            db.session.flush()
            created.append(item)
            used_bytes += stored.size_bytes
            audit("FILE_UPLOAD", f"{display_name} ({stored.size_bytes} bytes)", "file", item.id)
        db.session.commit()
        flash(f"{len(created)} archivo(s) subido(s).", "success")
    except (StorageError, ValueError) as exc:
        db.session.rollback()
        for object_key in uploaded_keys:
            try:
                storage.delete(object_key)
            except StorageError:
                current_app.logger.exception("Falló rollback de objeto %s", object_key)
        flash(str(exc), "error")
    return redirect_to_folder(folder.id)


@bp.post("/files/<int:file_id>/rename")
@login_required
def rename_file(file_id):
    item = active_file(file_id)
    try:
        new_name = safe_filename(request.form.get("name"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect_to_folder(item.folder_id)
    old = item.display_name
    item.display_name = new_name
    audit("FILE_RENAME", f"{old} → {new_name}", "file", item.id)
    db.session.commit()
    flash("Archivo renombrado.", "success")
    return redirect_to_folder(item.folder_id)


@bp.post("/files/<int:file_id>/delete")
@login_required
def delete_file(file_id):
    item = active_file(file_id)
    folder_id = item.folder_id
    try:
        storage.delete(item.object_key)
    except StorageError as exc:
        flash(str(exc), "error")
        return redirect_to_folder(folder_id)
    item.deleted_at = utcnow()
    item.deleted_by_id = current_user.id
    audit("FILE_DELETE", item.display_name, "file", item.id)
    db.session.commit()
    flash("Archivo eliminado.", "success")
    return redirect_to_folder(folder_id)


@bp.get("/files/<int:file_id>/download")
@login_required
def download_file(file_id):
    item = active_file(file_id)
    audit("FILE_DOWNLOAD_INTERNAL", item.display_name, "file", item.id)
    db.session.commit()
    return stream_object(item)


@bp.post("/files/<int:file_id>/share")
@login_required
def create_share(file_id):
    item = active_file(file_id)
    token = secrets.token_urlsafe(32)
    max_downloads = request.form.get("max_downloads", type=int)
    expires_at = item.created_at + timedelta(days=current_app.config["FILE_RETENTION_DAYS"])
    link = ShareLink(
        token_hash=ShareLink.digest(token),
        file_id=item.id,
        created_by_id=current_user.id,
        expires_at=expires_at,
        max_downloads=max_downloads if max_downloads and max_downloads > 0 else None,
        label=(request.form.get("label") or "").strip()[:255] or None,
    )
    link.set_password(request.form.get("password", ""))
    db.session.add(link)
    db.session.flush()
    audit("SHARE_CREATE", f"Enlace para {item.display_name}", "share", link.id)
    db.session.commit()
    public_url = f"{current_app.config['PUBLIC_BASE_URL']}{url_for('share.open_share', token=token)}"
    return render_template("share_created.html", item=item, link=link, public_url=public_url)


@bp.post("/shares/<int:share_id>/revoke")
@login_required
def revoke_share(share_id):
    link = db.session.get(ShareLink, share_id)
    if not link:
        abort(404)
    active_file(link.file_id)
    folder_id = link.file.folder_id
    link.is_active = False
    audit("SHARE_REVOKE", f"Enlace para {link.file.display_name}", "share", link.id)
    db.session.commit()
    flash("Enlace revocado.", "success")
    return redirect_to_folder(folder_id)


@bp.get("/audit")
@login_required
@superadmin_required
def audit_logs():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "").strip()
    query = AuditLog.query
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(AuditLog.username.ilike(pattern), AuditLog.action.ilike(pattern), AuditLog.details.ilike(pattern))
        )
    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50)
    share_logs = (
        ShareAccessLog.query.order_by(ShareAccessLog.created_at.desc()).limit(100).all()
        if page == 1 and not q
        else []
    )
    return render_template("audit.html", pagination=pagination, share_logs=share_logs, q=q)


@bp.get("/expiration")
@login_required
@superadmin_required
def expiration_panel():
    now = utcnow()
    retention_days = current_app.config["FILE_RETENTION_DAYS"]
    files = []
    for item in DriveFile.query.filter_by(deleted_at=None).order_by(DriveFile.created_at.asc()).all():
        expires_at = item.created_at + timedelta(days=retention_days)
        seconds_left = (expires_at - now).total_seconds()
        days_left = max(0, ceil(seconds_left / 86400))
        color = "red" if seconds_left <= 2 * 86400 else "yellow" if seconds_left <= 7 * 86400 else "green"
        files.append({"item": item, "expires_at": expires_at, "days_left": days_left, "color": color})
    return render_template("expiration.html", files=files, retention_days=retention_days)


def redirect_to_folder(folder_id):
    return redirect(url_for("drive.browse", folder_id=folder_id) if folder_id else url_for("drive.index"))
