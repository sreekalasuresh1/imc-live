"""Versioned homework and separate student portal access."""
from alembic import op
import sqlalchemy as sa
revision='12d05_homework'
down_revision='10c04_live_classroom'
branch_labels=depends_on=None
def record():return [sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False)]
def fk(name,target):return sa.Column(name,sa.String(36),sa.ForeignKey(target),nullable=False)
def col(name,type):return sa.Column(name,type,nullable=False)
def upgrade():
    op.create_table('hw_drafts',*record(),fk('teacher_id','users.id'),col('source_id',sa.String(80)),col('revision',sa.Integer()),col('document',sa.JSON()),col('details',sa.JSON()),col('assets',sa.JSON()),sa.UniqueConstraint('teacher_id','source_id'))
    op.create_table('hw_versions',*record(),fk('draft_id','hw_drafts.id'),col('number',sa.Integer()),col('publish_key',sa.String(80)),col('fingerprint',sa.String(64)),col('document',sa.JSON()),col('details',sa.JSON()),sa.UniqueConstraint('draft_id','number'),sa.UniqueConstraint('draft_id','publish_key'))
    op.create_table('hw_images',sa.Column('version_id',sa.String(36),sa.ForeignKey('hw_versions.id'),primary_key=True),sa.Column('id',sa.String(80),primary_key=True),col('png',sa.LargeBinary()))
    op.create_table('hw_recipients',*record(),fk('version_id','hw_versions.id'),fk('student_id','users.id'),col('status',sa.String(30)),col('resubmit',sa.Boolean()),col('revision',sa.Integer()),col('answers',sa.JSON()),sa.UniqueConstraint('version_id','student_id'))
    op.create_table('hw_submissions',*record(),fk('assignment_id','hw_recipients.id'),col('number',sa.Integer()),col('submit_key',sa.String(80)),col('draft_revision',sa.Integer()),col('answers',sa.JSON()),sa.UniqueConstraint('assignment_id','number'),sa.UniqueConstraint('assignment_id','submit_key'))
    op.create_table('hw_saves',sa.Column('assignment_id',sa.String(36),sa.ForeignKey('hw_recipients.id'),primary_key=True),sa.Column('save_key',sa.String(80),primary_key=True),col('fingerprint',sa.String(64)),col('revision',sa.Integer()))
    op.create_table('hw_events',*record(),fk('assignment_id','hw_recipients.id'),col('action',sa.String(30)),col('revision',sa.Integer()))
    op.create_table('hw_grants',*record(),fk('teacher_id','users.id'),fk('student_id','users.id'),sa.Column('secret_hash',sa.String(64),nullable=False,unique=True),col('consumed',sa.Boolean()),col('revoked',sa.Boolean()),col('expires_at',sa.DateTime(timezone=True)))
    op.create_table('hw_portal_sessions',*record(),sa.Column('grant_id',sa.String(36),sa.ForeignKey('hw_grants.id'),nullable=False,unique=True),sa.Column('token_hash',sa.String(64),nullable=False,unique=True),col('csrf_token',sa.String(64)),col('expires_at',sa.DateTime(timezone=True)))
def downgrade():raise RuntimeError('Restore a backup rather than deleting homework or submission history.')
