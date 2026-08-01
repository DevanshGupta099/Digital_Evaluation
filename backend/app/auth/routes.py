from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.database.session import get_db
from app.database.models import User, UserRole
from app.auth.schemas import UserLoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

@router.post("/login", response_model=UserResponse)
async def login(request: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Mock login: fetch a user by username and return their details.
    In a real app, this would verify passwords and issue JWTs.
    """
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username")
        
    return user

@router.get("/users", response_model=list[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    """
    List all mock users to populate the login dropdown.
    """
    result = await db.execute(select(User))
    return result.scalars().all()
