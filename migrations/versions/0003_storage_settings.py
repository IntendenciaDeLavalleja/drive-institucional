"""Add the global assignable storage limit.

Revision ID: 0003_storage_settings
Revises: 0002_units_and_quotas
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "0003_storage_settings"
down_revision = "0002_units_and_quotas"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "storage_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("total_quota_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.bulk_insert(
        sa.table(
            "storage_settings",
            sa.column("id", sa.Integer),
            sa.column("total_quota_bytes", sa.BigInteger),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [{
            "id": 1,
            "total_quota_bytes": 1024**4,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }],
    )


def downgrade():
    op.drop_table("storage_settings")