import base64
import copy
import secrets
from typing import Literal
from datetime import timedelta
from fastapi import APIRouter,Depends,Request,Response,HTTPException
from pydantic import BaseModel,ConfigDict,Field,StrictInt
from sqlalchemy import select,update,func,delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..db import get_db
from ..config import settings
from ..security import teacher,authenticated,COOKIE as ACCOUNT_COOKIE,digest,valid_csrf
from ..models import User,AuthSession,StudentProfile,Batch,BatchMember,PrivateDocument,PrivateAsset,now
from ..homework_models import HomeworkDraft,HomeworkVersion,HomeworkRecipient,HomeworkSubmission,HomeworkSave,HomeworkImage,HomeworkEvent,HomeworkGrant,HomeworkPortalSession
from .. import homework_service as svc
from .. import test_timing as timing
from ..test_models import TestClock
from .. import batch_service
from ..batch_models import BatchPublication
from .join import utc,limit

router=APIRouter(tags=['Homework'])
COOKIE='classroom_homework'
class Input(BaseModel):model_config=ConfigDict(extra='forbid')
class Import(Input):
    format:str='my-classroom-assignment-v1'
    document:dict
    metadata:dict
    assets:dict[str,str]
    expected_revision:StrictInt|None=Field(default=None,ge=0)
class Publish(Input):
    expected_revision:StrictInt=Field(ge=0)
    publish_key:str=Field(pattern=r'^[a-zA-Z0-9-]{1,80}$')
    student_ids:list[str]=Field(default_factory=list,max_length=1000)
    batch_id:str|None=None
    batch_revision:StrictInt|None=Field(default=None,ge=0)
class Save(Input):
    expected_revision:StrictInt=Field(ge=0)
    save_key:str=Field(pattern=r'^[a-zA-Z0-9-]{1,80}$')
    answers:dict
class Submit(Input):
    expected_revision:StrictInt=Field(ge=0)
    submit_key:str=Field(pattern=r'^[a-zA-Z0-9-]{1,80}$')
class Grant(Input):
    student_id:str=Field(min_length=1,max_length=80)
    days:StrictInt=Field(default=30,ge=1,le=90)
class Redeem(Input):code:str=Field(min_length=1,max_length=120)

@router.get('/homework/drafts')
def drafts(work_type:Literal['HOMEWORK','TEST']='HOMEWORK',user:User=Depends(teacher),db:Session=Depends(get_db)):
    return [dict(id=d.id,source_id=d.source_id,revision=d.revision,title=d.document['title'],creationDate=d.document['creationDate'],pages=len(d.document['pages']),metadata=d.details,status='DRAFT') for d in db.scalars(select(HomeworkDraft).where(HomeworkDraft.teacher_id==user.id,HomeworkDraft.work_type==work_type).order_by(HomeworkDraft.updated_at.desc()))]

@router.post('/homework/drafts/import',status_code=201)
def import_draft(body:Import,user:User=Depends(teacher),db:Session=Depends(get_db)):
    if body.format not in ['my-classroom-assignment-v1','my-classroom-test-v1']:svc.fail('Choose an assignment file exported by the Windows app.',422)
    work_type='TEST' if body.format=='my-classroom-test-v1' else 'HOMEWORK'
    document,metadata,assets=svc.validate_package(body.document,body.metadata,body.assets,work_type)
    old=db.scalar(select(HomeworkDraft).where(HomeworkDraft.teacher_id==user.id,HomeworkDraft.source_id==document['id']))
    if old:
        if old.work_type!=work_type:svc.fail('A draft cannot change between homework and test.',409)
        if body.expected_revision is None:svc.fail('This homework already has a server draft. Refresh and explicitly update it.',409)
        result=db.execute(update(HomeworkDraft).where(HomeworkDraft.id==old.id,HomeworkDraft.revision==body.expected_revision).values(document=document,details=metadata,assets=assets,revision=body.expected_revision+1,updated_at=now()).execution_options(synchronize_session=False))
        if result.rowcount!=1:db.rollback();svc.fail('The server draft changed. Refresh before updating it.',409)
        id=old.id;revision=body.expected_revision+1
    else:
        if body.expected_revision is not None:svc.fail('The original server draft is unavailable.',409)
        row=HomeworkDraft(work_type=work_type,teacher_id=user.id,source_id=document['id'],document=document,details=metadata,assets=assets,revision=0);db.add(row)
        try:db.flush()
        except IntegrityError:db.rollback();svc.fail('The draft was uploaded in another window. Refresh before retrying.',409)
        id=row.id;revision=0
    try:db.commit()
    except IntegrityError:db.rollback();svc.fail('The draft was uploaded in another window. Refresh before retrying.',409)
    return {'id':id,'revision':revision}

