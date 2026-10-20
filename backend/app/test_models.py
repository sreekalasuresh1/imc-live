from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base

class TestClock(Base):
    __tablename__='test_attempt_clocks'
    assignment_id:Mapped[str]=mapped_column(ForeignKey('hw_recipients.id'),primary_key=True)
    attempt:Mapped[int]=mapped_column(Integer,default=1)
    started_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    deadline_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    closed_submission_id:Mapped[str|None]=mapped_column(ForeignKey('hw_submissions.id'),nullable=True)
