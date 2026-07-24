from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime,Integer,String,Text,func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped,mapped_column

from app.db.base import Base

class Job(Base):
    __tablename__ = "jobs"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True)
    user_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False,index=True)

    status:Mapped[str]=mapped_column(String(32),nullable=False,default="queued")
    progress:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    input_path:Mapped[str]=mapped_column(String(1024),nullable=False)
    output_path:Mapped[str]=mapped_column(String(1024),nullable=True)
    error_message:Mapped[str | None]=mapped_column(Text,nullable=True)

    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
    