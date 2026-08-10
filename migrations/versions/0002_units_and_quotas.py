"""Add organizational units and storage quotas.

Revision ID: 0002_units_and_quotas
Revises: 0001_drive_initial
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "0002_units_and_quotas"
down_revision = "0001_drive_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name"),
    )
    operations = (
        ("users", "fk_users_unit_id", "SET NULL"),
        ("folders", "fk_folders_unit_id", "CASCADE"),
        ("drive_files", "fk_drive_files_unit_id", "CASCADE"),
    )
    for table, constraint, ondelete in operations:
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column("unit_id", sa.Integer(), nullable=True))
                batch.create_foreign_key(constraint, "units", ["unit_id"], ["id"], ondelete=ondelete)
                batch.create_index(f"ix_{table}_unit_id", ["unit_id"])
        else:
            op.add_column(table, sa.Column("unit_id", sa.Integer(), nullable=True))
            op.create_foreign_key(constraint, table, "units", ["unit_id"], ["id"], ondelete=ondelete)
            op.create_index(f"ix_{table}_unit_id", table, ["unit_id"])

    bind = op.get_bind()
    existing_records = sum(
        bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        for table in ("users", "folders", "drive_files")
    )
    if not existing_records:
        return

    now = datetime.utcnow()
    units = sa.table(
        "units",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("quota_bytes", sa.BigInteger),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        units,
        [{
            "name": "Unidad sin asignar",
            "quota_bytes": 1_099_511_627_776,
            "created_at": now,
            "updated_at": now,
        }],
    )
    legacy_unit_id = bind.execute(
        sa.select(units.c.id).where(units.c.name == "Unidad sin asignar")
    ).scalar_one()
    bind.execute(sa.text("UPDATE users SET unit_id = :unit_id WHERE role = 'admin'"), {"unit_id": legacy_unit_id})
    bind.execute(sa.text("UPDATE folders SET unit_id = :unit_id"), {"unit_id": legacy_unit_id})
    bind.execute(sa.text("UPDATE drive_files SET unit_id = :unit_id"), {"unit_id": legacy_unit_id})


def downgrade():
    op.drop_index("ix_drive_files_unit_id", table_name="drive_files")
    op.drop_constraint("fk_drive_files_unit_id", "drive_files", type_="foreignkey")
    op.drop_column("drive_files", "unit_id")
    op.drop_index("ix_folders_unit_id", table_name="folders")
    op.drop_constraint("fk_folders_unit_id", "folders", type_="foreignkey")
    op.drop_column("folders", "unit_id")
    op.drop_index("ix_users_unit_id", table_name="users")
    op.drop_constraint("fk_users_unit_id", "users", type_="foreignkey")
    op.drop_column("users", "unit_id")
    op.drop_table("units")
