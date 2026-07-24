from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String,Boolean,DateTime,func,ForeignKey
from sqlalchemy.orm import mapped_column,Mapped
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class LoginHistory(Base):
    __tablename__="login_history"

    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID | None]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    email_attempted:Mapped[str]=mapped_column(String(320),nullable=False,index=True)
    success:Mapped[bool]=mapped_column(Boolean,nullable=False)
    ip_address:Mapped[str | None]=mapped_column(String(100),nullable=True)
    user_agent:Mapped[str | None]=mapped_column(String(500),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    