from fastapi import Depends, HTTPException
from redis.asyncio import Redis
from pydantic_settings import BaseSettings
from app.auth import get_current_user_optional
import os

class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"

settings = Settings()

redis = Redis.from_url(settings.REDIS_URL)

class TokenBudgetLimiter:
    MONTHLY_BUDGET = 1_000_000
    ESTIMATED_TOKENS_PER_REQUEST = 2000
    
    async def check_and_increment(self, user_id: str, estimated_tokens: int = 0):
        """Check if user has budget remaining and pre-increment with estimate"""
        key = f"budget:{user_id}"
        
        current = await redis.get(key)
        current_usage = int(current or 0)
        
        # Check if adding this request would exceed budget
        if current_usage + estimated_tokens >= self.MONTHLY_BUDGET:
            raise HTTPException(429, "Monthly token budget exceeded")
        
        # Pre-increment with estimate to reserve budget for this request
        if current is None:
            await redis.set(key, estimated_tokens, ex=2592000)  # 30 days
        else:
            await redis.incrby(key, estimated_tokens)
        
        return estimated_tokens  # Return how much we pre-incremented
    
    async def reconcile_usage(self, user_id: str, estimated: int, actual: int):
        """Reconcile estimated with actual token usage"""
        if not user_id or user_id == "anonymous":
            return
        
        key = f"budget:{user_id}"
        # Adjust by the difference (actual - estimated)
        difference = actual - estimated
        if difference != 0:
            await redis.incrby(key, difference)
    
    async def increment_usage(self, user_id: str, tokens: int):
        """Direct increment for cases without pre-increment"""
        if not user_id or user_id == "anonymous":
            return
            
        key = f"budget:{user_id}"
        current = await redis.get(key)
        if current is None:
            await redis.set(key, tokens, ex=2592000)  # 30 days
        else:
            await redis.incrby(key, tokens)

token_budget_limiter = TokenBudgetLimiter()

async def token_budget_check(user=Depends(get_current_user_optional)):
    """Dependency to check token budget before processing request
    
    NOTE: Token budget enforcement is currently DISABLED to avoid issues with streaming
    and complex edge cases. To enable, uncomment the check_and_increment logic below.
    See SETUP_NOTES.md for recommended implementation pattern using context managers.
    """
    # TODO: Implement proper token budget with TokenBudgetReservation context manager
    # For now, just return placeholder to avoid breaking the handler
    return {"estimated": 0, "user_id": user.get("user_id", "anonymous") if user else "anonymous"}
    
    # DISABLED - Uncomment after implementing proper context manager:
    # if not user:
    #     return {"estimated": 0, "user_id": "anonymous"}
    # 
    # user_id = user.get("user_id", "anonymous")
    # if user_id == "anonymous":
    #     return {"estimated": 0, "user_id": "anonymous"}
    # 
    # estimated = await token_budget_limiter.check_and_increment(
    #     user_id, 
    #     estimated_tokens=token_budget_limiter.ESTIMATED_TOKENS_PER_REQUEST
    # )
    # return {"estimated": estimated, "user_id": user_id}