# Setup Notes for Replit Environment

## Completed Setup Tasks

### 1. Dependency Resolution
- Fixed FastAPI version conflict: changed from 0.115.2 to >=0.111.0,<0.112.0
- Fixed Uvicorn version conflict: changed from 0.30.6 to >=0.22.0,<0.23.0
- All Python dependencies installed successfully

### 2. Code Fixes
- Created missing `app/cache.py` module for Redis caching
- Fixed syntax errors in `main.py`:
  - Added missing commas in `acompletion()` call
  - Fixed missing colon in `if` statement
  - Fixed variable name case (`cache_key` vs `cache_Key`)
  - Removed invalid import `ProxyConfig`
- Fixed missing import in `rate_limiter.py` (`get_current_user_optional`)
- Added SlowAPI limiter initialization and exception handler

### 3. Environment Configuration
- Set environment variables:
  - `REDIS_URL`: redis://localhost:6379
  - `JWT_SECRET`: development-secret-change-in-production
  - `JWT_ALGORITHM`: HS256
- Installed and started Redis server
- Created `.gitignore` for Python projects

### 4. Replit Integration
- Configured workflow for port 5000 with webview output
- Set up deployment configuration (autoscale)
- Created comprehensive `replit.md` documentation

### 5. Rate Limiting & Token Budget
- Integrated SlowAPI with app.state.limiter
- Implemented token budget limiter with:
  - Pre-increment with 2000 token estimate per request
  - Reconciliation with actual usage from LiteLLM responses
  - Rollback on failed requests
  - Safe handling of anonymous users
  - Cache hits bypass budget checks

### 6. Cache Serialization
- Implemented robust serialization for LiteLLM responses:
  - Tries `model_dump_json()` first
  - Falls back to `json()` method
  - Then `model_dump()` + `json.dumps()`
  - Graceful error handling

## Known Limitations & Future Improvements

### Token Budget Accounting

**STATUS**: ⚠️  Token budget enforcement is currently **DISABLED**

The token budget feature has been disabled because proper implementation requires handling complex edge cases:
- Streaming responses (no immediate usage data)
- Generator exceptions (mid-stream failures)
- Client cancellations
- Provider errors after streaming starts

**Why Disabled**: Simple estimate-and-reconcile patterns leak reservations on streaming/error paths, causing:
- Incorrect quota accounting
- Users locked out from accumulated estimation errors
- No actual budget protection

**To Enable Properly**: Implement a `TokenBudgetReservation` async context manager:

```python
# Recommended pattern from architect review:
class TokenBudgetReservation:
    async def __aenter__(self):
        # Check and increment budget
        pass
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Always reconcile or rollback
        pass

# Usage in endpoint:
async with TokenBudgetReservation(user_id, estimate=2000) as reservation:
    response = await acompletion(...)
    if streaming:
        return wrap_streaming_response(response, reservation)
    else:
        reservation.reconcile(actual_tokens)
        return response
```

**Current Workaround**: The rate limiter (60 requests/minute) provides basic protection. For production use, implement the context manager pattern above before enabling token budgets.

**See**: Comments in `app/rate_limiter.py` for disabled code that can be re-enabled after proper implementation.

### Environment Variables for Production
The following environment variables should be set for production deployment:
- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key  
- `GROQ_API_KEY`: Your Groq API key
- `HELICONE_API_KEY`: (Optional) For observability
- `JWT_SECRET`: Strong secret for production (change from development default)
- `REDIS_URL`: Production Redis instance URL

### Authentication
Current implementation uses hardcoded API keys in `auth.py`:
```python
valid_keys = {"sk-user-123", "sk-user-456"}
```

**For Production**: Replace with database or Redis-based key management.

## Server Status
✅ Server running successfully on port 5000
✅ Health check endpoint working: GET /
✅ API documentation available: GET /docs
✅ OpenAI-compatible endpoints ready

## API Usage

### Authentication
Use one of two methods:
1. API Key: `x-api-key: sk-user-123`
2. JWT Token: `Authorization: Bearer <token>`

### Endpoints
- `POST /chat/completions` - Chat completion (OpenAI-compatible)
- `GET /v1/models` - List available models
- `GET /` or `/health` - Health check
- `GET /docs` - Interactive API documentation
