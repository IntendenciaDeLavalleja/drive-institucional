"""Add location fields to tickets

Revision ID: a1b2c3d4e5f6
Revises: 4224d59394a9
Create Date: 2026-03-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '7f3c1a2b9d10'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tickets', sa.Column('location_lat', sa.Float(), nullable=True))
    op.add_column('tickets', sa.Column('location_lng', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('tickets', 'location_lng')
    op.drop_column('tickets', 'location_lat')
