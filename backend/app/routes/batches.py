from fastapi import APIRouter,Depends
from pydantic import Field,StrictInt
from sqlalchemy import select,delete
from sqlalchemy.orm import Session
from ..db import get_db
from ..security import teacher
from ..models import User,BatchMember,Classroom,ClassroomMember
from ..schemas import BatchCreate,ClassCreate
from ..batch_models import BatchPublication
from ..homework_models import HomeworkVersion,HomeworkRecipient
from .. import batch_service as svc,test_timing,homework_service as hw
from .join import utc

router=APIRouter(tags=['Batch management'])
class Edit(BatchCreate):expected_revision:StrictInt=Field(ge=0)
class BatchClass(ClassCreate):
    expected_revision:StrictInt=Field(ge=0)

@router.get('/batches/{id}')
def read(id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    return svc.summary(db,svc.owned(db,id,user.id))

@router.put('/batches/{id}')
def edit(id:str,body:Edit,user:User=Depends(teacher),db:Session=Depends(get_db)):
    row=svc.owned(db,id,user.id,True);svc.check_revision(row,body.expected_revision);svc.valid_students(db,user.id,body.student_ids)
    db.execute(delete(BatchMember).where(BatchMember.batch_id==id));db.add_all([BatchMember(batch_id=id,student_id=x) for x in body.student_ids]);row.name=body.name;row.revision+=1;db.commit()
    return svc.summary(db,row)

@router.post('/batches/{id}/classes',status_code=201)
def create_class(id:str,body:BatchClass,user:User=Depends(teacher),db:Session=Depends(get_db)):
    row=svc.owned(db,id,user.id,True);svc.check_revision(row,body.expected_revision)
    ids=[x.id for x in svc.members(db,id)]
    if body.kind!='BATCH' or body.batch_id!=id or set(body.student_ids)!=set(ids):hw.fail('Review every student in this batch before creating its class.',409)
    svc.valid_students(db,user.id,ids)
    classroom=Classroom(teacher_id=user.id,**body.model_dump(exclude={'student_ids','expected_revision'}));db.add(classroom);db.flush()
    db.add_all([ClassroomMember(classroom_id=classroom.id,student_id=x) for x in ids]);db.commit()
    return {'id':classroom.id}

@router.get('/batches/{id}/work')
def work(id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    svc.owned(db,id,user.id);test_timing.expire_teacher(db,user.id)
    rows=db.execute(select(BatchPublication,HomeworkVersion).join(HomeworkVersion,HomeworkVersion.id==BatchPublication.version_id).where(BatchPublication.batch_id==id).order_by(HomeworkVersion.created_at.desc())).all()
    result=[]
    for source,v in rows:
        recipients=list(db.scalars(select(HomeworkRecipient).where(HomeworkRecipient.version_id==v.id)))
        result.append(dict(version_id=v.id,title=v.document['title'],type=v.details.get('workType','HOMEWORK'),version=v.number,batch_name=source.batch_name,batch_revision=source.batch_revision,assigned_at=utc(v.created_at),students=[dict(id=r.student_id,name=db.get(User,r.student_id).name,status=r.status,submissions=len(hw.submission_list(db,r.id))) for r in recipients]))
    return result
