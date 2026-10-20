from fastapi import APIRouter, Depends, HTTPException
import secrets
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Batch, BatchMember, Classroom, ClassroomMember, StudentProfile, User
from ..schemas import BatchCreate, ClassCreate, Roster, StudentCreate
from ..security import authenticated, passwords, public_user, teacher
from .. import batch_service

router = APIRouter(tags=['Teaching'])


def owned_students(db, teacher_id, ids):
    found = set(db.scalars(select(StudentProfile.user_id).where(StudentProfile.teacher_id == teacher_id, StudentProfile.user_id.in_(ids))))
    if found != set(ids):
        raise HTTPException(400, 'Choose students from your own student list')


def class_list(db, user):
    query = select(Classroom).order_by(Classroom.created_at.desc())
    if user.role == 'TEACHER':
        query = query.where(Classroom.teacher_id == user.id)
    else:
        query = query.join(ClassroomMember).where(ClassroomMember.student_id == user.id)
    classes = list(db.scalars(query))
    members = {}
    if classes:
        for class_id, member in db.execute(select(ClassroomMember.classroom_id, User).join(User, User.id == ClassroomMember.student_id).where(ClassroomMember.classroom_id.in_([c.id for c in classes]))):
            # Students see their own enrollment only; no roster information leaks.
            if user.role == 'TEACHER' or member.id == user.id:
                members.setdefault(class_id, []).append({'id': member.id, 'name': member.name})
    return [{'id': c.id, 'name': c.name, 'grade': c.grade, 'subject': c.subject, 'kind': c.kind, 'batch_id': c.batch_id, 'scheduled_at': c.scheduled_at, 'students': members.get(c.id, [])} for c in classes]


@router.get('/students')
def students(user: User = Depends(teacher), db: Session = Depends(get_db)):
    rows = db.execute(select(User, StudentProfile).join(StudentProfile, User.id == StudentProfile.user_id).where(StudentProfile.teacher_id == user.id).order_by(User.name)).all()
    classes = class_list(db, user)
    return [{**public_user(u), 'grade': p.grade, 'subject': p.subject, 'active': u.active, 'last_login_at': u.last_login_at, 'classes': [c['name'] for c in classes if u.id in [s['id'] for s in c['students']]]} for u, p in rows]


@router.post('/students', status_code=201)
def create_student(body: StudentCreate, user: User = Depends(teacher), db: Session = Depends(get_db)):
    student = User(username=body.username or ('pending.' + secrets.token_hex(16)), name=body.name, password_hash=passwords.hash(body.password or secrets.token_urlsafe(64)), role='STUDENT')
    db.add(student)
    try:
        db.flush()
        db.add(StudentProfile(user_id=student.id, teacher_id=user.id, grade=body.grade, subject=body.subject))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'That username is unavailable')
    return public_user(student)


@router.get('/batches')
def batches(user: User = Depends(teacher), db: Session = Depends(get_db)):
    result = []
    for batch in db.scalars(select(Batch).where(Batch.teacher_id == user.id).order_by(Batch.created_at.desc())):
        members = db.scalars(select(User).join(BatchMember, User.id == BatchMember.student_id).where(BatchMember.batch_id == batch.id)).all()
        result.append({'id': batch.id, 'name': batch.name, 'revision': batch.revision, 'students': [{'id': m.id, 'name': m.name, 'active':m.active} for m in members]})
    return result


@router.post('/batches', status_code=201)
def create_batch(body: BatchCreate, user: User = Depends(teacher), db: Session = Depends(get_db)):
    owned_students(db, user.id, body.student_ids)
    batch_service.valid_students(db,user.id,body.student_ids)
    batch = Batch(teacher_id=user.id, name=body.name)
    db.add(batch)
    db.flush()
    db.add_all([BatchMember(batch_id=batch.id, student_id=s) for s in body.student_ids])
    db.commit()
    return {'id': batch.id}


@router.get('/classes')
def classes(user: User = Depends(authenticated), db: Session = Depends(get_db)):
    return class_list(db, user)


@router.post('/classes', status_code=201)
def create_class(body: ClassCreate, user: User = Depends(teacher), db: Session = Depends(get_db)):
    owned_students(db, user.id, body.student_ids)
    if body.batch_id:
        batch = batch_service.owned(db,body.batch_id,user.id,True)
        members = set(db.scalars(select(BatchMember.student_id).where(BatchMember.batch_id == batch.id)))
        if members != set(body.student_ids):
            raise HTTPException(400, 'Choose all students in this batch')
    classroom = Classroom(teacher_id=user.id, **body.model_dump(exclude={'student_ids'}))
    db.add(classroom)
    db.flush()
    db.add_all([ClassroomMember(classroom_id=classroom.id, student_id=s) for s in body.student_ids])
    db.commit()
    return {'id': classroom.id}


@router.put('/classes/{class_id}/members')
def change_members(class_id: str, body: Roster, user: User = Depends(teacher), db: Session = Depends(get_db)):
    classroom = db.scalar(select(Classroom).where(Classroom.id == class_id, Classroom.teacher_id == user.id).with_for_update())
    if not classroom:
        raise HTTPException(404, 'Class not found')
    if classroom.kind == 'ONE_TO_ONE' and len(body.student_ids) != 1:
        raise HTTPException(400, 'A 1-to-1 class must have exactly one student')
    owned_students(db, user.id, body.student_ids)
    db.execute(delete(ClassroomMember).where(ClassroomMember.classroom_id == class_id))
    db.add_all([ClassroomMember(classroom_id=class_id, student_id=s) for s in body.student_ids])
    # The class has its own roster; editing it detaches the original batch template.
    classroom.batch_id = None
    db.commit()
    return {'id': class_id}
