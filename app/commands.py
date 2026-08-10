import click
from datetime import timedelta

from flask import current_app
from flask.cli import with_appcontext
from flask_migrate import upgrade

from .extensions import db
from .audit import audit
from .models import DriveFile, Unit, User, utcnow
from .storage import storage


def _ensure_schema():
    """Apply pending migrations before querying or creating a user."""
    click.echo("Verificando migraciones...")
    upgrade()


@click.command("create-admin")
@click.argument("username")
@click.argument("email")
@click.argument("password")
@click.argument("is_superuser", default="false")
@click.argument("unit_name", required=False)
@with_appcontext
def create_admin(username, email, password, is_superuser, unit_name):
    """Crea un admin o superadmin sin interacción, como sample-backend."""
    try:
        _ensure_schema()
    except Exception as exc:
        db.session.rollback()
        raise click.ClickException(f"No se pudo preparar la base de datos: {exc}") from exc

    username = username.strip()
    email = email.strip().lower()
    if User.query.filter((User.email == email) | (User.username == username)).first():
        click.secho(f"Error: el usuario {email} o el nombre {username} ya existe.", fg="red")
        return

    role = "superadmin" if str(is_superuser).strip().lower() == "true" else "admin"
    unit = None
    if role == "admin":
        if not unit_name:
            raise click.ClickException("Los admins requieren una unidad existente como quinto argumento.")
        unit = Unit.query.filter_by(name=unit_name.strip()).first()
        if not unit:
            raise click.ClickException(f"La unidad '{unit_name}' no existe.")
    try:
        user = User(username=username, email=email, role=role, unit_id=getattr(unit, "id", None), is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        label = "Super Admin" if role == "superadmin" else "Admin"
        click.secho(f"{label} {username} creado correctamente.", fg="green")
    except Exception as exc:
        db.session.rollback()
        click.secho(f"Error creando usuario: {exc}", fg="red")


@click.command("init-storage")
@with_appcontext
def init_storage():
    storage._require_client()
    click.echo(f"Bucket privado '{storage.bucket}' listo.")


@click.command("prune-expired-files")
@with_appcontext
def prune_expired_files():
    """Elimina objetos y registros que superaron su vida útil."""
    retention_days = current_app.config["FILE_RETENTION_DAYS"]
    cutoff = utcnow() - timedelta(days=retention_days)
    dialect = db.engine.dialect.name
    lock_acquired = True
    if dialect in {"mariadb", "mysql"}:
        lock_acquired = bool(
            db.session.execute(db.text("SELECT GET_LOCK('drive_expired_file_cleanup', 0)")).scalar()
        )
    if not lock_acquired:
        click.echo("La limpieza ya se está ejecutando en otra instancia.")
        return

    deleted = 0
    failed = 0
    try:
        expired_ids = [
            file_id
            for (file_id,) in (
                DriveFile.query.with_entities(DriveFile.id)
                .filter(DriveFile.deleted_at.is_(None), DriveFile.created_at <= cutoff)
                .order_by(DriveFile.created_at)
                .all()
            )
        ]
        for file_id in expired_ids:
            item = DriveFile.query.filter_by(id=file_id, deleted_at=None).with_for_update().first()
            if not item:
                continue
            try:
                storage.delete(item.object_key)
                item.deleted_at = utcnow()
                audit(
                    "FILE_EXPIRE_DELETE",
                    f"{item.display_name}; vencimiento de {retention_days} días",
                    "file",
                    item.id,
                )
                db.session.commit()
                deleted += 1
            except Exception:
                db.session.rollback()
                current_app.logger.exception("No se pudo eliminar el archivo vencido %s", file_id)
                failed += 1
    finally:
        if dialect in {"mariadb", "mysql"}:
            db.session.execute(db.text("SELECT RELEASE_LOCK('drive_expired_file_cleanup')"))
            db.session.commit()

    click.echo(f"Limpieza completada: {deleted} eliminado(s), {failed} con error.")
