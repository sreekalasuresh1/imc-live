from sqlalchemy import String, Integer, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import Record


class CorrectionDraft(Record, Base):
    __tablename__ = 'work_corrections'
    submission_id: Mapped[str] = mapped_column(ForeignKey('hw_submissions.id'), unique=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    body: Mapped[dict] = mapped_column(JSON)


class CorrectionSave(Base):
    __tablename__ = 'work_correction_saves'
    correction_id: Mapped[str] = mapped_column(ForeignKey('work_corrections.id'), primary_key=True)
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer)


class CorrectionReturn(Record, Base):
    __tablename__ = 'work_correction_returns'
    __table_args__ = (UniqueConstraint('correction_id', 'number'), UniqueConstraint('correction_id', 'key'))
    correction_id: Mapped[str] = mapped_column(ForeignKey('work_corrections.id'))
    number: Mapped[int] = mapped_column(Integer)
    key: Mapped[str] = mapped_column(String(80))
    draft_revision: Mapped[int] = mapped_column(Integer)
    body: Mapped[dict] = mapped_column(JSON)


class ClassroomCopy(Record, Base):
    __tablename__ = 'work_classroom_copies'
    __table_args__ = (UniqueConstraint('submission_id', 'key'),)
    submission_id: Mapped[str] = mapped_column(ForeignKey('hw_submissions.id'))
    document_id: Mapped[str] = mapped_column(ForeignKey('private_documents.id'), unique=True)
    key: Mapped[str] = mapped_column(String(80))
    fingerprint: Mapped[str] = mapped_column(String(64))
    correction_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CopyPublication(Base):
    __tablename__ = 'work_copy_publications'
    class_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), primary_key=True)
    generation: Mapped[int] = mapped_column(Integer, primary_key=True)
    copy_id: Mapped[str] = mapped_column(ForeignKey('work_classroom_copies.id'))
    board_id: Mapped[str] = mapped_column(ForeignKey('live_boards.id'))
    fingerprint: Mapped[str] = mapped_column(String(64))
