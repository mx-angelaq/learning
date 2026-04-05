"""Authentication routes."""

from fastapi import APIRouter, HTTPException, status
from app.auth import verify_password, create_access_token
from app.models.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    if not verify_password(request.password, request.role):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid password for role '{request.role}'."
        )
    token = create_access_token(request.role)
    return TokenResponse(access_token=token, role=request.role)
