"""Durable, isolated live classrooms."""
from alembic import op
import sqlalchemy as sa
revision='10c04_live_classroom'
down_revision='9b03_class_invitations'
branch_labels=depends_on=None
def upgrade():
    op.create_table('live_boards',sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.Column('classroom_id',sa.String(36),sa.ForeignKey('classrooms.id'),nullable=False),sa.Column('generation',sa.Integer(),nullable=False),sa.Column('sequence',sa.Integer(),nullable=False),sa.Column('document',sa.JSON(),nullable=False),sa.Column('authors',sa.JSON(),nullable=False),sa.Column('writers',sa.JSON(),nullable=False),sa.UniqueConstraint('classroom_id','generation'))
    op.create_table('live_operations',sa.Column('board_id',sa.String(36),sa.ForeignKey('live_boards.id'),primary_key=True),sa.Column('operation_id',sa.String(80),primary_key=True),sa.Column('sequence',sa.Integer(),nullable=False),sa.Column('actor',sa.String(64),nullable=False),sa.Column('request',sa.JSON(),nullable=False),sa.Column('event',sa.JSON(),nullable=False),sa.UniqueConstraint('board_id','sequence'))
    op.create_table('live_assets',sa.Column('board_id',sa.String(36),sa.ForeignKey('live_boards.id'),primary_key=True),sa.Column('id',sa.String(36),primary_key=True),sa.Column('png',sa.LargeBinary(),nullable=False))
    op.create_table('live_transients',sa.Column('board_id',sa.String(36),sa.ForeignKey('live_boards.id'),primary_key=True),sa.Column('actor',sa.String(64),primary_key=True),sa.Column('body',sa.JSON(),nullable=False),sa.Column('expires',sa.Float(),nullable=False))
def downgrade():
    raise RuntimeError('Restore a backup rather than deleting live lesson history.')
