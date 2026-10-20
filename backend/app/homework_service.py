import base64
import copy
import hashlib
import io
import json
import warnings
from datetime import date
from uuid import uuid4
from PIL import Image, ImageDraw
from fastapi import HTTPException
from sqlalchemy import select,update,func
from .models import User,StudentProfile,now
from .homework_models import HomeworkDraft,HomeworkVersion,HomeworkImage,HomeworkRecipient,HomeworkSubmission,HomeworkEvent
from .document_schema import validate_document,validate_object,ident
from .routes.join import utc

def fail(message,status=400):raise HTTPException(status,message)
def fingerprint(value):
    try:return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    except (ValueError,TypeError):fail('Invalid homework data.',422)
def owned_draft(db,user,id):
    draft=db.scalar(select(HomeworkDraft).where(HomeworkDraft.id==id,HomeworkDraft.teacher_id==user.id))
    if not draft:fail('Homework draft not found.',404)
    return draft
def student(db,teacher_id,id):
    found=db.scalar(select(User).join(StudentProfile,StudentProfile.user_id==User.id).where(User.id==id,User.active.is_(True),User.role=='STUDENT',StudentProfile.teacher_id==teacher_id))
    if not found:fail('Choose an active student from your roster.')
    return found
def validate_package(document,metadata,assets,work_type="HOMEWORK"):
    try:
        doc=validate_document(copy.deepcopy(document))
        if not isinstance(metadata,dict) or set(metadata)-({'instructions','dueDate','recipientType','recipientId','recipientName','timeLimitMinutes'} if work_type=='TEST' else {'instructions','dueDate','recipientType','recipientId','recipientName'}):raise ValueError()
        minutes=metadata.get('timeLimitMinutes',0)
        if type(minutes) is not int or not 0<=minutes<=1440:raise ValueError()
        instructions=metadata.get('instructions','');due=metadata.get('dueDate','')
        if not isinstance(instructions,str) or len(instructions)>10000 or not isinstance(due,str) or (due and date.fromisoformat(due).isoformat()!=due):raise ValueError()
        intended=metadata.get('recipientName','')
        if not isinstance(intended,str) or len(intended)>200:raise ValueError()
        if not isinstance(assets,dict) or len(assets)>1000:raise ValueError()
        required={o['assetId'] for p in doc['pages'] for o in p['objects'] if o['type']=='image'}
        if set(assets)!=required:raise ValueError()
        normalized={}
        for aid,encoded in assets.items():
            if not ident(aid) or not isinstance(encoded,str):raise ValueError()
            raw=base64.b64decode(encoded,validate=True)
            if len(raw)>40*1024*1024:raise ValueError()
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                image=Image.open(io.BytesIO(raw),formats=['PNG'])
                if image.width*image.height>32_000_000 or getattr(image,'n_frames',1)!=1:raise ValueError()
                image.load();image=image.convert('RGBA');image.info.clear();out=io.BytesIO();image.save(out,format='PNG')
            normalized[aid]=base64.b64encode(out.getvalue()).decode()
        if sum(len(x) for x in normalized.values())>64*1024*1024:raise ValueError()
        return doc,{'instructions':instructions,'dueDate':due,'recipientName':intended,**({'timeLimitMinutes':minutes} if work_type=='TEST' else {})},normalized
    except (ValueError,TypeError,KeyError,OSError,OverflowError,Image.DecompressionBombError,Image.DecompressionBombWarning):fail('Invalid homework package. Use a supported assignment file up to 64 MB, with PNG images up to 32 million pixels.',422)

def published(db,draft,key,signature,number):
    doc=copy.deepcopy(draft.document)
    doc['id']=str(uuid4());doc['revision']=0
    for field in ['student','batch','topic','subject']:doc.pop(field,None)
    version=HomeworkVersion(draft_id=draft.id,number=number,publish_key=key,fingerprint=signature,document={},details={**{k:draft.details.get(k,'') for k in ['instructions','dueDate']},'workType':draft.work_type,**({'timeLimitMinutes':draft.details.get('timeLimitMinutes',0)} if draft.work_type=='TEST' else {})});db.add(version);db.flush()
    for p in doc['pages']:
        for obj in p['objects']:
            if obj['type']!='image':continue
            image=Image.open(io.BytesIO(base64.b64decode(draft.assets[obj['assetId']]))).convert('RGBA');draw=ImageDraw.Draw(image)
            for mask in obj.get('masks',[]):draw.polygon([(x*image.width,y*image.height) for x,y in mask['points']],fill=(0,0,0,0))
            image.paste((0,0,0,0),mask=image.getchannel('A').point(lambda a:255 if a==0 else 0));out=io.BytesIO();image.save(out,format='PNG');aid=str(uuid4());db.add(HomeworkImage(version_id=version.id,id=aid,png=out.getvalue()));obj['assetId']=aid;obj.pop('masks',None)
    version.document=doc;return version

def assignment(db,id,uid=None,teacher_id=None,lock=False):
    if lock:
        db.execute(update(HomeworkRecipient).where(HomeworkRecipient.id==id).values(revision=HomeworkRecipient.revision).execution_options(synchronize_session=False));db.expire_all()
    row=db.get(HomeworkRecipient,id);v=db.get(HomeworkVersion,row.version_id) if row else None;d=db.get(HomeworkDraft,v.draft_id) if v else None
    if not row or (uid and row.student_id!=uid) or (teacher_id and d.teacher_id!=teacher_id):fail('Homework assignment not found.',404)
    return row,v,d
def answers_valid(value,version):
    try:
        if not isinstance(value,dict) or set(value)!={'pages'} or not isinstance(value['pages'],list):raise ValueError()
        if [p.get('id') for p in value['pages']]!=[p['id'] for p in version.document['pages']]:raise ValueError()
        ids={o['id'] for p in version.document['pages'] for o in p['objects']}
        for p in value['pages']:
            if set(p)!={'id','objects'} or not isinstance(p['objects'],list):raise ValueError()
            for obj in p['objects']:
                validate_object(obj)
                if obj['type'] in ['image','grid'] or obj['id'] in ids:raise ValueError()
                ids.add(obj['id'])
        if len(json.dumps(value,allow_nan=False).encode())>16*1024*1024:raise ValueError()
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):fail('Invalid answer layer. The assigned template cannot be edited.',422)
    return copy.deepcopy(value)
def event(db,row,action):db.add(HomeworkEvent(assignment_id=row.id,action=action,revision=row.revision))
def summary(row,v,d):return dict(id=row.id,homework_id=d.id,version=v.number,workType=v.details.get('workType','HOMEWORK'),title=v.document['title'],creationDate=v.document['creationDate'],dueDate=v.details.get('dueDate',''),status=row.status,revision=row.revision,resubmit=row.resubmit)
def submission_list(db,id):
    return [dict(id=s.id,number=s.number,submitted_at=utc(s.created_at),draft_revision=s.draft_revision) for s in db.scalars(select(HomeworkSubmission).where(HomeworkSubmission.assignment_id==id).order_by(HomeworkSubmission.number))]
