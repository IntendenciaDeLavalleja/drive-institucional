"""Initial schema: create base tables

Revision ID: 0000_initial_schema
Revises: 
Create Date: 2026-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0000_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # users — no incluye username/is_superuser (agregados en 7f3c1a2b9d10)
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # tickets — sin location_lat/location_lng (agregados en a1b2c3d4e5f6)
    op.create_table(
        'tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tracking_code', sa.String(length=50), nullable=False),
        sa.Column('municipality_or_destination', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('NEW', 'IN_PROGRESS', 'RESOLVED', 'ARCHIVED', name='ticketstatus'), nullable=False, server_default='NEW'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tracking_code'),
    )
    op.create_index('ix_tickets_tracking_code', 'tickets', ['tracking_code'], unique=True)
    op.create_index('ix_tickets_email', 'tickets', ['email'], unique=False)
    op.create_index('ix_tickets_status', 'tickets', ['status'], unique=False)
    op.create_index('ix_tickets_created_at', 'tickets', ['created_at'], unique=False)

    # ticket_attachments
    op.create_table(
        'ticket_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('object_key', sa.String(length=255), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ticket_attachments_ticket_id', 'ticket_attachments', ['ticket_id'], unique=False)

    # ticket_status_history
    op.create_table(
        'ticket_status_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('old_status', sa.String(length=50), nullable=True),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ticket_status_history_ticket_id', 'ticket_status_history', ['ticket_id'], unique=False)

    # activity_logs — sin username (agregado en 7f3c1a2b9d10)
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('activity_logs')
    op.drop_table('ticket_status_history')
    op.drop_table('ticket_attachments')
    op.drop_index('ix_tickets_created_at', table_name='tickets')
    op.drop_index('ix_tickets_status', table_name='tickets')
    op.drop_index('ix_tickets_email', table_name='tickets')
    op.drop_index('ix_tickets_tracking_code', table_name='tickets')
    op.drop_table('tickets')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
