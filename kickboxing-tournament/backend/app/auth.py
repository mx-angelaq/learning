"""Authentication: JWT-based admin/staff auth, public is unauthenticated."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.config import settings

security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def create_access_token(role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {"sub": role, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain_password: str, role: str) -> bool:
    if role == "admin":
        return plain_password == settings.ADMIN_PASSWORD
    elif role == "staff":
        return plain_password == settings.STAFF_PASSWORD
    return False


def get_current_role(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:
    if credentials is None:
        return None
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[ALGORITHM])
        role: str = payload.get("sub")
        if role not in ("admin", "staff"):
            return None
        return role
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError, Exception):
        return None


def require_admin(role: Optional[str] = Depends(get_current_role)):
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for this action."
        )
    return role


def require_staff_or_admin(role: Optional[str] = Depends(get_current_role)):
    if role not in ("admin", "staff"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff or admin access required for this action."
        )
    return role
