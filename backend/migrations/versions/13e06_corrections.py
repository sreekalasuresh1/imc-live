"""Private correction layers, explicit immutable returns and classroom copy provenance."""
from alembic import op
import sqlalchemy as sa
revision = '13e06_corrections'
down_revision = '12d05_homework'
branch_labels = depends_on = None

def record():
    return [sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False)]
def col(name,kind):return sa.Column(name,kind,nullable=False)
def fk(name,target,**kw):return sa.Column(name,sa.String(36),sa.ForeignKey(target),nullable=False,**kw)
def upgrade():
    op.create_table('work_corrections',*record(),fk('submission_id','hw_submissions.id',unique=True),col('revision',sa.Integer()),col('body',sa.JSON()))
    op.create_table('work_correction_saves',fk('correction_id','work_corrections.id',primary_key=True),sa.Column('key',sa.String(80),primary_key=True),col('fingerprint',sa.String(64)),col('revision',sa.Integer()))
    op.create_table('work_correction_returns',*record(),fk('correction_id','work_corrections.id'),col('number',sa.Integer()),col('key',sa.String(80)),col('draft_revision',sa.Integer()),col('body',sa.JSON()),sa.UniqueConstraint('correction_id','number'),sa.UniqueConstraint('correction_id','key'))
    op.create_table('work_classroom_copies',*record(),fk('submission_id','hw_submissions.id'),fk('document_id','private_documents.id',unique=True),col('key',sa.String(80)),col('fingerprint',sa.String(64)),sa.Column('correction_revision',sa.Integer(),nullable=True),sa.UniqueConstraint('submission_id','key'))
    op.create_table('work_copy_publications',fk('class_id','classrooms.id',primary_key=True),sa.Column('generation',sa.Integer(),primary_key=True),fk('copy_id','work_classroom_copies.id'),fk('board_id','live_boards.id'),col('fingerprint',sa.String(64)))
def downgrade():raise RuntimeError('Restore a backup rather than deleting correction history.')
