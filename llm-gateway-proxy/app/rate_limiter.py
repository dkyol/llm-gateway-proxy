from fastapi import Depends, HTTPException
from redis.asyncio import Redis
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    REDIS_URL: str

settings = Settings()

redis = Redis.from_url(settings.REDIS_URL)

async def token_budget_limiter(user=Depends(get_current_user_optional)):
    user_id = user["user_id"]
    key = f"budget:{user_id}"

    # Example: 1M tokens per month budget
    current = await redis.get(key)
    if current is None:
        await redis.set(key, 0, ex=2592000)  # 30 days

    if int(current or 0) > 1_000_000:
        raise HTTPException(429, "Monthly token budget exceeded")

    # Increment on response (LiteLLM does this automatically with logging)
    return True