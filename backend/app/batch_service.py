from sqlalchemy import select,update
from .models import Batch,BatchMember,User,StudentProfile
from . import homework_service as hw

def owned(db,id,uid,lock=False):
    row=db.scalar(select(Batch).where(Batch.id==id,Batch.teacher_id==uid))
    if not row:hw.fail('Batch not found.',404)
    if lock:
        db.execute(update(Batch).where(Batch.id==id).values(revision=Batch.revision).execution_options(synchronize_session=False));db.refresh(row)
    return row

def members(db,id):
    return list(db.scalars(select(User).join(BatchMember,BatchMember.student_id==User.id).where(BatchMember.batch_id==id).order_by(User.name,User.id)))

def summary(db,row):
    return dict(id=row.id,name=row.name,revision=row.revision,students=[dict(id=x.id,name=x.name,active=x.active) for x in members(db,row.id)])

def check_revision(row,expected):
    if expected is None or row.revision!=expected:hw.fail('This batch changed or has not been reviewed. Refresh and review its students before continuing.',409)

def valid_students(db,uid,ids):
    for id in ids:hw.student(db,uid,id)
