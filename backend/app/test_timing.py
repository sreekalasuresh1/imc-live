"""Server-authoritative clocks; never trust a client timestamp or reconnect duration."""
import copy
from uuid import uuid4
from datetime import timedelta
from sqlalchemy import select,func
from .models import now
from .test_models import TestClock
from .homework_models import HomeworkSubmission,HomeworkRecipient,HomeworkVersion,HomeworkDraft
from . import homework_service as hw
from .routes.join import utc

def is_test(version):return version.details.get('workType')=='TEST'
def clock(db,row):
    value=db.get(TestClock,row.id)
    if not value:value=TestClock(assignment_id=row.id,attempt=1);db.add(value);db.flush()
    return value
def info(db,row,version):
    if not is_test(version):return {}
    c=clock(db,row)
    return dict(attempt=c.attempt,started_at=utc(c.started_at) if c.started_at else None,deadline_at=utc(c.deadline_at) if c.deadline_at else None,server_now=now(),timeLimitMinutes=version.details.get('timeLimitMinutes',0))
def start(db,row,version):
    if not is_test(version):hw.fail('This assignment is not a test.',400)
    c=clock(db,row)
    if row.status=='SUBMITTED':return c
    if not c.started_at:
        c.started_at=now();minutes=version.details.get('timeLimitMinutes',0);c.deadline_at=c.started_at+timedelta(minutes=minutes) if minutes else None
        row.status='IN_PROGRESS';hw.event(db,row,'TEST_STARTED');db.commit()
    return c
def expire(db,row,version):
    if not is_test(version):return
    c=clock(db,row)
    if row.status!='SUBMITTED' and c.deadline_at and utc(c.deadline_at)<=now():
        number=(db.scalar(select(func.max(HomeworkSubmission.number)).where(HomeworkSubmission.assignment_id==row.id)) or 0)+1
        submission=HomeworkSubmission(assignment_id=row.id,number=number,submit_key='server-timeout-'+str(uuid4()),draft_revision=row.revision,answers=copy.deepcopy(row.answers));db.add(submission);db.flush()
        c.closed_submission_id=submission.id;row.status='SUBMITTED';row.resubmit=False;hw.event(db,row,'TEST_TIME_EXPIRED');db.commit()
def require_started(db,row,version):
    if is_test(version) and not clock(db,row).started_at:hw.fail('Start this test before opening its questions or saving answers.',409)
def refresh(db,row,version):
    if is_test(version):
        row,version,_=hw.assignment(db,row.id,lock=True);expire(db,row,version)
    return row
def reset(db,row,version):
    if is_test(version):
        c=clock(db,row);c.attempt+=1;c.started_at=None;c.deadline_at=None;c.closed_submission_id=None;row.revision+=1
def finish(db,row,version,submission):
    if is_test(version):clock(db,row).closed_submission_id=submission.id
def expire_teacher(db,teacher_id):
    rows=db.execute(select(HomeworkRecipient,HomeworkVersion).join(HomeworkVersion,HomeworkVersion.id==HomeworkRecipient.version_id).join(HomeworkDraft,HomeworkDraft.id==HomeworkVersion.draft_id).where(HomeworkDraft.teacher_id==teacher_id,HomeworkDraft.work_type=='TEST',HomeworkRecipient.status!='SUBMITTED')).all()
    for r,v in rows:refresh(db,r,v)
