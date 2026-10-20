from datetime import datetime
from sqlalchemy import String, JSON, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import Record


class ParentShare(Record, Base):
    __tablename__ = 'parent_shares'
    teacher_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    assignment_id: Mapped[str] = mapped_column(ForeignKey('hw_recipients.id'))
    version_id: Mapped[str] = mapped_column(ForeignKey('hw_versions.id'))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    selection: Mapped[dict] = mapped_column(JSON)
    snapshot: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class ParentSession(Record, Base):
    __tablename__ = 'parent_view_sessions'
    share_id: Mapped[str] = mapped_column(ForeignKey('parent_shares.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
