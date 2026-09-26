"""
Authentication router.
Handles operator login, JWT token issuance, and user self-registration/profile.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import (
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    create_access_token,
    get_password_hash,
    verify_password,
)
from backend.api.deps import get_current_user
from backend.core.config import get_settings
from backend.database.models import UserModel
from backend.database.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token, summary="Authenticate and acquire JWT token")
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)) -> Token:
    """Authenticates email and password, returning a signed JWT Bearer token."""
    query = select(UserModel).where(UserModel.email == credentials.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    settings = get_settings()
    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id},
        expires_delta=expires,
    )

    return Token(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=int(expires.total_seconds()),
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register user",
)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> UserResponse:
    """Registers a new user. If no users exist in the system, automatically assigns ADMIN role."""
    query = select(UserModel).where(UserModel.email == user_in.email)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists",
        )

    # Check total users count to promote first user to ADMIN
    count_query = select(UserModel)
    all_users = (await db.execute(count_query)).scalars().all()
    assigned_role = "ADMIN" if len(all_users) == 0 else user_in.role

    new_user = UserModel(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=assigned_role,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
    )


@router.get("/me", response_model=UserResponse, summary="Get current logged-in user")
async def get_me(current_user: UserModel = Depends(get_current_user)) -> UserResponse:
    """Returns profile information for the authenticated session user."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
