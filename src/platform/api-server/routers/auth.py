"""
Authentication API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
import sys
sys.path.append('/home/mislav/footballvision-pro/src/platform/api-server')

from services.auth import get_auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: int
    email: str
    role: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """
    User login - returns JWT access and refresh tokens

    Default credentials (for development):
    - Email: admin@localhost
    - Password: admin
    - Role: admin
    """
    auth = get_auth_service()

    # TODO: Lookup user in database
    # For now, hardcoded admin user for development
    if req.email == "admin@localhost" and req.password == "admin":
        user_id = 1
        role = "admin"

        access_token = auth.create_access_token(user_id, req.email, role)
        refresh_token = auth.create_refresh_token(user_id)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user_id,
            email=req.email,
            role=role
        )

    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.post("/refresh")
async def refresh_token(req: RefreshRequest):
    """
    Refresh access token using refresh token

    Returns:
        New access token
    """
    auth = get_auth_service()
    payload = auth.verify_token(req.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # TODO: Get user from database using payload["user_id"]
    user_id = payload["user_id"]

    # Hardcoded for now
    new_access_token = auth.create_access_token(
        user_id,
        "admin@localhost",  # From DB
        "admin"  # From DB
    )

    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout():
    """
    Logout current user

    In a full implementation, this would invalidate the token
    in a blacklist or database
    """
    # TODO: Invalidate token in database/Redis
    return {"message": "Logged out successfully"}

@router.get("/verify")
async def verify_token(token: str):
    """
    Verify if a token is valid

    Args:
        token: JWT token to verify

    Returns:
        Token payload if valid
    """
    auth = get_auth_service()
    payload = auth.verify_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "valid": True,
        "user_id": payload.get("user_id"),
        "email": payload.get("email"),
        "role": payload.get("role")
    }
