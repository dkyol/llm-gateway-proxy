from fastapi import FastAPI, Request, HTTPException, status, Depends, APIRouter

from litellm import acompletion, token_counter 
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.auth import verify_api_key, verify_jwt, get_current_user
from app.rate_limiter import token_budget_limiter
from app.cache import get_cached_response, set_cache
from app.logging import setup_logging 

import os
import time

app = FastAPI(
    title="LLM Gateway Proxy",
    description="OpenAI compatible with authentication",  # fixed typo
    openapi_url="/openapi.json",
    docs_url="/docs"
)

# === Global setup ===
setup_logging()  
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Fix: define router and include it so the endpoint actually exists and is under /v1
router = APIRouter()

@router.post("/chat/completions")
async def chat_completion(
    request: Request,
    user = Depends(get_current_user),  # REQUIRED auth – 401 if missing JWT or API key
):
    data = await request.json()
    user_id = user.sub  # JWT sub is the user ID (or use user.id if you store it differently)

    model = data.get("model")
    messages = data.get("messages", [])
    max_tokens = data.get("max_tokens", 1024)  # safe default

    # Accurate prompt token count + conservative completion estimate
    prompt_tokens = token_counter(model=model, messages=messages)
    estimated_tokens = prompt_tokens + max_tokens

    # Reserve budget – will raise 429 if exceeded
    await token_budget_limiter.check_and_increment(user_id, estimated_tokens)

    try:
        # Forward to LiteLLM
        response = await acompletion(**data)

        # Reconcile exact usage for non-streaming requests
        if not data.get("stream", False):
            if hasattr(response, "usage") and response.usage and response.usage.total_tokens:
                actual_tokens = response.usage.total_tokens
                await token_budget_limiter.reconcile_usage(user_id, estimated_tokens, actual_tokens)

        return response

    except Exception as e:
        # If the LLM call fails, give the tokens back
        await token_budget_limiter.reconcile_usage(user_id, estimated_tokens, 0)
        raise e

# Health + OpenAI-compatible root
@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok", "proxy": "llm-gateway-proxy"}

@app.get("/v1/models")
async def list_models(user=Depends(verify_api_key)):
    models = [
        {"id": "gpt-4o", "object": "model"},
        {"id": "claude-3-5-sonnet-20241022", "object": "model"},
    ]
    return {"data": models, "object": "list"}

# Critical: include the router so /v1/chat/completions exists
app.include_router(router, prefix="/v1")