@router.post('/homework/drafts/{id}/publish')
def publish(id:str,body:Publish,user:User=Depends(teacher),db:Session=Depends(get_db)):
    svc.owned_draft(db,user,id)
    db.execute(update(HomeworkDraft).where(HomeworkDraft.id==id).values(revision=HomeworkDraft.revision).execution_options(synchronize_session=False));db.expire_all();draft=svc.owned_draft(db,user,id)
    signature=svc.fingerprint(body.model_dump(exclude={'publish_key'} if body.batch_revision is not None else {'publish_key','batch_revision'}))
    prior=db.scalar(select(HomeworkVersion).where(HomeworkVersion.draft_id==id,HomeworkVersion.publish_key==body.publish_key))
    if prior:
        if prior.fingerprint!=signature:svc.fail('Publish key was reused for different recipients or work.',409)
        return {'version_id':prior.id,'version':prior.number}
    if draft.revision!=body.expected_revision:svc.fail('The draft changed. Refresh before assigning it.',409)
    ids=body.student_ids
    if body.batch_id:
        if ids:svc.fail('Choose individual students or a batch, not both.')
        batch=batch_service.owned(db,body.batch_id,user.id,True)
        batch_service.check_revision(batch,body.batch_revision)
        ids=list(db.scalars(select(BatchMember.student_id).where(BatchMember.batch_id==body.batch_id)))
    if not ids or len(ids)!=len(set(ids)):svc.fail('Choose at least one distinct recipient.')
    for sid in ids:svc.student(db,user.id,sid)
    number=(db.scalar(select(func.max(HomeworkVersion.number)).where(HomeworkVersion.draft_id==id)) or 0)+1
    version=svc.published(db,draft,body.publish_key,signature,number)
    if body.batch_id:db.add(BatchPublication(version_id=version.id,batch_id=batch.id,batch_name=batch.name,batch_revision=batch.revision,recipients=sorted(ids)))
    for sid in ids:
        row=HomeworkRecipient(version_id=version.id,student_id=sid,answers={'pages':[{'id':p['id'],'objects':[]} for p in version.document['pages']]},revision=0,status='ASSIGNED',resubmit=False);db.add(row);db.flush();svc.event(db,row,'ASSIGNED')
        if timing.is_test(version):db.add(TestClock(assignment_id=row.id,attempt=1))
    db.commit();return {'version_id':version.id,'version':number}

@router.get('/homework/assignments')
def teacher_assignments(work_type:Literal['HOMEWORK','TEST']='HOMEWORK',user:User=Depends(teacher),db:Session=Depends(get_db)):
    timing.expire_teacher(db,user.id)
    rows=db.execute(select(HomeworkRecipient,HomeworkVersion,HomeworkDraft,User).join(HomeworkVersion,HomeworkVersion.id==HomeworkRecipient.version_id).join(HomeworkDraft,HomeworkDraft.id==HomeworkVersion.draft_id).join(User,User.id==HomeworkRecipient.student_id).where(HomeworkDraft.teacher_id==user.id,HomeworkDraft.work_type==work_type).order_by(HomeworkRecipient.created_at.desc())).all()
    return [{**svc.summary(r,v,d),'student':s.name,'student_id':s.id,'submissions':svc.submission_list(db,r.id)} for r,v,d,s in rows]

