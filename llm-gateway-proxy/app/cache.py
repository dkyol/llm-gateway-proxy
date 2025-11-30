from redis.asyncio import Redis
import json
import os

redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

async def get_cached_response(key: str):
    try:
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)
        return None
    except Exception as e:
        print(f"Cache get error: {e}")
        return None

async def set_cache(key: str, value: dict, ttl: int = 300):
    try:
        await redis.setex(key, ttl, json.dumps(value))
    except Exception as e:
        print(f"Cache set error: {e}")
