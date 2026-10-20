import copy
import io
from types import SimpleNamespace
from uuid import uuid4
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from PIL import Image
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, PrivateDocument, PrivateAsset, ClassAccess, Classroom, ClassroomMember, now
from ..homework_models import HomeworkSubmission, HomeworkRecipient, HomeworkVersion, HomeworkDraft, HomeworkImage
from ..correction_models import CorrectionDraft, CorrectionSave, CorrectionReturn, ClassroomCopy, CopyPublication
from ..security import teacher
from .. import homework_service as hw
from ..document_schema import validate_document
from .homework import actor
from .join import utc, owned
from .. import live_service, test_timing
from ..live_models import LiveBoard

router = APIRouter(tags=['Student work and corrections'])

class Input(BaseModel):model_config = ConfigDict(extra='forbid')
class Save(Input):
    expected_revision: StrictInt = Field(ge=0)
    key: str = Field(pattern=r'^[a-zA-Z0-9-]{1,80}$')
    body: dict
class Return(Input):
    expected_revision: StrictInt = Field(ge=0)
    key: str = Field(pattern=r'^[a-zA-Z0-9-]{1,80}$')
class Copy(Input):
    key: str = Field(pattern=r'^[a-zA-Z0-9-]{1,80}$')
    title: str = Field(min_length=1,max_length=200)
    correction_revision: StrictInt | None = Field(default=None,ge=0)

class Share(Input):
    class_id: str
    generation: StrictInt
    document_revision: StrictInt = Field(ge=0)
    audience_ids: list[str]

def owned_copy(db,id,docid,user):
    submission(db,id,user.id)
    source=db.scalar(select(ClassroomCopy).where(ClassroomCopy.submission_id==id,ClassroomCopy.document_id==docid))
    doc=db.get(PrivateDocument,docid)
    if not source or not doc or doc.owner_id!=user.id:hw.fail('Classroom copy not found.',404)
    return doc

def audience(db,cid,user):
    classroom=owned(db,user,cid)
    members=list(db.scalars(select(User).join(ClassroomMember,ClassroomMember.student_id==User.id).where(ClassroomMember.classroom_id==cid).order_by(User.id)))
    return classroom,members

