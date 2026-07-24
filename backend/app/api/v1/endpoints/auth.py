import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.pg import Tenant, TenantUser, TenantPlan

router = APIRouter()

# Shared HTTPBearer scheme — reused as a FastAPI Depends
_http_bearer = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    company_name: str
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    tenant_id: str
    tenant_name: str


# ---------------------------------------------------------------------------
# Dependency: get_current_user
# BUG #2 FIX — now a proper FastAPI dependency using HTTPBearer
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    db: AsyncSession = Depends(get_db),
) -> TenantUser:
    """Decode JWT from Authorization header and return the active TenantUser."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await db.execute(select(TenantUser).where(TenantUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert a company name to a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)       # remove special chars
    slug = re.sub(r"[\s_]+", "-", slug)         # spaces → hyphens
    slug = re.sub(r"-+", "-", slug).strip("-")  # collapse hyphens
    return slug[:50]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new tenant (Party B) and its first admin user."""

    # Check email not already taken
    existing = await db.execute(
        select(TenantUser).where(TenantUser.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # BUG #4 FIX — make slug unique by appending a numeric suffix when needed
    base_slug = _slugify(body.company_name)
    slug = base_slug
    suffix = 1
    while True:
        collision = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if not collision.scalar_one_or_none():
            break
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    # Create tenant
    tenant = Tenant(
        name=body.company_name,
        slug=slug,
        plan=TenantPlan.STARTER,
        contact_email=body.email,
    )
    db.add(tenant)
    await db.flush()    # get tenant.id

    # Create admin user
    user = TenantUser(
        tenant_id=tenant.id,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role="admin",
    )
    db.add(user)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Registration failed due to a conflict. Please try again.")

    token_subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(token_subject, {"tenant_id": str(tenant.id), "role": "admin"}),
        refresh_token=create_refresh_token(token_subject),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TenantUser).where(TenantUser.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive")

    # Update last login
    user.last_login_at = datetime.now(UTC)

    return TokenResponse(
        access_token=create_access_token(
            str(user.id), {"tenant_id": str(user.tenant_id), "role": user.role}
        ),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        user_id = payload["sub"]
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(TenantUser).where(TenantUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(
            str(user.id), {"tenant_id": str(user.tenant_id), "role": user.role}
        ),
        refresh_token=create_refresh_token(str(user.id)),
    )


# BUG #3 FIX — add the missing /me endpoint
@router.get("/me", response_model=MeResponse)
async def me(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    db: AsyncSession = Depends(get_db),
):
    """Return the currently authenticated user's profile, with tenant name."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    # Load user + tenant in a single JOIN query
    result = await db.execute(
        select(TenantUser)
        .options(joinedload(TenantUser.tenant))
        .where(TenantUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc

    return MeResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=str(user.tenant_id),
        tenant_name=user.tenant.name,
    )