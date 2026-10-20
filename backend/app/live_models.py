from sqlalchemy import String, Integer, JSON, ForeignKey, LargeBinary, UniqueConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import Record

class LiveBoard(Record, Base):
    __tablename__='live_boards'
    __table_args__=(UniqueConstraint('classroom_id','generation'),)
    classroom_id:Mapped[str]=mapped_column(ForeignKey('classrooms.id'))
    generation:Mapped[int]=mapped_column(Integer)
    sequence:Mapped[int]=mapped_column(Integer,default=0)
    document:Mapped[dict]=mapped_column(JSON)
    authors:Mapped[dict]=mapped_column(JSON,default=dict)
    writers:Mapped[list]=mapped_column(JSON,default=list)

class LiveOperation(Base):
    __tablename__='live_operations'
    __table_args__=(UniqueConstraint('board_id','sequence'),)
    board_id:Mapped[str]=mapped_column(ForeignKey('live_boards.id'),primary_key=True)
    operation_id:Mapped[str]=mapped_column(String(80),primary_key=True)
    sequence:Mapped[int]=mapped_column(Integer)
    actor:Mapped[str]=mapped_column(String(64))
    request:Mapped[dict]=mapped_column(JSON)
    event:Mapped[dict]=mapped_column(JSON)

class LiveAsset(Base):
    __tablename__='live_assets'
    board_id:Mapped[str]=mapped_column(ForeignKey('live_boards.id'),primary_key=True)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    png:Mapped[bytes]=mapped_column(LargeBinary)

class LiveTransient(Base):
    __tablename__='live_transients'
    board_id:Mapped[str]=mapped_column(ForeignKey('live_boards.id'),primary_key=True)
    actor:Mapped[str]=mapped_column(String(64),primary_key=True)
    body:Mapped[dict]=mapped_column(JSON)
    expires:Mapped[float]=mapped_column(Float)
