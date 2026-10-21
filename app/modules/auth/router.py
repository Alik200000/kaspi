from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.modules.catalog.models import User, Organization
from app.modules.auth.schemas import UserRegister, UserLogin, TokenResponse, UserResponse
from app.modules.auth.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication & Multi-Tenancy"])


@router.post("/register", response_model=TokenResponse)
async def register_organization(
    payload: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a new tenant organization and creates its initial Owner account.
    """
    # Check if email is already taken
    existing_user = await db.execute(select(User).where(User.email == payload.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )

    # 1. Create Organization
    org = Organization(name=payload.organization_name)
    db.add(org)
    await db.flush()

    # 2. Create Owner User
    user = User(
        organization_id=org.id,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role="owner"
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 3. Generate JWT
    token = create_access_token({"sub": str(user.id), "org_id": str(org.id), "role": user.role})
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticates user and returns JWT access token.
    """
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    token = create_access_token({"sub": str(user.id), "org_id": str(user.organization_id), "role": user.role})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns current authenticated user profile.
    """
    return current_user
