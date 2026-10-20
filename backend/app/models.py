"""Phase 1 domain schema. Later-phase tables are reserved, without public APIs."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.now(timezone.utc)


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class User(Record, Base):
    __tablename__ = 'users'
    __table_args__ = (CheckConstraint("role IN ('TEACHER','STUDENT')", name='user_role'),)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TeacherProfile(Record, Base):
    __tablename__ = 'teacher_profiles'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True)


class StudentProfile(Record, Base):
    __tablename__ = 'student_profiles'
    __table_args__ = (CheckConstraint('grade BETWEEN 6 AND 10', name='student_grade'),)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    legacy_grade: Mapped[int] = mapped_column('grade', Integer, default=8)
    grade: Mapped[str] = mapped_column('grade_label', String(100), default='')
    subject: Mapped[str] = mapped_column(String(80), default='Mathematics')


class AuthSession(Record, Base):
    __tablename__ = 'auth_sessions'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LoginAttempt(Record, Base):
    __tablename__ = 'login_attempts'
    key_hash: Mapped[str] = mapped_column(String(64), index=True)


class Batch(Record, Base):
    __tablename__ = 'batches'
    revision: Mapped[int] = mapped_column(Integer, default=0)
    teacher_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))


class BatchMember(Record, Base):
    __tablename__ = 'batch_members'
    __table_args__ = (UniqueConstraint('batch_id', 'student_id'),)
    batch_id: Mapped[str] = mapped_column(ForeignKey('batches.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)


class Classroom(Record, Base):
    __tablename__ = 'classrooms'
    __table_args__ = (CheckConstraint("kind IN ('ONE_TO_ONE','BATCH')", name='class_kind'), CheckConstraint('grade BETWEEN 6 AND 10', name='class_grade'))
    teacher_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey('batches.id'))
    name: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(80))
    legacy_grade: Mapped[int] = mapped_column('grade', Integer, default=8)
    grade: Mapped[str] = mapped_column('grade_label', String(100), default='')
    kind: Mapped[str] = mapped_column(String(20))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClassroomMember(Record, Base):
    __tablename__ = 'classroom_members'
    __table_args__ = (UniqueConstraint('classroom_id', 'student_id'),)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)


class Homework(Record, Base):
    __tablename__ = 'homework'
    teacher_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    grade: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default='')
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pages: Mapped[list] = mapped_column(JSON, default=list)


class HomeworkAssignment(Record, Base):
    __tablename__ = 'homework_assignments'
    __table_args__ = (UniqueConstraint('homework_id', 'student_id'), CheckConstraint("status IN ('NEW','IN_PROGRESS','SUBMITTED','REVIEWED')", name='homework_status'))
    homework_id: Mapped[str] = mapped_column(ForeignKey('homework.id'), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='NEW')


class HomeworkSubmission(Record, Base):
    __tablename__ = 'homework_submissions'
    __table_args__ = (UniqueConstraint('assignment_id', 'version'),)
    assignment_id: Mapped[str] = mapped_column(ForeignKey('homework_assignments.id'), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    feedback: Mapped[str] = mapped_column(Text, default='')
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Lesson(Record, Base):
    __tablename__ = 'lessons'
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    participants: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LessonPage(Record, Base):
    __tablename__ = 'lesson_pages'
    __table_args__ = (UniqueConstraint('lesson_id', 'position'),)
    lesson_id: Mapped[str] = mapped_column(ForeignKey('lessons.id', ondelete='CASCADE'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer, default=900)
    height: Mapped[int] = mapped_column(Integer, default=1273)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    thumbnail_key: Mapped[str | None] = mapped_column(String(255))


class WhiteboardObject(Record, Base):
    __tablename__ = 'whiteboard_objects'
    page_id: Mapped[str] = mapped_column(ForeignKey('lesson_pages.id', ondelete='CASCADE'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    type: Mapped[str] = mapped_column(String(40))
    x: Mapped[float]
    y: Mapped[float]
    width: Mapped[float]
    height: Mapped[float]
    rotation: Mapped[float] = mapped_column(default=0)
    z_index: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)


class Attachment(Record, Base):
    __tablename__ = 'attachments'
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    homework_id: Mapped[str | None] = mapped_column(ForeignKey('homework.id'))
    submission_id: Mapped[str | None] = mapped_column(ForeignKey('homework_submissions.id'))
    lesson_id: Mapped[str | None] = mapped_column(ForeignKey('lessons.id'))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)


class PrivateDocument(Record, Base):
    __tablename__ = 'private_documents'
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    body: Mapped[dict] = mapped_column(JSON)


class PrivateAsset(Record, Base):
    __tablename__ = 'private_assets'
    document_id: Mapped[str] = mapped_column(ForeignKey('private_documents.id', ondelete='CASCADE'), index=True)
    png: Mapped[bytes] = mapped_column(LargeBinary)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)


class ClassAccess(Base):
    __tablename__ = 'class_access'
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), primary_key=True)
    generation: Mapped[int] = mapped_column(Integer, default=1)
    open: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JoinInvitation(Record, Base):
    __tablename__ = 'join_invitations'
    classroom_id: Mapped[str] = mapped_column(ForeignKey('class_access.classroom_id'), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class JoinSession(Record, Base):
    __tablename__ = 'join_sessions'
    invitation_id: Mapped[str] = mapped_column(ForeignKey('join_invitations.id'), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JoinRate(Base):
    __tablename__ = 'join_rates'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    bucket: Mapped[int] = mapped_column(Integer, index=True)
    attempts: Mapped[int] = mapped_column(Integer)