@router.get('/homework/assignments/{id}')
def teacher_read(id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    r,v,d=svc.assignment(db,id,teacher_id=user.id)
    timing.refresh(db,r,v)
    return {**svc.summary(r,v,d),'document':v.document,'metadata':v.details,'submissions':svc.submission_list(db,id),'history':[{'action':e.action,'at':utc(e.created_at),'revision':e.revision} for e in db.scalars(select(HomeworkEvent).where(HomeworkEvent.assignment_id==id).order_by(HomeworkEvent.created_at))]}

@router.post('/homework/assignments/{id}/reopen')
def reopen(id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    r,v,_=svc.assignment(db,id,teacher_id=user.id,lock=True)
    timing.expire(db,r,v)
    if r.status=='SUBMITTED':
        r.resubmit=True;r.status='IN_PROGRESS';timing.reset(db,r,v);svc.event(db,r,'RESUBMISSION_ALLOWED');db.commit()
    return {'status':r.status,'resubmit':r.resubmit}

def actor(request,db):
    token=request.cookies.get(COOKIE)
    if token:
        session=db.scalar(select(HomeworkPortalSession).where(HomeworkPortalSession.token_hash==digest(token),HomeworkPortalSession.expires_at>now()))
        grant=db.get(HomeworkGrant,session.grant_id) if session else None
        if not grant or grant.revoked or utc(grant.expires_at)<=now():svc.fail('Homework access expired or was revoked. Ask your teacher for a new link.',401)
        uid=grant.student_id;teacher_id=grant.teacher_id;csrf=session.csrf_token;expires=session.expires_at
    else:
        session=db.scalar(select(AuthSession).where(AuthSession.token_hash==digest(request.cookies.get(ACCOUNT_COOKIE,'')),AuthSession.expires_at>now()))
        user=db.get(User,session.user_id) if session else None
        profile=db.scalar(select(StudentProfile).where(StudentProfile.user_id==user.id)) if user and user.role=='STUDENT' and user.active else None
        if not profile:svc.fail('Open your homework invitation or sign in with your student account.',401)
        uid=user.id;teacher_id=profile.teacher_id;csrf=session.csrf_token;expires=session.expires_at
    owner=db.get(User,teacher_id)
    if not owner or not owner.active:svc.fail('Homework access is unavailable.',401)
    try:student=svc.student(db,teacher_id,uid)
    except HTTPException:svc.fail('Homework access is unavailable.',401)
    if request.method!='GET' and not valid_csrf(request.headers.get('X-CSRF-Token',''),csrf):svc.fail('Invalid security token.',403)
    return dict(uid=uid,teacher_id=teacher_id,student=student.name,csrf_token=csrf,expires_at=utc(expires))

@router.post('/homework/access')
def issue(body:Grant,request:Request,user:User=Depends(teacher),db:Session=Depends(get_db)):
    svc.student(db,user.id,body.student_id)
    # Serialize regeneration on the student record, including PostgreSQL workers.
    db.execute(update(User).where(User.id==body.student_id).values(active=User.active))
    db.execute(update(HomeworkGrant).where(HomeworkGrant.teacher_id==user.id,HomeworkGrant.student_id==body.student_id).values(revoked=True))
    raw=secrets.token_urlsafe(32);expires=now()+timedelta(days=body.days)
    grant=HomeworkGrant(teacher_id=user.id,student_id=body.student_id,secret_hash=digest(raw),expires_at=expires);db.add(grant);db.commit()
    return {'id':grant.id,'code':raw,'url':request.headers['origin']+'/homework#code='+raw,'expires_at':utc(expires)}

@router.get('/homework/access')
def grants(user:User=Depends(teacher),db:Session=Depends(get_db)):
    return [dict(id=g.id,student_id=g.student_id,consumed=g.consumed,revoked=g.revoked,expires_at=utc(g.expires_at)) for g in db.scalars(select(HomeworkGrant).where(HomeworkGrant.teacher_id==user.id).order_by(HomeworkGrant.created_at.desc()))]

@router.post('/homework/access/{id}/revoke')
def revoke(id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    result=db.execute(update(HomeworkGrant).where(HomeworkGrant.id==id,HomeworkGrant.teacher_id==user.id).values(revoked=True))
    if not result.rowcount:svc.fail('Access link not found.',404)
    db.commit();return {'revoked':True}

@router.post('/homework-portal/redeem')
def redeem(body:Redeem,request:Request,response:Response,db:Session=Depends(get_db)):
    limit(db,request)
    grant=db.scalar(select(HomeworkGrant).where(HomeworkGrant.secret_hash==digest(body.code),HomeworkGrant.revoked.is_(False),HomeworkGrant.consumed.is_(False),HomeworkGrant.expires_at>now()))
    if not grant:svc.fail('This homework link is invalid, expired, or already used.')
    svc.student(db,grant.teacher_id,grant.student_id)
    if not db.get(User,grant.teacher_id).active:svc.fail('Homework access is unavailable.')
    result=db.execute(update(HomeworkGrant).where(HomeworkGrant.id==grant.id,HomeworkGrant.revoked.is_(False),HomeworkGrant.consumed.is_(False),HomeworkGrant.expires_at>now()).values(consumed=True).execution_options(synchronize_session=False))
    if result.rowcount!=1:db.rollback();svc.fail('This homework link is invalid, expired, or already used.')
    old=request.cookies.get(COOKIE)
    if old:db.execute(delete(HomeworkPortalSession).where(HomeworkPortalSession.token_hash==digest(old)))
    token=secrets.token_urlsafe(48);csrf=secrets.token_hex(32);db.add(HomeworkPortalSession(grant_id=grant.id,token_hash=digest(token),csrf_token=csrf,expires_at=grant.expires_at));db.commit()
    response.set_cookie(COOKIE,token,httponly=True,secure=settings.cookie_secure,samesite='lax',path='/api/homework-portal',max_age=max(1,int((utc(grant.expires_at)-now()).total_seconds())))
    return {'uid':grant.student_id,'student':db.get(User,grant.student_id).name,'csrf_token':csrf,'expires_at':utc(grant.expires_at)}

@router.get('/homework-portal/session')
def session(request:Request,db:Session=Depends(get_db)):
    a=actor(request,db);return {k:a[k] for k in ['uid','student','csrf_token','expires_at']}

@router.post('/homework-portal/leave',status_code=204)
def leave(request:Request,response:Response,db:Session=Depends(get_db)):
    actor(request,db);db.execute(delete(HomeworkPortalSession).where(HomeworkPortalSession.token_hash==digest(request.cookies.get(COOKIE,''))));db.commit();response.delete_cookie(COOKIE,path='/api/homework-portal',secure=settings.cookie_secure,httponly=True,samesite='lax')

@router.get('/homework-portal/assignments')
def student_assignments(request:Request,db:Session=Depends(get_db)):
    a=actor(request,db)
    rows=db.execute(select(HomeworkRecipient,HomeworkVersion,HomeworkDraft).join(HomeworkVersion,HomeworkVersion.id==HomeworkRecipient.version_id).join(HomeworkDraft,HomeworkDraft.id==HomeworkVersion.draft_id).where(HomeworkRecipient.student_id==a['uid'],HomeworkDraft.teacher_id==a['teacher_id']).order_by(HomeworkRecipient.created_at.desc())).all()
    return [svc.summary(timing.refresh(db,r,v),v,d) for r,v,d in rows]

def student_assignment(request,db,id,lock=False):
    a=actor(request,db);r,v,d=svc.assignment(db,id,uid=a['uid'],teacher_id=a['teacher_id'],lock=lock)
    if lock:actor(request,db)
    return r,v,d

@router.get('/homework-portal/assignments/{id}')
def student_read(id:str,request:Request,db:Session=Depends(get_db)):
    r,v,d=student_assignment(request,db,id)
    timing.refresh(db,r,v)
    if timing.is_test(v) and not timing.clock(db,r).started_at:
        return {**svc.summary(r,v,d),'timing':timing.info(db,r,v),'metadata':v.details,'submissions':svc.submission_list(db,id)}
    return {**svc.summary(r,v,d),'timing':timing.info(db,r,v),'document':v.document,'metadata':v.details,'answers':r.answers,'submissions':svc.submission_list(db,id)}

@router.put('/homework-portal/assignments/{id}/draft')
def save(id:str,body:Save,request:Request,db:Session=Depends(get_db)):
    r,v,_=student_assignment(request,db,id,True);signature=svc.fingerprint(body.model_dump(exclude={'save_key'}));prior=db.get(HomeworkSave,(id,body.save_key))
    if prior:
        if prior.fingerprint!=signature:svc.fail('Save key was reused with different answers.',409)
        return {'revision':prior.revision}
    timing.require_started(db,r,v);timing.expire(db,r,v)
    if r.status=='SUBMITTED':svc.fail('This submission is locked. Ask your teacher to allow another attempt.',409)
    if r.revision!=body.expected_revision:svc.fail('A newer answer draft exists. Download your local copy before reopening the server copy.',409)
    r.answers=svc.answers_valid(body.answers,v);r.revision+=1;r.status='IN_PROGRESS';svc.event(db,r,'SAVED');db.add(HomeworkSave(assignment_id=id,save_key=body.save_key,fingerprint=signature,revision=r.revision));db.commit();return {'revision':r.revision}

@router.post('/homework-portal/assignments/{id}/submit')
def submit(id:str,body:Submit,request:Request,db:Session=Depends(get_db)):
    r,v,_=student_assignment(request,db,id,True);prior=db.scalar(select(HomeworkSubmission).where(HomeworkSubmission.assignment_id==id,HomeworkSubmission.submit_key==body.submit_key))
    if prior:
        if prior.draft_revision!=body.expected_revision:svc.fail('Submit key was reused for different work.',409)
        return {'id':prior.id,'number':prior.number,'submitted_at':utc(prior.created_at)}
    timing.require_started(db,r,v);timing.expire(db,r,v)
    if timing.is_test(v) and r.status=='SUBMITTED':
        closed=db.get(HomeworkSubmission,timing.clock(db,r).closed_submission_id) if timing.clock(db,r).closed_submission_id else None
        if closed and closed.draft_revision==body.expected_revision:return {'id':closed.id,'number':closed.number,'submitted_at':utc(closed.created_at)}
    if r.status=='SUBMITTED':svc.fail('This work is already submitted. Another attempt needs teacher permission.',409)
    if r.revision!=body.expected_revision:svc.fail('Save the current answers before submitting.',409)
    n=(db.scalar(select(func.max(HomeworkSubmission.number)).where(HomeworkSubmission.assignment_id==id)) or 0)+1
    if n>1 and not r.resubmit:svc.fail('Ask the teacher to allow another attempt.',403)
    s=HomeworkSubmission(assignment_id=id,number=n,submit_key=body.submit_key,draft_revision=r.revision,answers=copy.deepcopy(r.answers));db.add(s);db.flush();timing.finish(db,r,v,s);r.status='SUBMITTED';r.resubmit=False;svc.event(db,r,'SUBMITTED');db.commit();return {'id':s.id,'number':n,'submitted_at':utc(s.created_at)}

@router.get('/homework-portal/assignments/{id}/assets/{asset}')
def student_image(id:str,asset:str,request:Request,db:Session=Depends(get_db)):
    r,v,_=student_assignment(request,db,id)
    if not db.scalar(select(HomeworkSubmission.id).where(HomeworkSubmission.assignment_id==id).limit(1)):timing.require_started(db,r,v)
    return image_response(db,r,asset)

@router.get('/homework/assignments/{id}/assets/{asset}')
def teacher_image(id:str,asset:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    r,_,_=svc.assignment(db,id,teacher_id=user.id);return image_response(db,r,asset)

def image_response(db,r,asset):
    found=db.get(HomeworkImage,(r.version_id,asset))
    if not found:svc.fail('Homework image not found.',404)
    return Response(found.png,media_type='image/png')

def read_submission(db,id,sid):
    s=db.scalar(select(HomeworkSubmission).where(HomeworkSubmission.id==sid,HomeworkSubmission.assignment_id==id))
    if not s:svc.fail('Submission not found.',404)
    return dict(id=s.id,number=s.number,answers=s.answers,submitted_at=utc(s.created_at))

@router.get('/homework/assignments/{id}/submissions/{sid}')
def teacher_submission(id:str,sid:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    svc.assignment(db,id,teacher_id=user.id);return read_submission(db,id,sid)

@router.get('/homework-portal/assignments/{id}/submissions/{sid}')
def student_submission(id:str,sid:str,request:Request,db:Session=Depends(get_db)):
    student_assignment(request,db,id);return read_submission(db,id,sid)

@router.post('/homework-portal/assignments/{id}/start-test')
def start_test(id:str,request:Request,db:Session=Depends(get_db)):
    r,v,d=student_assignment(request,db,id,True);timing.start(db,r,v);timing.expire(db,r,v)
    return {**svc.summary(r,v,d),'timing':timing.info(db,r,v)}

@router.get('/homework-portal/assignments/{id}/test-clock')
def test_clock(id:str,request:Request,db:Session=Depends(get_db)):
    r,v,d=student_assignment(request,db,id,True)
    if not timing.is_test(v):svc.fail('Test not found.',404)
    timing.expire(db,r,v)
    return {**svc.summary(r,v,d),'timing':timing.info(db,r,v),'submissions':svc.submission_list(db,id)}
