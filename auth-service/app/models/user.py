from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String,Boolean,DateTime,func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.db.base import Base
from app.models.refresh_token import RefreshToken
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User
class User(Base):
    __tablename__="users"
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    email:Mapped[str]=mapped_column(String(320),unique=True,nullable=False,index=True)
    hashed_password:Mapped[str]=mapped_column(String(255),nullable=False)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
    
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    refresh_tokens:Mapped[list["RefreshToken"]]=relationship(
        back_populates="user",cascade="all , delete-orphan"
    )
