from sqlalchemy import String,Integer
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base

class SecurityRate(Base):
    __tablename__='security_rate_buckets'
    key:Mapped[str]=mapped_column(String(64),primary_key=True)
    bucket:Mapped[int]=mapped_column(Integer,index=True)
    attempts:Mapped[int]=mapped_column(Integer)
