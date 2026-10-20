from sqlalchemy import String, Integer, JSON, ForeignKey, LargeBinary, UniqueConstraint, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .db import Base
from .models import Record

class HomeworkDraft(Record, Base):
    __tablename__='hw_drafts'
    __table_args__=(UniqueConstraint('teacher_id','source_id'),)
    teacher_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    source_id:Mapped[str]=mapped_column(String(80))
    revision:Mapped[int]=mapped_column(Integer,default=0)
    document:Mapped[dict]=mapped_column(JSON)
    details:Mapped[dict]=mapped_column(JSON)
    assets:Mapped[dict]=mapped_column(JSON)
    work_type:Mapped[str]=mapped_column(String(16),default='HOMEWORK')

class HomeworkVersion(Record, Base):
    __tablename__='hw_versions'
    __table_args__=(UniqueConstraint('draft_id','number'),UniqueConstraint('draft_id','publish_key'))
    draft_id:Mapped[str]=mapped_column(ForeignKey('hw_drafts.id'))
    number:Mapped[int]=mapped_column(Integer)
    publish_key:Mapped[str]=mapped_column(String(80))
    fingerprint:Mapped[str]=mapped_column(String(64))
    document:Mapped[dict]=mapped_column(JSON)
    details:Mapped[dict]=mapped_column(JSON)

class HomeworkImage(Base):
    __tablename__='hw_images'
    version_id:Mapped[str]=mapped_column(ForeignKey('hw_versions.id'),primary_key=True)
    id:Mapped[str]=mapped_column(String(80),primary_key=True)
    png:Mapped[bytes]=mapped_column(LargeBinary)

class HomeworkRecipient(Record, Base):
    __tablename__='hw_recipients'
    __table_args__=(UniqueConstraint('version_id','student_id'),)
    version_id:Mapped[str]=mapped_column(ForeignKey('hw_versions.id'))
    student_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    status:Mapped[str]=mapped_column(String(30),default='ASSIGNED')
    resubmit:Mapped[bool]=mapped_column(Boolean,default=False)
    revision:Mapped[int]=mapped_column(Integer,default=0)
    answers:Mapped[dict]=mapped_column(JSON)

class HomeworkSubmission(Record, Base):
    __tablename__='hw_submissions'
    __table_args__=(UniqueConstraint('assignment_id','number'),UniqueConstraint('assignment_id','submit_key'))
    assignment_id:Mapped[str]=mapped_column(ForeignKey('hw_recipients.id'))
    number:Mapped[int]=mapped_column(Integer)
    submit_key:Mapped[str]=mapped_column(String(80))
    draft_revision:Mapped[int]=mapped_column(Integer)
    answers:Mapped[dict]=mapped_column(JSON)

class HomeworkSave(Base):
    __tablename__='hw_saves'
    assignment_id:Mapped[str]=mapped_column(ForeignKey('hw_recipients.id'),primary_key=True)
    save_key:Mapped[str]=mapped_column(String(80),primary_key=True)
    fingerprint:Mapped[str]=mapped_column(String(64))
    revision:Mapped[int]=mapped_column(Integer)

class HomeworkEvent(Record, Base):
    __tablename__='hw_events'
    assignment_id:Mapped[str]=mapped_column(ForeignKey('hw_recipients.id'))
    action:Mapped[str]=mapped_column(String(30))
    revision:Mapped[int]=mapped_column(Integer)

class HomeworkGrant(Record, Base):
    __tablename__='hw_grants'
    teacher_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    student_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    secret_hash:Mapped[str]=mapped_column(String(64),unique=True)
    consumed:Mapped[bool]=mapped_column(Boolean,default=False)
    revoked:Mapped[bool]=mapped_column(Boolean,default=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

class HomeworkPortalSession(Record, Base):
    __tablename__='hw_portal_sessions'
    grant_id:Mapped[str]=mapped_column(ForeignKey('hw_grants.id'),unique=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True)
    csrf_token:Mapped[str]=mapped_column(String(64))
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
