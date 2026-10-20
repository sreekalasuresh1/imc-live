"""Phase 9 scoped classroom invitations."""
from alembic import op
import sqlalchemy as sa
revision='9b03_class_invitations'
down_revision='8a02_private_documents'
branch_labels=depends_on=None

def upgrade():
    op.create_table('class_access',sa.Column('classroom_id',sa.String(36),sa.ForeignKey('classrooms.id'),primary_key=True),sa.Column('generation',sa.Integer(),nullable=False),sa.Column('open',sa.Boolean(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('join_invitations',*record(),sa.Column('classroom_id',sa.String(36),sa.ForeignKey('class_access.classroom_id'),nullable=False),sa.Column('generation',sa.Integer(),nullable=False),sa.Column('student_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('secret_hash',sa.String(64),unique=True,nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('consumed',sa.Boolean(),nullable=False),sa.Column('revoked',sa.Boolean(),nullable=False))
    op.create_index('ix_join_invitations_classroom_id','join_invitations',['classroom_id'])
    op.create_table('join_sessions',*record(),sa.Column('invitation_id',sa.String(36),sa.ForeignKey('join_invitations.id'),unique=True,nullable=False),sa.Column('token_hash',sa.String(64),unique=True,nullable=False),sa.Column('csrf_token',sa.String(64),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('join_rates',sa.Column('key',sa.String(64),primary_key=True),sa.Column('bucket',sa.Integer(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False))
    op.create_index('ix_join_rates_bucket','join_rates',['bucket'])

def record():
    return [sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False)]

def downgrade():
    op.drop_table('join_sessions');op.drop_table('join_invitations');op.drop_table('class_access');op.drop_table('join_rates')
