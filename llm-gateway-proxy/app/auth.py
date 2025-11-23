from fastapi import Header, HTTPException, Depends
from jose import JWTError, jwt
import os

def verify_jwt(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid token")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")])
        return payload
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

def verify_api_key(x_api_key: str = Header(None, alias="x-api-key")):
    # Simple API key allowlist (in prod use Redis/DB)
    valid_keys = {"sk-user-123", "sk-user-456"}
    if x_api_key not in valid_keys:
        raise HTTPException(401, "Invalid API key")
    return {"user_id": x_api_key[:20]}

def get_current_user_optional(
    authorization: str = Header(None),
    x_api_key: str = Header(None, alias="x-api-key")
):
    if authorization:
        return verify_jwt(authorization)
    if x_api_key:
        return verify_api_key(x_api_key)
    return {"user_id": "anonymous"}