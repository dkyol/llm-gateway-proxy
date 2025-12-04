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
    description="OpenAI compatible with authentication",  
    openapi_url="/openapi.json",
    docs_url="/docs"
)

# === Global setup ===
setup_logging()  
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/chat/completions")
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

@app.post("/chat/fallback_completion")
async def fallback_completion(
    request: Request,
    user = Depends(get_current_user)
)

"""Attempts completion using models until once succeeds"""
data = await request.json()
user_id = user.sub

#expect list of models 
fallback_models: List[str] = data.pop("fallback_models", [])

if not fallback_models:
    raise HTTPException(
        status_code = status.HTTP_400_BAD_REQUEST,
        detail = "No List of models provided in request body"
    )

# try first model in the list 
primary_model_used = None

for model_name in fallback_models:
    request_data = data.copy()
    request_data['model'] = model_name 

    #estimate tokens 
    prompt_tokens = token_counter(model=model_name, messages=request_data.get("messages", []))
    max_tokens = request_data.get("max_tokens", 1024)
    estimated_tokens = prompt_tokens + max_tokens 

    try:
        await token_budget_limiter.check_and_increment(user_id, estimated_tokens)

        response = await acompletion(**request_data)

        #Success! Reconcile usage
        if not data.get("stream", False):
            if hasattr(response, "usage") and response.usage and response.usage.total_tokens:
                actual_tokens = response.usage.total_tokens
                await token_budget_limiter.reconcile_usage(user_id, estimated_tokens, actual_tokens)

        print(f"used this model {model_name}")
        return response 

    except Exception as e:
        # failure for this model
        await token_budget_limiter.reconcile_usage(user_id, estimated_tokens, 0)
        print(f"Model {model_name} failed. Trying next model. Error: {str(e)}")        
        continue # try next model
raise HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail = "list of models failed to generate a response"
)

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
