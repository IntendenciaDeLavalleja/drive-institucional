"""Merge unit-role and global-storage migrations.

Revision ID: 0004_merge_unit_storage
Revises: 0003_enforce_user_unit_roles, 0003_storage_settings
"""


revision = "0004_merge_unit_storage"
down_revision = ("0003_enforce_user_unit_roles", "0003_storage_settings")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
