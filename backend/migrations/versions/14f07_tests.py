"""Private tests and server-controlled attempt clocks."""
from alembic import op
import sqlalchemy as sa
revision='14f07_tests'
down_revision='13e06_corrections'
branch_labels=depends_on=None
def upgrade():
    op.add_column('hw_drafts',sa.Column('work_type',sa.String(16),nullable=False,server_default='HOMEWORK'))
    op.create_table('test_attempt_clocks',sa.Column('assignment_id',sa.String(36),sa.ForeignKey('hw_recipients.id'),primary_key=True),sa.Column('attempt',sa.Integer(),nullable=False),sa.Column('started_at',sa.DateTime(timezone=True),nullable=True),sa.Column('deadline_at',sa.DateTime(timezone=True),nullable=True),sa.Column('closed_submission_id',sa.String(36),sa.ForeignKey('hw_submissions.id'),nullable=True))
def downgrade():raise RuntimeError('Restore a backup rather than removing test timing and history.')
