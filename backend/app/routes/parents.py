"""Parent links expose only a teacher-previewed immutable selection."""
import copy
import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, now
from ..security import teacher, digest, rate_limit
from ..config import settings
from ..homework_models import HomeworkRecipient, HomeworkVersion, HomeworkDraft, HomeworkSubmission, HomeworkImage
from ..correction_models import CorrectionDraft, CorrectionReturn
from ..parent_models import ParentShare, ParentSession
from .. import homework_service as hw
from .join import utc

router = APIRouter(tags=['Parent sharing'])
COOKIE = 'classroom_parent_view'
COOKIE_PATH = '/api/parent-portal'

class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assignment_id: str = Field(min_length=1,max_length=36)
    submission_id: str | None = Field(default=None,max_length=36)
    return_id: str | None = Field(default=None,max_length=36)
    questions: StrictBool = False
    answers: StrictBool = False
    corrections: StrictBool = False
    comments: StrictBool = False
    marks: StrictBool = False

class Create(Selection):
    days: StrictInt = Field(default=7,ge=1,le=30)
    preview_hash: str = Field(pattern=r'^[a-f0-9]{64}$')

class Redeem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: str = Field(min_length=40,max_length=100)

def projected(db, selection, uid):
    r,v,d = hw.assignment(db,selection.assignment_id,teacher_id=uid)
    if not any([selection.questions,selection.answers,selection.corrections,selection.comments,selection.marks]):
        hw.fail('Choose at least one item to share.',422)
    s = db.get(HomeworkSubmission,selection.submission_id) if selection.submission_id else None
    if selection.submission_id and (not s or s.assignment_id!=r.id):hw.fail('Submission not found.',404)
    if selection.answers and not s:hw.fail('Choose a submitted version for answers.',422)
    returned = None
    if selection.return_id:
        returned = db.scalar(select(CorrectionReturn).join(CorrectionDraft,CorrectionDraft.id==CorrectionReturn.correction_id).where(CorrectionReturn.id==selection.return_id,CorrectionDraft.submission_id==selection.submission_id))
        if not returned:hw.fail('Returned correction not found.',404)
    if any([selection.corrections,selection.comments,selection.marks]) and not returned:
        hw.fail('Choose a returned correction version. Private drafts cannot be shared.',422)
    # Explicit allowlist: never serialize draft metadata, roster, provenance or private fields.
    result = dict(title=v.document['title'],student=db.get(User,r.student_id).name,work_type=v.details.get('workType','HOMEWORK'),assignment_version=v.number,creation_date=v.document['creationDate'],included={k:getattr(selection,k) for k in ['questions','answers','corrections','comments','marks']})
    if selection.questions:result.update(instructions=v.details.get('instructions',''),due_date=v.details.get('dueDate',''))
    if selection.answers:result['submission_number']=s.number
    if returned and any([selection.corrections,selection.comments,selection.marks]):result['correction_number']=returned.number
    if selection.comments:result['comments']=returned.body['comments']
    if selection.marks:result['marks']=returned.body['marks']
    if any([selection.questions,selection.answers,selection.corrections]):
        answers={p['id']:p['objects'] for p in s.answers['pages']} if s else {}
        corrections={p['id']:p['objects'] for p in returned.body['pages']} if returned else {}
        pages=[]
        for p in v.document['pages']:
            objects=[]
            if selection.questions:objects.extend(copy.deepcopy(p['objects']))
            if selection.answers:objects.extend(copy.deepcopy(answers[p['id']]))
            if selection.corrections:objects.extend(copy.deepcopy(corrections[p['id']]))
            pages.append(dict(id=p['id'],objects=objects))
        result['document']={'pages':pages}
    return result,v

@router.get('/parent-sharing/options')
def options(user:User=Depends(teacher),db:Session=Depends(get_db)):
    rows=db.execute(select(HomeworkRecipient,HomeworkVersion).join(HomeworkVersion,HomeworkVersion.id==HomeworkRecipient.version_id).join(HomeworkDraft,HomeworkDraft.id==HomeworkVersion.draft_id).where(HomeworkDraft.teacher_id==user.id).order_by(HomeworkRecipient.created_at.desc())).all()
    result=[]
    for r,v in rows:
        submissions=[]
        for s in db.scalars(select(HomeworkSubmission).where(HomeworkSubmission.assignment_id==r.id).order_by(HomeworkSubmission.number)):
            returns=list(db.scalars(select(CorrectionReturn).join(CorrectionDraft,CorrectionDraft.id==CorrectionReturn.correction_id).where(CorrectionDraft.submission_id==s.id).order_by(CorrectionReturn.number)))
            submissions.append(dict(id=s.id,number=s.number,returns=[dict(id=x.id,number=x.number) for x in returns]))
        result.append(dict(id=r.id,title=v.document['title'],student=db.get(User,r.student_id).name,type=v.details.get('workType','HOMEWORK'),version=v.number,submissions=submissions))
    return result

