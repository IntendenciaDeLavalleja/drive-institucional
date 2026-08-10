"""Enforce unit assignment by user role.

Revision ID: 0003_enforce_user_unit_roles
Revises: 0002_units_and_quotas
"""

from alembic import op


revision = "0003_enforce_user_unit_roles"
down_revision = "0002_units_and_quotas"
branch_labels = None
depends_on = None


CONSTRAINT = "(role = 'superadmin' AND unit_id IS NULL) OR (role = 'admin' AND unit_id IS NOT NULL)"


def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch:
            batch.create_check_constraint("ck_users_role_unit", CONSTRAINT)


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch:
            batch.drop_constraint("ck_users_role_unit", type_="check")
