"""Atomic authentication throttling."""
from alembic import op
import sqlalchemy as sa
revision='17c10_security'
down_revision='16b09_batches'
branch_labels=depends_on=None
def upgrade():
    op.create_table('security_rate_buckets',sa.Column('key',sa.String(64),primary_key=True),sa.Column('bucket',sa.Integer(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False))
    op.create_index('ix_security_rate_buckets_bucket','security_rate_buckets',['bucket'])
def downgrade():raise RuntimeError('Restore a backup rather than removing active authentication controls.')
