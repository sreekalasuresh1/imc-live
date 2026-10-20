import base64
import io
import secrets
import time
from datetime import timedelta, timezone
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from ..db import get_db
from ..config import settings
from ..models import ClassAccess, JoinInvitation, JoinSession, JoinRate, Classroom, ClassroomMember, StudentProfile, User, now
from ..security import teacher, digest, valid_csrf

router=APIRouter(tags=['Classroom access'])
COOKIE='classroom_join'

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Start(Input):
    minutes: int=Field(default=120,ge=5,le=720,strict=True)

class Issue(Input):
    student_id: str=Field(min_length=1,max_length=80)
    minutes: int=Field(default=30,ge=1,le=120,strict=True)

class Redeem(Input):
    code: str=Field(min_length=1,max_length=80)

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def owned(db,user,class_id):
    row=db.scalar(select(Classroom).where(Classroom.id==class_id,Classroom.teacher_id==user.id))
    if not row: raise HTTPException(404,'Class not found')
    return row

def active(db,class_id):
    row=db.scalar(select(ClassAccess).where(ClassAccess.classroom_id==class_id,ClassAccess.open.is_(True),ClassAccess.expires_at>now()))
    if not row: raise HTTPException(409,'Start classroom access first')
    return row

def member(db,class_id,student_id):
    return db.scalar(select(User).join(ClassroomMember,ClassroomMember.student_id==User.id).join(Classroom,Classroom.id==ClassroomMember.classroom_id).join(StudentProfile,StudentProfile.user_id==User.id).where(Classroom.id==class_id,User.id==student_id,User.active.is_(True),User.role=='STUDENT',StudentProfile.teacher_id==Classroom.teacher_id))

@router.post('/classes/{class_id}/access')
def start(class_id:str,body:Start,user:User=Depends(teacher),db:Session=Depends(get_db)):
    owned(db,user,class_id)
    insert=pg_insert if db.bind.dialect.name=='postgresql' else sqlite_insert
    stamp=now(); expires=stamp+timedelta(minutes=body.minutes)
    statement=insert(ClassAccess).values(classroom_id=class_id,generation=1,open=True,expires_at=expires)
    statement=statement.on_conflict_do_update(index_elements=['classroom_id'],set_={'generation':ClassAccess.generation+1,'open':True,'expires_at':expires},where=(ClassAccess.open.is_(False)) | (ClassAccess.expires_at<=stamp))
    db.execute(statement);db.commit()
    return status(class_id,user,db)

