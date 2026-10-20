"""Phase 8: private documents/assets and flexible grade labels.

Legacy numeric grade columns remain intact for safe additive migration.
"""
from alembic import op
import sqlalchemy as sa

revision = '8a02_private_documents'
down_revision = '6f73a0b718ac'
branch_labels = depends_on = None


def upgrade():
    for table in ('student_profiles', 'classrooms'):
        op.add_column(table, sa.Column('grade_label', sa.String(100), nullable=False, server_default=''))
        op.execute(sa.text(f'UPDATE {table} SET grade_label = CAST(grade AS VARCHAR(100))'))
    op.create_table('private_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('body', sa.JSON(), nullable=False))
    op.create_index('ix_private_documents_owner_id', 'private_documents', ['owner_id'])
    op.create_table('private_assets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('private_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('png', sa.LargeBinary(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False))
    op.create_index('ix_private_assets_document_id', 'private_assets', ['document_id'])


def downgrade():
    raise RuntimeError('This migration stores new user work. Restore a pre-upgrade backup to roll back safely.')
