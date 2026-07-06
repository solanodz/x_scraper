"""FastAPI: REST + Feed Stream (SSE) + Chat Stream."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.auth import PUBLIC_PATHS, auth_enabled, verify_token
from backend.app.routes.chat import router as chat_router
from backend.app.routes.ingest import router as ingest_router
from backend.app.routes.quotes import router as quotes_router
from backend.app.routes.signals import router as signals_router
from backend.app.routes.watch import router as watch_router

load_dotenv()


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(
    title="X Scraper Terminal API",
    description="REST + Feed Stream SSE + Research Chat Stream",
    version="0.1.0",
)


@app.middleware("http")
async def require_auth(request: Request, call_next):
    if not auth_enabled():
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing bearer token"},
        )
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        verify_token(token)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )
    return await call_next(request)


# CORS después del auth middleware para que envuelva también respuestas 401
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(signals_router)
app.include_router(chat_router)
app.include_router(ingest_router)
app.include_router(quotes_router)
app.include_router(watch_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
