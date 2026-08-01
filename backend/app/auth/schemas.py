from pydantic import BaseModel
from typing import Optional
from app.database.models import UserRole

class UserLoginRequest(BaseModel):
    username: str

class UserResponse(BaseModel):
    id: str
    username: str
    name: str
    role: UserRole
    department_id: Optional[str] = None
    
    class Config:
        from_attributes = True
