from fastapi import Header, HTTPException, Depends, status
from jose import JWTError, jwt
from dotenv import load_dotenv
import os

# Load .env at module import time (safe to call multiple times)
load_dotenv()

# Load these once at startup – will raise a clear error if missing
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

if not JWT_SECRET:
    raise ValueError("JWT_SECRET is not set in environment variables / .env file")

# Load allowed API keys from .env as a comma-separated string
ALLOWED_API_KEYS_ENV = os.getenv("ALLOWED_API_KEYS", "")  # e.g. "sk-user-123,sk-user-456,sk-prod-abc123"
VALID_API_KEYS = {key.strip() for key in ALLOWED_API_KEYS_ENV.split(",") if key.strip()}

def verify_jwt(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e

def verify_api_key(x_api_key: str = Header(None, alias="x-api-key")):
    if not x_api_key or x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # Return the same shape as JWT payload so main.py can always use user.sub
    return {"sub": x_api_key}

def get_current_user(
    authorization: str = Header(None),
    x_api_key: str = Header(None, alias="x-api-key"),
):
    if authorization:
        return verify_jwt(authorization)
    if x_api_key:
        return verify_api_key(x_api_key)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated"
    )