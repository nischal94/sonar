from pydantic import BaseModel, EmailStr
from uuid import UUID

class WorkspaceRegister(BaseModel):
    workspace_name: str
    email: EmailStr
    password: str

class WorkspaceResponse(BaseModel):
    workspace_id: UUID
    user_id: UUID
    email: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
