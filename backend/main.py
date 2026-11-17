from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db
from app.core.errors import AppError
from app.core.logging import configure_logging, new_request_id
from app.api.endpoints import (
    auth, users, projects, datasets, sql, charts, dashboards, analysis, notebooks,
    ai, reports, misc, spreadsheet,
)

configure_logging()
import logging

logger = logging.getLogger("nexus")

app = FastAPI(
    title="Nexus Data API",
    version="1.0.0",
    description="All-in-one data analytics platform: import, profile, clean, transform, SQL, visualize, model and report.",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
)

# Rate limiting storage (in-memory, use Redis for production)
_rate_limit_storage: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = False  # Simple lock for single-threaded safety

def _rate_limit_key(request: Request) -> str:
    """Generate rate limit key from client IP."""
    client_ip = request.client.host if request.client else "unknown"
    # Include user ID if authenticated
    user_id = getattr(request.state, "user_id", None)
    return f"{client_ip}:{user_id or 'anon'}"

async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """Rate limiting middleware using sliding window."""
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)
    
    # Skip rate limiting for health/docs endpoints
    if request.url.path in ("/health", "/api/docs", "/api/openapi.json", "/"):
        return await call_next(request)
    
    key = _rate_limit_key(request)
    now = time.time()
    window = settings.RATE_LIMIT_WINDOW_SECONDS
    max_requests = settings.RATE_LIMIT_MAX
    
    # Clean old entries and count current window
    requests = _rate_limit_storage[key]
    # Remove timestamps outside the window
    while requests and requests[0] < now - window:
        requests.pop(0)
    
    if len(requests) >= max_requests:
        return JSONResponse(
            status_code=429,
            content={
                "message": "Rate limit exceeded. Please slow down.",
                "retry_after": int(window),
            },
            headers={
                "Retry-After": str(int(window)),
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + window)),
            },
        )
    
    requests.append(now)
    
    response = await call_next(request)
    
    # Add rate limit headers
    remaining = max(0, max_requests - len(requests))
    response.headers["X-RateLimit-Limit"] = str(max_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(int(now + window))
    
    return response

# CSP middleware
async def csp_middleware(request: Request, call_next: Callable) -> Response:
    """Add Content Security Policy headers."""
    response = await call_next(request)
    
    if settings.CSP_ENABLED:
        # Strict CSP - adjust as needed for frontend resources
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' https://*.supabase.co wss://*.supabase.co; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    return response

app.middleware("http")(rate_limit_middleware)
app.middleware("http")(csp_middleware)

origins = ["*"]
if settings.CORS_ORIGINS != "*":
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = new_request_id()
    start = time.perf_counter()
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except AppError as exc:
        return JSONResponse(status_code=exc.status_code, content={
            "message": exc.message, "error_id": request_id, "code": exc.code,
            "detail": exc.detail,
        })
    except Exception as exc:  # noqa: BLE001
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={
            "message": "An unexpected error occurred. Please try again or contact support.",
            "error_id": request_id,
        })
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Duration-Ms"] = f"{duration_ms:.1f}"
    logger.info(
        "request",
        extra={"request_id": request_id, "operation": f"{request.method} {request.url.path}",
               "duration_ms": round(duration_ms, 1), "status": response.status_code},
    )
    return response


@app.on_event("startup")
def on_startup():
    from app.core.jobs import RUNNING  # noqa: F401
    init_db()
    logger.info("Nexus Data started")


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(datasets.router)
app.include_router(sql.router)
app.include_router(charts.router)
app.include_router(dashboards.router)
app.include_router(analysis.router)
app.include_router(analysis.ML_ROUTER)
app.include_router(notebooks.router)
app.include_router(ai.router)
app.include_router(reports.router)
app.include_router(misc.router)
app.include_router(spreadsheet.router)


@app.get("/")
def root():
    return {
        "app": "Nexus Data",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health",
    }