from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel,EmailStr,Field

class UserCreate(BaseModel):
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)

class UserLogin(BaseModel):
    email:EmailStr
    password:str

class UserRead(BaseModel):
    id:uuid.UUID
    email:EmailStr
    is_active:bool
    created_at:datetime

    model_config={"from_attributes":True}

class TokenPair(BaseModel):
    access_token:str
    refresh_token:str
    token_type:str="bearer"
    expires_in:int

class RefreshRequest(BaseModel):
    refresh_token:str

class AccessTokenResponse(BaseModel):
    access_token:str
    token_type:str="bearer"
    expires_in:int

class GenericMessage(BaseModel):
    detail:str
        