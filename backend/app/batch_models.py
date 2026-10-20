from sqlalchemy import String, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class BatchPublication(Base):
    __tablename__='batch_publications'
    version_id:Mapped[str]=mapped_column(ForeignKey('hw_versions.id'),primary_key=True)
    batch_id:Mapped[str]=mapped_column(ForeignKey('batches.id'),index=True)
    batch_name:Mapped[str]=mapped_column(String(120))
    batch_revision:Mapped[int]=mapped_column(Integer)
    recipients:Mapped[list]=mapped_column(JSON)
