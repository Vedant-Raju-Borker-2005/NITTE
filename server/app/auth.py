"""
MethaneX — JWT Authentication Module
=====================================
Demo auth layer with three hardcoded users.
Replace _DEMO_USERS with a real database for production.

Demo credentials:
  admin@methanex.app    / admin1234    (role: admin,    tier: enterprise)
  operator@methanex.app / operator1234 (role: operator, tier: pro)
  analyst@methanex.app  / analyst1234  (role: analyst,  tier: basic)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

try:
    from jose import JWTError, jwt
    _JOSE_AVAILABLE = True
except ImportError:
    _JOSE_AVAILABLE = False
    JWTError = Exception

try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _PASSLIB_AVAILABLE = True
except ImportError:
    _PASSLIB_AVAILABLE = False
    _pwd_context = None

# ── Configuration ─────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "methanex-demo-secret-key-change-in-production-2026!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8   # 8 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30

# ── OAuth2 bearer (auto_error=False so unauthenticated routes still work) ─────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ── Demo user store ────────────────────────────────────────────────────────────
def _hash(plain: str) -> str:
    if _PASSLIB_AVAILABLE and _pwd_context:
        return _pwd_context.hash(plain)
    # Fallback: store plain for demo if passlib not installed yet
    return f"plain:{plain}"


_DEMO_USERS: dict[str, dict] = {
    "admin@methanex.app": {
        "id": "usr-001",
        "email": "admin@methanex.app",
        "name": "Admin User",
        "role": "admin",
        "tier": "enterprise",
        "hashed_password": _hash("admin1234"),
    },
    "operator@methanex.app": {
        "id": "usr-002",
        "email": "operator@methanex.app",
        "name": "Facility Operator",
        "role": "operator",
        "tier": "pro",
        "hashed_password": _hash("operator1234"),
    },
    "analyst@methanex.app": {
        "id": "usr-003",
        "email": "analyst@methanex.app",
        "name": "ESG Analyst",
        "role": "analyst",
        "tier": "basic",
        "hashed_password": _hash("analyst1234"),
    },
}


# ── Password verification ──────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("plain:"):
        return plain == hashed[6:]
    if _PASSLIB_AVAILABLE and _pwd_context:
        try:
            return _pwd_context.verify(plain, hashed)
        except Exception:
            return False
    return plain == hashed


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Returns user dict if credentials valid, else None."""
    user = _DEMO_USERS.get(email.lower().strip())
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


# ── Token creation ─────────────────────────────────────────────────────────────
def _create_token(data: dict, expires_delta: timedelta) -> str:
    if not _JOSE_AVAILABLE:
        # Fallback: return a simple base64 encoded mock token for demo
        import base64, json
        payload = {**data, "exp": (datetime.utcnow() + expires_delta).isoformat()}
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

    payload = data.copy()
    payload["exp"] = datetime.utcnow() + expires_delta
    payload["iat"] = datetime.utcnow()
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user: dict) -> str:
    return _create_token(
        {"sub": user["id"], "role": user["role"], "tier": user["tier"]},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user: dict) -> str:
    return _create_token(
        {"sub": user["id"], "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


# ── Token verification ─────────────────────────────────────────────────────────
def verify_token(token: str) -> Optional[dict]:
    """Returns decoded payload dict or None if invalid/expired."""
    if not _JOSE_AVAILABLE:
        try:
            import base64, json
            payload = json.loads(base64.urlsafe_b64decode(token + "==").decode())
            return payload
        except Exception:
            return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── User lookups ───────────────────────────────────────────────────────────────
def get_user_by_id(user_id: str) -> Optional[dict]:
    for u in _DEMO_USERS.values():
        if u["id"] == user_id:
            return u
    return None


# ── FastAPI Dependencies ───────────────────────────────────────────────────────
async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[dict]:
    """Soft dependency — returns user or None (does not block unauthenticated requests)."""
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    return get_user_by_id(payload.get("sub", ""))


async def require_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> dict:
    """Hard dependency — raises 401 if not authenticated."""
    user = await get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Valid Bearer token required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_pro(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """Requires pro or enterprise tier."""
    user = await require_user(token)
    if user["tier"] not in ("pro", "enterprise"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TIER_LIMIT", "message": "Upgrade to Pro to access live scans"},
        )
    return user
