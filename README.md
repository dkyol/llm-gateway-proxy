# LLM Gateway Proxy
**LLM Gateway Proxy** is a simple but powerful reverse proxy for Large Language Models that makes working with multiple models much easier and more reliable.

It gives you two super-useful features:

- **Instant model comparison** – Send the same prompt to several models at once and see all their responses side-by-side in a single request. Perfect for quickly testing which model (GPT-4o, Claude 3.5, Gemini, Llama 3.1, etc.) gives the best output for your use case.

- **Automatic fallback on failure** – Define a list of backup models/endpoints. If the main model times out, returns an error, or hits rate limits, the proxy instantly retries the request with the next model in your list—so your app never breaks because one provider is down or overloaded.

In short: compare models in one click, and keep your requests running reliably even if/when individual LLMs fail reach token limit. Don't babysit multiple APIs.

## Overview
An OpenAI-compatible API gateway proxy that provides:
- **OpenAI-compatible endpoint** for chat completions
- **JWT + API key authentication** for secure access
- **Per-user rate limiting** with monthly token budgets
- **Automatic fallback** across multiple LLM providers (OpenAI → Anthropic → Groq)
- **Response caching** using Redis for improved performance
- **Observability** PostHog
## Project Structure
```
llm-gateway-proxy/
├── app/
│   ├── main.py           # FastAPI application and endpoints
│   ├── auth.py           # JWT and API key authentication
│   ├── rate_limiter.py   # Token budget rate limiting
│   ├── cache.py          # Redis caching layer
│   └── logging.py        # OpenTelemetry setup
├── requirements.txt      # Python dependencies
└── README.md            # Original project description
```

## Technology Stack
- **Framework**: FastAPI 0.111.x
- **Server**: Uvicorn 0.22.x
- **LLM Client**: LiteLLM 1.52.6 (with automatic fallbacks)
- **Caching**: Redis 5.0.8
- **Rate Limiting**: SlowAPI
- **Authentication**: JWT (python-jose)
- **Observability**: OpenTelemetry

## Environment Variables

### Required
- `REDIS_URL`: Redis connection URL (default: redis://localhost:6379)
- `JWT_SECRET`: Secret key for JWT token signing
- `JWT_ALGORITHM`: JWT signing algorithm (default: HS256)

- LLM Provider API Keys (set as needed):
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GROQ_API_KEY`

### OpenAI-Compatible
- `POST /chat/completions` - Chat completion endpoint (requires authentication)
- `GET /v1/models` - List available models 

## Other API Endpoints
- /chat/fallback_completion
- /compare_models

### Health Check
- `GET /` or `GET /health` - Returns server status

## Authentication

The proxy supports two authentication methods:

1. **API Key**: Pass `x-api-key` header
2. **JWT Token**: Pass `Authorization: Bearer <token>` header

Anonymous requests are allowed but have limited quota.

## Rate Limiting
- Global rate limit: 60 requests per minute (via SlowAPI)
- **Note**: Per-user token budget enforcement is currently disabled (see SETUP_NOTES.md for details and implementation guidance)

## Development Setup

The application is configured to run on **port 5000** with:
- Redis running on localhost:6379
- Auto-reload enabled for development
- CORS configured for Replit proxy

## Deployment Configuration

The project uses **autoscale** deployment target:
- Automatically scales based on traffic
- Runs on-demand (cost-efficient)
- Command: `cd llm-gateway-proxy && uvicorn app.main:app --host 0.0.0.0 --port 5000`
- Note: The `cd llm-gateway-proxy` is required because the app code is in a subdirectory


## Notes

- The application uses LiteLLM for automatic provider fallback
- Caching is implemented for non-streaming responses (5-minute TTL)
- The proxy is OpenAI-compatible, allowing drop-in replacement for OpenAI API
- See **SETUP_NOTES.md** for known limitations and production recommendations
