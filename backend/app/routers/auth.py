from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceRegister, WorkspaceResponse, TokenResponse
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
workspace_router = APIRouter(prefix="/workspace", tags=["workspace"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def create_access_token(user_id: UUID, workspace_id: UUID) -> str:
    payload = {
        "sub": str(user_id),
        "workspace_id": str(workspace_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@workspace_router.post("/register", status_code=201, response_model=WorkspaceResponse)
async def register(body: WorkspaceRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    workspace = Workspace(name=body.workspace_name)
    db.add(workspace)
    await db.flush()

    user = User(
        workspace_id=workspace.id,
        email=body.email,
        hashed_password=pwd_context.hash(body.password),
        role="owner"
    )
    db.add(user)
    await db.commit()

    return WorkspaceResponse(workspace_id=workspace.id, user_id=user.id, email=user.email)


class ChannelUpdateRequest(BaseModel):
    delivery_channels: dict


@workspace_router.patch("/channels", status_code=200)
async def update_channels(
    body: ChannelUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        sa_update(Workspace)
        .where(Workspace.id == current_user.workspace_id)
        .values(delivery_channels=body.delivery_channels)
    )
    await db.commit()
    return {"message": "Channels updated."}


@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(form.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token(user.id, user.workspace_id)
    return TokenResponse(access_token=token)
