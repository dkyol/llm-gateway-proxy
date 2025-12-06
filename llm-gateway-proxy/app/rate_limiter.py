from fastapi import Depends, HTTPException
from redis.asyncio import Redis
from pydantic_settings import BaseSettings
from app.auth import get_current_user
import os
from app.log import log_to_posthog

class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"

settings = Settings()
redis = Redis.from_url(settings.REDIS_URL)

class TokenBudgetLimiter:
    MONTHLY_BUDGET = 1_000_000
    ESTIMATED_TOKENS_PER_REQUEST = 2000
   
    async def check_and_increment(self, user_id: str, estimated_tokens: int = ESTIMATED_TOKENS_PER_REQUEST):
        """Check if user has budget remaining and pre-increment with estimate. Now REQUIRES authenticated user."""
        if not user_id or user_id == "anonymous":
            log_to_posthog(user_id or "anonymous", "token_budget_access_denied", {"reason": "unauthenticated"})
            raise HTTPException(status_code=401, detail="Authentication required")

        key = f"budget:{user_id}"
       
        current = await redis.get(key)
        current_usage = int(current or 0)
       
        # Check if adding this request would exceed budget
        if current_usage + estimated_tokens > self.MONTHLY_BUDGET:
            log_to_posthog(user_id, 'token_budget_exceeded', {'current_usage': current_usage, 'estimated_tokens': estimated_tokens})
            raise HTTPException(status_code=429, detail="Monthly token budget exceeded")
       
        # Pre-increment with estimate to reserve budget for this request
        if current is None:
            await redis.set(key, estimated_tokens, ex=2592000)  # 30 days
        else:
            await redis.incrby(key, estimated_tokens)
       
        log_to_posthog(user_id, 'token_budget_incremented', {'estimated_tokens': estimated_tokens, 'new_usage': current_usage + estimated_tokens})
       
        return estimated_tokens

    async def reconcile_usage(self, user_id: str, estimated: int, actual: int):
        """Reconcile estimated with actual token usage. Skips silently if called incorrectly (should never happen with required auth)."""
        if not user_id or user_id == "anonymous":
            return  # Safe fallback – check_and_increment should have already blocked this

        key = f"budget:{user_id}"
        difference = actual - estimated
        if difference != 0:
            await redis.incrby(key, difference)
            log_to_posthog(user_id, 'token_usage_reconciled', {'estimated': estimated, 'actual': actual, 'difference': difference})
   
    async def increment_usage(self, user_id: str, tokens: int):
        """Direct increment for cases without pre-increment – now also requires authentication."""
        if not user_id or user_id == "anonymous":
            log_to_posthog(user_id or "anonymous", "token_budget_access_denied", {"reason": "unauthenticated"})
            raise HTTPException(status_code=401, detail="Authentication required")
           
        key = f"budget:{user_id}"
        current = await redis.get(key)
        current_usage = int(current or 0)

        if current is None:
            await redis.set(key, tokens, ex=2592000)  # 30 days
        else:
            await redis.incrby(key, tokens)
       
        log_to_posthog(user_id, 'token_usage_incremented', {'tokens': tokens, 'new_usage': current_usage + tokens})

token_budget_limiter = TokenBudgetLimiter()