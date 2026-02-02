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
    nombre_completo: Optional[str] = Field(None, nullable=True)
    password: Optional[str] = Field(None, nullable=True)
    usuario_activo: Optional[bool] = None