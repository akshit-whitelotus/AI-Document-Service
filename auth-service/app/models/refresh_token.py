from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import ForeignKey,Boolean,DateTime,String,func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column,Mapped,relationship
from app.db.base import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User
class RefreshToken(Base):
    __tablename__="refresh_tokens"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="CASCADE"),nullable=False,index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True,nullable=False)
    issued_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    revoked_at:Mapped[datetime | None]=mapped_column(DateTime(timezone=True),nullable=True)
    user_agent:Mapped[str | None]=mapped_column(String(512),nullable=True)
    ip_address:Mapped[str | None]=mapped_column(String(64),nullable=True)
    user:Mapped["User"]=relationship("User",back_populates="refresh_tokens")