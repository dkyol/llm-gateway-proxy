from fastapi import FastAPI, Request, HTTPException, status, Depends, APIRouter
from litellm import acompletion, token_counter 
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.auth import verify_api_key, verify_jwt, get_current_user
from app.rate_limiter import token_budget_limiter
from app.cache import get_cached_response, set_cache
from app.log import setup_logging, log_to_posthog
from app.log import setup_logging 
import os
import time
from pydantic import BaseModel
from typing import List


app = FastAPI(
    title="LLM Gateway Proxy",
    description="OpenAI compatible with authentication",  
    openapi_url="/openapi.json",
    docs_url="/docs"
)

# === Global setup ===
setup_logging(app)  
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/chat/completions")
async def chat_completion(
    request: Request,
    #user = Depends(get_current_user),  # REQUIRED auth – 401 if missing JWT or API key
    user = None
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

        log_to_posthog(
        distinct_id=user_id,
        event="chat_completion_success",
        properties={
            "model": model,
            "prompt_tokens": prompt_tokens,
            "estimated_tokens": estimated_tokens,
            "actual_total_tokens": response.usage.total_tokens if hasattr(response, "usage") and response.usage else None,
            "stream": data.get("stream", False),
            "max_tokens": max_tokens,
            "temperature": data.get("temperature"),
            "user_agent": request.headers.get("user-agent"),
        },
        )
        return response

    except Exception as e:
        # If the LLM call fails, give the tokens back
        await token_budget_limiter.reconcile_usage(user_id, estimated_tokens, 0)
        
        log_to_posthog(
        distinct_id=user_id,
        event="chat_completion_error",
        properties={
            "model": model,
            "estimated_tokens": estimated_tokens,
            "error_type": str(type(e).__name__),
            "error_message": str(e)[:200],  # truncate long errors
        },
        )
        
        raise e

@app.post("/chat/fallback_completion")
async def fallback_completion(
    request: Request,
    user = Depends(get_current_user)
):

    """Attempts completion using models until once succeeds
     "fallback_models": ["gpt-4o", "claude-3-5-sonnet-20241022", "gpt-3.5-turbo"]
    """
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
    #primary_model_used = None
    
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
            
            log_to_posthog(
                distinct_id=user_id,
                event="fallback_completion_success",
                properties={
                    "successful_model": model_name,
                    "fallback_models_tried": fallback_models,
                    "successful_attempt_number": fallback_models.index(model_name) + 1,
                },
            )
            return response
 
    
        except Exception as e:
            # failure for this model
            await token_budget_limiter.reconcile_usage(user_id, estimated_tokens, 0)
            print(f"Model {model_name} failed. Trying next model. Error: {str(e)}")        
            continue # try next model
    log_to_posthog(
    distinct_id=user_id,
    event="fallback_completion_all_failed",
    properties={
        "fallback_models_tried": fallback_models,
    },
    )
    
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail = "list of models failed to generate a response"
    )

class ComparisonRequest(BaseModel):
    prompt: str
    models: List[str] #list of model names to compare 

class ModelResponseComparison(BaseModel):
    model_id: str
    response_content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    error: str | None = None

class ComparisonResponse(BaseModel):
    comparison_results: List[ModelResponseComparison]

@app.post("/compare_models", response_model=ComparisonResponse)
async def compare_models(
    comparison_data: ComparisonRequest,
    user = Depends(get_current_user)
    ):

    """Compares output from selected models for a single prompt"""

    user_id = user.sub
    results_list = []

    messages = [{"role": "user", "content": comparison_data.prompt}]

    # iterate through the requested models sequentially 
    for model_name in comparison_data.models:
        estimated_tokens = token_counter(model=model_name, messages=messages) + 1024

        try:
            await token_budget_limiter.check_and_increment(user_id, estimated_tokens)

            #Call LLM using lite LLM
            response = await acompletion(
                model = model_name,
                messages=messages,
                max_tokens=1024
            )

            # extract data and reconcile usage 
            actual_tokens = response.usage.total_tokens
            await token_budget_limiter.reconcile_usage(user_id, estimated_tokens, actual_tokens)

            results_list.append(
                    ModelResponseComparison(
                        model_id=model_name,
                        response_content=response.choices[0].message.content,
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                        error=None
                    )
            )
            successful = [r.model_id for r in results_list if r.error is None]
            log_to_posthog(
                distinct_id=user_id,
                event="model_comparison_completed",
                properties={
                    "models_requested": comparison_data.models,
                    "models_succeeded": successful,
                    "models_failed": [r.model_id for r in results_list if r.error is not None],
                    "total_prompt_tokens": sum(r.prompt_tokens for r in results_list),
                },
            )


        except Exception as e:
            # if any model fails give tokens back

            await token_budget_limiter.reconcile_usage(user_id, estimated_tokens, 0 )
            results_list.append(ModelResponseComparison(
                model_id=model_name,
                response_content = "",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                error=str(e)
            ))

    return ComparisonResponse(comparison_results=results_list)
            
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