@router.post('/parent-sharing/preview')
def preview(body:Selection,user:User=Depends(teacher),db:Session=Depends(get_db)):
    content,_=projected(db,body,user.id)
    return dict(content=content,preview_hash=hw.fingerprint(content))

def summary(row):
    return dict(id=row.id,title=row.snapshot['title'],student=row.snapshot['student'],included=row.snapshot['included'],created_at=utc(row.created_at),expires_at=utc(row.expires_at),status='REVOKED' if row.revoked else 'EXPIRED' if utc(row.expires_at)<=now() else 'ACTIVE')

@router.get('/parent-sharing')
def listing(user:User=Depends(teacher),db:Session=Depends(get_db)):
    return [summary(x) for x in db.scalars(select(ParentShare).where(ParentShare.teacher_id==user.id).order_by(ParentShare.created_at.desc()))]

@router.post('/parent-sharing',status_code=201)
def create(body:Create,user:User=Depends(teacher),db:Session=Depends(get_db)):
    selection=Selection.model_validate(body.model_dump(exclude={'days','preview_hash'}))
    content,v=projected(db,selection,user.id)
    if not secrets.compare_digest(body.preview_hash,hw.fingerprint(content)):hw.fail('The preview changed. Review it again before creating a link.',409)
    token=secrets.token_urlsafe(32)
    row=ParentShare(teacher_id=user.id,assignment_id=body.assignment_id,version_id=v.id,secret_hash=digest(token),selection=selection.model_dump(),snapshot=content,expires_at=now()+timedelta(days=body.days))
    db.add(row);db.commit()
    return {**summary(row),'token':token}

@router.post('/parent-sharing/{id}/revoke')
def revoke(id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    row=db.get(ParentShare,id)
    if not row or row.teacher_id!=user.id:hw.fail('Parent link not found.',404)
    row.revoked=True;db.commit()
    return summary(row)

def usable(db,row):
    owner=db.get(User,row.teacher_id) if row else None
    if not row or row.revoked or utc(row.expires_at)<=now() or not owner or not owner.active:
        hw.fail('This parent link is unavailable, expired or revoked. Please contact the teacher.',410)
    return row

@router.post('/parent-portal/open')
def open_link(body:Redeem,request:Request,response:Response,db:Session=Depends(get_db)):
    rate_limit(db,'parent-open:'+(request.client.host if request.client else 'unknown'),60)
    row=usable(db,db.scalar(select(ParentShare).where(ParentShare.secret_hash==digest(body.token))))
    old=db.scalar(select(ParentSession).where(ParentSession.token_hash==digest(request.cookies.get(COOKIE,''))))
    if old:db.delete(old)
    token=secrets.token_urlsafe(32);db.add(ParentSession(share_id=row.id,token_hash=digest(token)));db.commit()
    response.set_cookie(COOKIE,token,httponly=True,secure=settings.cookie_secure,samesite='strict',path=COOKIE_PATH,max_age=max(1,int((utc(row.expires_at)-now()).total_seconds())))
    return {'opened':True}

def current(request,db):
    session=db.scalar(select(ParentSession).where(ParentSession.token_hash==digest(request.cookies.get(COOKIE,''))))
    return usable(db,db.get(ParentShare,session.share_id) if session else None)

@router.get('/parent-portal/view')
def view(request:Request,db:Session=Depends(get_db)):
    row=current(request,db)
    return {**row.snapshot,'expires_at':utc(row.expires_at),'share_id':row.id}

@router.get('/parent-portal/{share_id}/assets/{id}')
def asset(share_id:str,id:str,request:Request,db:Session=Depends(get_db)):
    row=current(request,db)
    if row.id!=share_id:hw.fail('This parent session changed. Reopen the intended link.',410)
    ids={o['assetId'] for p in row.snapshot.get('document',{}).get('pages',[]) for o in p['objects'] if o['type']=='image'}
    if id not in ids:hw.fail('Image not shared.',404)
    image=db.get(HomeworkImage,(row.version_id,id))
    if not image:hw.fail('Image not found.',404)
    return Response(image.png,media_type='image/png')

@router.post('/parent-portal/close')
def close(request:Request,response:Response,db:Session=Depends(get_db)):
    session=db.scalar(select(ParentSession).where(ParentSession.token_hash==digest(request.cookies.get(COOKIE,''))))
    if session:db.delete(session);db.commit()
    response.delete_cookie(COOKIE,path=COOKIE_PATH)
    return {'closed':True}
