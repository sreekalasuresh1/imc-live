"""Versioned batch rosters and immutable assignment provenance."""
from alembic import op
import sqlalchemy as sa
revision='16b09_batches'
down_revision='15a08_parents'
branch_labels=depends_on=None
def upgrade():
    op.add_column('batches',sa.Column('revision',sa.Integer(),nullable=False,server_default='0'))
    op.create_table('batch_publications',sa.Column('version_id',sa.String(36),sa.ForeignKey('hw_versions.id'),primary_key=True),sa.Column('batch_id',sa.String(36),sa.ForeignKey('batches.id'),nullable=False),sa.Column('batch_name',sa.String(120),nullable=False),sa.Column('batch_revision',sa.Integer(),nullable=False),sa.Column('recipients',sa.JSON(),nullable=False))
    op.create_index('ix_batch_publications_batch_id','batch_publications',['batch_id'])
def downgrade():raise RuntimeError('Restore a backup rather than removing batch assignment history.')
