"""Optional, scoped parent sharing and read-only sessions."""
from alembic import op
import sqlalchemy as sa
revision = '15a08_parents'
down_revision = '14f07_tests'
branch_labels = depends_on = None

def records():
    return [sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False)]

def upgrade():
    op.create_table('parent_shares',*records(),sa.Column('teacher_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('assignment_id',sa.String(36),sa.ForeignKey('hw_recipients.id'),nullable=False),sa.Column('version_id',sa.String(36),sa.ForeignKey('hw_versions.id'),nullable=False),sa.Column('secret_hash',sa.String(64),unique=True,nullable=False),sa.Column('selection',sa.JSON(),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('revoked',sa.Boolean(),nullable=False))
    op.create_index('ix_parent_shares_teacher_id','parent_shares',['teacher_id'])
    op.create_table('parent_view_sessions',*records(),sa.Column('share_id',sa.String(36),sa.ForeignKey('parent_shares.id'),nullable=False),sa.Column('token_hash',sa.String(64),unique=True,nullable=False))
    op.create_index('ix_parent_view_sessions_share_id','parent_view_sessions',['share_id'])

def downgrade():
    raise RuntimeError('Restore a backup rather than deleting parent sharing history.')
