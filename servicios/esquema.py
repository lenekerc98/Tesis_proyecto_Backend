from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nombre_completo: str
    role: str

class UserLogin(BaseModel):
    nombre: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UsuarioUpdateRequest(BaseModel):
    nombre_completo: Optional[str] = Field(None, min_length=3, max_length=150)
    password: Optional[str] = Field(None, min_length=8, max_length=64)