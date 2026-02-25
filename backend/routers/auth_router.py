"""Authentication router: signup, login, and current user."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.auth.jwt import create_access_token
from backend.auth.password import hash_password, verify_password
from backend.crud.user_crud import create_user, get_user_by_email
from backend.database import get_db
from backend.models.user import User
from backend.schemas.auth_schema import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(
    body: SignupRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Register a new user and return a JWT."""
    existing = await get_user_by_email(db, body.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    hashed = hash_password(body.password)
    user = await create_user(db, body.email, hashed)
    token = create_access_token({"sub": user.email})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Authenticate a user and return a JWT."""
    user = await get_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": user.email})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""
    return UserResponse.model_validate(current_user)