@router.get('/classes/{class_id}/access')
def status(class_id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    owned(db,user,class_id); room=db.get(ClassAccess,class_id)
    opened=bool(room and room.open and utc(room.expires_at)>now())
    invites=[]
    if room:
        for inv in db.scalars(select(JoinInvitation).where(JoinInvitation.classroom_id==class_id,JoinInvitation.generation==room.generation).order_by(JoinInvitation.created_at.desc())):
            invites.append(dict(id=inv.id,student_id=inv.student_id,expires_at=utc(inv.expires_at),consumed=inv.consumed,revoked=inv.revoked))
    return dict(open=opened,expires_at=utc(room.expires_at) if room else None,invitations=invites)

@router.post('/classes/{class_id}/access/end')
def end(class_id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    owned(db,user,class_id);db.execute(update(ClassAccess).where(ClassAccess.classroom_id==class_id).values(open=False));db.commit();return {'ended':True}

@router.post('/classes/{class_id}/invitations',status_code=201)
def issue(class_id:str,body:Issue,request:Request,user:User=Depends(teacher),db:Session=Depends(get_db)):
    owned(db,user,class_id)
    db.execute(update(ClassAccess).where(ClassAccess.classroom_id==class_id).values(generation=ClassAccess.generation))
    room=active(db,class_id)
    if not member(db,class_id,body.student_id): raise HTTPException(400,'Choose an active student enrolled in this class')
    raw=base64.b32encode(secrets.token_bytes(16)).decode().rstrip('=')
    code='-'.join(raw[i:i+4] for i in range(0,len(raw),4))
    expires=min(now()+timedelta(minutes=body.minutes),utc(room.expires_at))
    # Regeneration revokes prior invitations and their live grants for this student.
    db.execute(update(JoinInvitation).where(JoinInvitation.classroom_id==class_id,JoinInvitation.student_id==body.student_id).values(revoked=True))
    inv=JoinInvitation(classroom_id=class_id,generation=room.generation,student_id=body.student_id,secret_hash=digest(raw),expires_at=expires)
    db.add(inv);db.flush()
    origin=request.headers.get('origin')
    if origin not in settings.origins: raise HTTPException(403,'Request origin is not allowed')
    url=origin+'/join#code='+code
    image=qrcode.make(url);output=io.BytesIO();image.save(output,format='PNG')
    db.commit()
    return dict(id=inv.id,code=code,url=url,expires_at=expires,qr='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode())

@router.post('/classes/{class_id}/invitations/{invitation_id}/revoke')
def revoke(class_id:str,invitation_id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    owned(db,user,class_id)
    result=db.execute(update(JoinInvitation).where(JoinInvitation.id==invitation_id,JoinInvitation.classroom_id==class_id).values(revoked=True))
    if not result.rowcount: raise HTTPException(404,'Invitation not found')
    db.commit();return {'revoked':True}

def limit(db,request):
    bucket=int(time.time())//60;key=digest(str(bucket)+':'+(request.client.host if request.client else 'unknown'))
    insert=pg_insert if db.bind.dialect.name=='postgresql' else sqlite_insert
    statement=insert(JoinRate).values(key=key,bucket=bucket,attempts=1)
    count=db.scalar(statement.on_conflict_do_update(index_elements=['key'],set_={'attempts':JoinRate.attempts+1}).returning(JoinRate.attempts))
    db.execute(delete(JoinRate).where(JoinRate.bucket<bucket-1));db.commit()
    if count>30: raise HTTPException(429,'Too many join attempts. Try again in a minute.',headers={'Retry-After':'60'})

def session_state(request,db):
    session=db.scalar(select(JoinSession).where(JoinSession.token_hash==digest(request.cookies.get(COOKIE,'')),JoinSession.expires_at>now()))
    inv=db.get(JoinInvitation,session.invitation_id) if session else None
    room=db.get(ClassAccess,inv.classroom_id) if inv else None
    student=member(db,inv.classroom_id,inv.student_id) if inv else None
    classroom=db.get(Classroom,inv.classroom_id) if inv else None
    owner=db.get(User,classroom.teacher_id) if classroom else None
    if not session or not inv or inv.revoked or not room or not room.open or utc(room.expires_at)<=now() or room.generation!=inv.generation or not student or not owner or not owner.active:
        raise HTTPException(401,'Classroom access has ended. Ask your teacher for a new invitation.')
    return session,dict(classroom_id=classroom.id,classroom=classroom.name,student=student.name,expires_at=utc(session.expires_at),csrf_token=session.csrf_token)

@router.post('/join/redeem')
def redeem(body:Redeem,request:Request,response:Response,db:Session=Depends(get_db)):
    limit(db,request)
    raw=body.code.replace('-','').replace(' ','').upper()
    inv=db.scalar(select(JoinInvitation).where(JoinInvitation.secret_hash==digest(raw),JoinInvitation.revoked.is_(False),JoinInvitation.consumed.is_(False),JoinInvitation.expires_at>now()))
    if inv: db.execute(update(ClassAccess).where(ClassAccess.classroom_id==inv.classroom_id).values(generation=ClassAccess.generation))
    room=db.get(ClassAccess,inv.classroom_id) if inv else None
    student=member(db,inv.classroom_id,inv.student_id) if inv else None
    classroom=db.get(Classroom,inv.classroom_id) if inv else None
    owner=db.get(User,classroom.teacher_id) if classroom else None
    if not inv or not room or not room.open or utc(room.expires_at)<=now() or room.generation!=inv.generation or not student or not owner or not owner.active:
        raise HTTPException(400,'This invitation is invalid, expired, or already used. Ask your teacher for a new one.')
    changed=db.execute(update(JoinInvitation).where(JoinInvitation.id==inv.id,JoinInvitation.consumed.is_(False),JoinInvitation.revoked.is_(False),JoinInvitation.expires_at>now()).values(consumed=True).execution_options(synchronize_session=False))
    if changed.rowcount!=1: db.rollback();raise HTTPException(400,'This invitation is invalid, expired, or already used. Ask your teacher for a new one.')
    token=secrets.token_urlsafe(48);csrf=secrets.token_hex(32)
    old=request.cookies.get(COOKIE)
    if old: db.execute(delete(JoinSession).where(JoinSession.token_hash==digest(old)))
    db.add(JoinSession(invitation_id=inv.id,token_hash=digest(token),csrf_token=csrf,expires_at=room.expires_at));db.commit()
    response.set_cookie(COOKIE,token,httponly=True,secure=settings.cookie_secure,samesite='lax',path='/api/join',max_age=max(1,int((utc(room.expires_at)-now()).total_seconds())))
    return dict(classroom_id=classroom.id,classroom=classroom.name,student=student.name,expires_at=utc(room.expires_at),csrf_token=csrf)

@router.get('/join/session')
def current(request:Request,db:Session=Depends(get_db)):
    return session_state(request,db)[1]

@router.post('/join/leave',status_code=204)
def leave(request:Request,response:Response,db:Session=Depends(get_db)):
    session,_=session_state(request,db)
    if not valid_csrf(request.headers.get('X-CSRF-Token',''),session.csrf_token): raise HTTPException(403,'Invalid security token')
    db.delete(session);db.commit();response.delete_cookie(COOKIE,path='/api/join',secure=settings.cookie_secure,httponly=True,samesite='lax')


