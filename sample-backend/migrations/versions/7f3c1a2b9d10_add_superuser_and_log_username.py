"""Add superuser and log username

Revision ID: 7f3c1a2b9d10
Revises: 4224d59394a9
Create Date: 2026-01-26 10:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f3c1a2b9d10'
down_revision = '4224d59394a9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_unique_constraint('uq_users_username', ['username'])

    with op.batch_alter_table('activity_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username', sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f('ix_activity_logs_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_activity_logs_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_activity_logs_username'), ['username'], unique=False)



def downgrade():
    with op.batch_alter_table('activity_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_activity_logs_username'))
        batch_op.drop_index(batch_op.f('ix_activity_logs_action'))
        batch_op.drop_index(batch_op.f('ix_activity_logs_created_at'))
        batch_op.drop_column('username')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('uq_users_username', type_='unique')
        batch_op.drop_column('is_superuser')
        batch_op.drop_column('username')
