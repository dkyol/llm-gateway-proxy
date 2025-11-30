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

async def set_cache(key: str, value, ttl: int = 300):
    try:
        # Handle LiteLLM/pydantic models and other serializable objects
        if hasattr(value, 'model_dump_json'):
            # Use model_dump_json for direct JSON string
            json_str = value.model_dump_json()
        elif hasattr(value, 'json'):
            # Some models have a json() method
            json_str = value.json()
        elif hasattr(value, 'model_dump'):
            # Convert to dict first then JSON
            json_str = json.dumps(value.model_dump())
        elif isinstance(value, dict):
            json_str = json.dumps(value)
        else:
            # Last resort: try to access __dict__
            if hasattr(value, '__dict__'):
                json_str = json.dumps(value.__dict__)
            else:
                # Give up gracefully
                print(f"Cache set warning: Cannot serialize value of type {type(value)}")
                return
        
        await redis.setex(key, ttl, json_str)
    except Exception as e:
        print(f"Cache set error: {e}")