@router.get('/student-work/{id}/copies/{docid}/audience/{cid}')
def copy_audience(id:str,docid:str,cid:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    doc=owned_copy(db,id,docid,user);classroom,members=audience(db,cid,user);room=db.get(ClassAccess,cid)
    board=db.scalar(select(LiveBoard).where(LiveBoard.classroom_id==cid,LiveBoard.generation==room.generation)) if room else None
    return dict(class_id=cid,name=classroom.name,students=[dict(id=x.id,name=x.name) for x in members],generation=room.generation if room else 0,open=bool(room and room.open and utc(room.expires_at)>now()),has_board=bool(board),document_revision=doc.revision)

@router.post('/student-work/{id}/copies/{docid}/publish')
def publish_copy(id:str,docid:str,body:Share,request:Request,user:User=Depends(teacher),db:Session=Depends(get_db)):
    doc=owned_copy(db,id,docid,user)
    live_actor=live_service.access(request,db,body.class_id,request.headers.get('X-CSRF-Token',''))
    db.execute(update(ClassAccess).where(ClassAccess.classroom_id==body.class_id).values(generation=ClassAccess.generation));db.expire_all()
    db.execute(update(PrivateDocument).where(PrivateDocument.id==docid).values(revision=PrivateDocument.revision));db.expire_all()
    db.scalar(select(Classroom).where(Classroom.id==body.class_id).with_for_update())
    room=db.get(ClassAccess,body.class_id);classroom,members=audience(db,body.class_id,user)
    if not room.open or utc(room.expires_at)<=now() or room.generation!=body.generation:hw.fail('Classroom access changed. Review the audience again.',409)
    signature=hw.fingerprint(body.model_dump());previous=db.get(CopyPublication,(body.class_id,body.generation))
    source=db.scalar(select(ClassroomCopy).where(ClassroomCopy.document_id==docid))
    if previous:
        if previous.copy_id!=source.id or previous.fingerprint!=signature:hw.fail('A different copy has already been published to this session.',409)
        return live_service.snapshot(db.get(LiveBoard,previous.board_id),live_actor)
    if room.generation!=body.generation or sorted(body.audience_ids)!=sorted(x.id for x in members) or doc.revision!=body.document_revision:hw.fail('The copy or audience changed. Review the audience again.',409)
    if db.scalar(select(LiveBoard).where(LiveBoard.classroom_id==body.class_id,LiveBoard.generation==room.generation)):hw.fail('This session already has a live board. Use the copy in a new session; existing live work is preserved.',409)
    class Transaction:
        def __getattr__(self,key):return getattr(db,key)
        def commit(self):db.flush()
    result=live_service.publish(Transaction(),body.class_id,live_actor,docid)
    db.add(CopyPublication(class_id=body.class_id,generation=body.generation,copy_id=source.id,board_id=result['board_id'],fingerprint=signature));db.commit()
    return result

def submission(db,id,teacher_id=None,student_id=None,lock=False):
    s=db.get(HomeworkSubmission,id)
    if not s:hw.fail('Submission not found.',404)
    r,v,d=hw.assignment(db,s.assignment_id,uid=student_id,teacher_id=teacher_id,lock=lock)
    return s,r,v,d

def original(v,s):
    doc=copy.deepcopy(v.document)
    bypage={p['id']:p['objects'] for p in s.answers['pages']}
    for p in doc['pages']:p['objects'].extend(copy.deepcopy(bypage[p['id']]))
    return doc

def empty(v):return {'pages':[{'id':p['id'],'objects':[]} for p in v.document['pages']],'comments':'','marks':''}
def correction(db,s,v):
    c=db.scalar(select(CorrectionDraft).where(CorrectionDraft.submission_id==s.id))
    if not c:
        c=CorrectionDraft(submission_id=s.id,revision=0,body=empty(v));db.add(c);db.flush()
    return c

def validate(body,v,s):
    if set(body)!={'pages','comments','marks'} or not isinstance(body['comments'],str) or len(body['comments'])>20000 or not isinstance(body['marks'],str) or len(body['marks'])>200:hw.fail('Invalid correction comments or marks.',422)
    hw.answers_valid({'pages':body['pages']},SimpleNamespace(document=original(v,s)))
    return copy.deepcopy(body)

def returned(db,c):
    return [] if not c else [dict(id=x.id,number=x.number,draft_revision=x.draft_revision,returned_at=utc(x.created_at)) for x in db.scalars(select(CorrectionReturn).where(CorrectionReturn.correction_id==c.id).order_by(CorrectionReturn.number))]

def info(s,r,v,d,db):
    c=db.scalar(select(CorrectionDraft).where(CorrectionDraft.submission_id==s.id))
    returns=returned(db,c)
    state='SUBMITTED' if not c or not c.revision else 'CORRECTION_DRAFT'
    if returns and returns[-1]['draft_revision']==c.revision:state='RETURNED'
    return dict(id=s.id,assignment_id=r.id,title=v.document['title'],creationDate=v.document['creationDate'],student_id=r.student_id,student=db.get(User,r.student_id).name,type=v.details.get('workType','HOMEWORK'),submission_number=s.number,submitted_at=utc(s.created_at),assignment_version=v.number,status=state,returns=returns)

@router.get('/student-work')
def listing(user:User=Depends(teacher),db:Session=Depends(get_db)):
    test_timing.expire_teacher(db,user.id)
    rows=db.execute(select(HomeworkSubmission,HomeworkRecipient,HomeworkVersion,HomeworkDraft).join(HomeworkRecipient,HomeworkRecipient.id==HomeworkSubmission.assignment_id).join(HomeworkVersion,HomeworkVersion.id==HomeworkRecipient.version_id).join(HomeworkDraft,HomeworkDraft.id==HomeworkVersion.draft_id).where(HomeworkDraft.teacher_id==user.id).order_by(HomeworkSubmission.created_at.desc())).all()
    return [info(s,r,v,d,db) for s,r,v,d in rows]

@router.get('/student-work/{id}')
def read(id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    s,r,v,d=submission(db,id,user.id)
    c=db.scalar(select(CorrectionDraft).where(CorrectionDraft.submission_id==id))
    copies=list(db.scalars(select(ClassroomCopy).where(ClassroomCopy.submission_id==id)))
    return {**info(s,r,v,d,db),'document':original(v,s),'revision':c.revision if c else 0,'body':c.body if c else empty(v),'copies':[dict(id=x.document_id,correction_revision=x.correction_revision,created_at=utc(x.created_at)) for x in copies]}

@router.put('/student-work/{id}/correction')
def save(id:str,body:Save,user:User=Depends(teacher),db:Session=Depends(get_db)):
    s,r,v,d=submission(db,id,user.id,lock=True);c=correction(db,s,v)
    signature=hw.fingerprint(body.model_dump(exclude={'key'}));prior=db.get(CorrectionSave,(c.id,body.key))
    if prior:
        if prior.fingerprint!=signature:hw.fail('Save key was reused for different corrections.',409)
        return {'revision':prior.revision}
    if c.revision!=body.expected_revision:hw.fail('A newer correction draft exists. Download your recovery copy before reopening.',409)
    c.body=validate(body.body,v,s);c.revision+=1;db.add(CorrectionSave(correction_id=c.id,key=body.key,fingerprint=signature,revision=c.revision));db.commit()
    return {'revision':c.revision}

@router.post('/student-work/{id}/return')
def return_work(id:str,body:Return,user:User=Depends(teacher),db:Session=Depends(get_db)):
    s,r,v,d=submission(db,id,user.id,lock=True);c=correction(db,s,v)
    prior=db.scalar(select(CorrectionReturn).where(CorrectionReturn.correction_id==c.id,CorrectionReturn.key==body.key))
    if prior:
        if prior.draft_revision!=body.expected_revision:hw.fail('Return key was reused for different work.',409)
        return {'id':prior.id,'number':prior.number,'returned_at':utc(prior.created_at)}
    if c.revision!=body.expected_revision:hw.fail('Save the current correction before returning it.',409)
    # Repeated explicit returns of the same saved revision are also harmless.
    prior=db.scalar(select(CorrectionReturn).where(CorrectionReturn.correction_id==c.id,CorrectionReturn.draft_revision==c.revision))
    if prior:return {'id':prior.id,'number':prior.number,'returned_at':utc(prior.created_at)}
    number=(db.scalar(select(func.max(CorrectionReturn.number)).where(CorrectionReturn.correction_id==c.id)) or 0)+1
    result=CorrectionReturn(correction_id=c.id,number=number,key=body.key,draft_revision=c.revision,body=copy.deepcopy(c.body));db.add(result);db.commit()
    return {'id':result.id,'number':number,'returned_at':utc(result.created_at)}

@router.get('/student-work/{id}/returns/{rid}')
def teacher_return(id:str,rid:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    submission(db,id,user.id);return return_body(db,id,rid)

def return_body(db,id,rid):
    result=db.scalar(select(CorrectionReturn).join(CorrectionDraft,CorrectionDraft.id==CorrectionReturn.correction_id).where(CorrectionDraft.submission_id==id,CorrectionReturn.id==rid))
    if not result:hw.fail('Returned correction not found.',404)
    return dict(id=result.id,number=result.number,returned_at=utc(result.created_at),body=result.body)

@router.get('/homework-portal/assignments/{aid}/corrections')
def student_returns(aid:str,request:Request,db:Session=Depends(get_db)):
    a=actor(request,db);hw.assignment(db,aid,uid=a['uid'],teacher_id=a['teacher_id'])
    rows=db.execute(select(CorrectionReturn,HomeworkSubmission).join(CorrectionDraft,CorrectionDraft.id==CorrectionReturn.correction_id).join(HomeworkSubmission,HomeworkSubmission.id==CorrectionDraft.submission_id).where(HomeworkSubmission.assignment_id==aid).order_by(CorrectionReturn.created_at)).all()
    return [dict(id=x.id,submission_id=s.id,submission_number=s.number,number=x.number,returned_at=utc(x.created_at)) for x,s in rows]

@router.get('/homework-portal/assignments/{aid}/corrections/{rid}')
def student_return(aid:str,rid:str,request:Request,db:Session=Depends(get_db)):
    a=actor(request,db);r,v,d=hw.assignment(db,aid,uid=a['uid'],teacher_id=a['teacher_id'])
    row=db.execute(select(CorrectionReturn,HomeworkSubmission).join(CorrectionDraft,CorrectionDraft.id==CorrectionReturn.correction_id).join(HomeworkSubmission,HomeworkSubmission.id==CorrectionDraft.submission_id).where(HomeworkSubmission.assignment_id==aid,CorrectionReturn.id==rid)).first()
    if not row:hw.fail('Returned correction not found.',404)
    x,s=row
    return dict(id=x.id,number=x.number,submission_number=s.number,returned_at=utc(x.created_at),document=original(v,s),body=x.body)

@router.post('/student-work/{id}/classroom-copy',status_code=201)
def classroom_copy(id:str,body:Copy,user:User=Depends(teacher),db:Session=Depends(get_db)):
    s,r,v,d=submission(db,id,user.id,lock=True);signature=hw.fingerprint(body.model_dump(exclude={'key'}))
    prior=db.scalar(select(ClassroomCopy).where(ClassroomCopy.submission_id==id,ClassroomCopy.key==body.key))
    if prior:
        if prior.fingerprint!=signature:hw.fail('Copy key was reused for different work.',409)
        return {'id':prior.document_id}
    doc=original(v,s)
    if body.correction_revision is not None:
        c=correction(db,s,v)
        if c.revision!=body.correction_revision:hw.fail('Save and refresh the correction before copying it.',409)
        for p,layer in zip(doc['pages'],c.body['pages']):p['objects'].extend(copy.deepcopy(layer['objects']))
        # Comments/marks stay private unless the teacher intentionally adds them to the copy.
    stamp=now().isoformat();doc.update(id=str(uuid4()),title=body.title.strip() or 'Classroom discussion',revision=0,createdAt=stamp,updatedAt=stamp)
    for field in ['student','batch','topic','subject']:doc.pop(field,None)
    for p in doc['pages']:
        p['id']=str(uuid4())
        for obj in p['objects']:obj['id']=str(uuid4())
    doc['activePageId']=doc['pages'][0]['id']
    row=PrivateDocument(id=doc['id'],owner_id=user.id,title=doc['title'],revision=0,body=copy.deepcopy(doc));db.add(row);db.flush();assets={}
    for p in doc['pages']:
        for obj in p['objects']:
            if obj['type']!='image':continue
            old=obj['assetId']
            if old not in assets:
                image=db.get(HomeworkImage,(v.id,old));im=Image.open(io.BytesIO(image.png));aid=str(uuid4());assets[old]=aid;db.add(PrivateAsset(id=aid,document_id=doc['id'],png=image.png,width=im.width,height=im.height))
            obj['assetId']=assets[old]
    try:validate_document(doc)
    except (ValueError,TypeError,KeyError,OverflowError):hw.fail('This combined classroom copy exceeds the document limits.',422)
    row.body=copy.deepcopy(doc)
    db.add(ClassroomCopy(submission_id=id,document_id=doc['id'],key=body.key,fingerprint=signature,correction_revision=body.correction_revision));db.commit()
    return {'id':doc['id']}
