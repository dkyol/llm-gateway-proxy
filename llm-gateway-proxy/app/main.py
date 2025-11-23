from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi import Depends

from litellm import acompletion 
from litellm.proxy.utils import ProxyConfig
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.auth import verify_api_key, verify_jwt, get_current_user_optional
from app.rate_limiter import token_budget_limiter
from app.cache import get_cached_response, set_cache
from app.logging import setup_logging 

import os
import time

app = FastAPI(
    title="LLM Gateway Proxy",
    description="Open AI compatitable with authentication",
    openapi_url="/openapi.json",
    docs_url="/docs"
)# === Global setup ===
setup_logging()  # Helicone + Phoenix + OTEL

@app.post("/chat/completions")
@limiter.limit("60/minute") #global fallback

async def chat_completion(
    request: Request,
    user=Depends(get_current_user_optional),
    token_budget_check=Depends(token_budget_limiter)
):

    start_time = time.time()
    data = await request.json()

    # extract user_id 
    user_id = user['user_id'] if user else 'anonymous'

    #caching (simple has of prompt and model)
    cache_Key = f"{data.get('model')} : {hash(str(data.get('messages')))}"
    cached = await get_cached_response(cache_Key)

    if cached and data.get("stream") != True:
        return cached 

    try:
        response = await acompletion(
            model=data["model"]
            messages=data["messages"]
            temperature=data.get("temperature", ".8")
            max_tokens=data.get("max_tokens")
            stream=data.get("stream", False)
            user=user_id,
            litellm_call_id=request.headers.get("x-litellm-call-id"),
            #automatic fallback order 
            litellm_params={
                "timeout" : 120,
                "max_retries" : 2,
                "fallback_models": ["gpt-4o", "claude-3-5-sonnet-20241022"]

            }, 
            # logging & cost 
            metadata= {
                "user_api_key" : request.headers.get("authorization", "")[:20] + "...",
                "user_id": user_id,
                "helicone_api_key": os.getenv("HELICONE_API_KEY"),

            }
        )

        # cache non-streaming response for 5 minutes
        if not data.get("stream")
            await set_cache(cache_key, response, ttl=300)

        latency = time.time() - start_time
        print(f"Request succeeded | {user_id} | {latency:.2f}s")

        return response

    except Exception as e:
        latency = time.time() - start_time
        print(f"Request failed | {user_id} | {latency:.2f}s | {str(e)}")
        raise HTTPException(status_code=502, detail=str(e))

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