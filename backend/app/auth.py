"""Supabase JWT validation (JWKS ES256/RS256 + legacy HS256)."""

from __future__ import annotations

import os
from functools import lru_cache

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

_bearer = HTTPBearer(auto_error=False)

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def auth_enabled() -> bool:
    load_dotenv()
    raw = os.getenv("AUTH_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def get_supabase_url() -> str | None:
    load_dotenv()
    url = (
        os.getenv("SUPABASE_URL", "").strip()
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
    )
    return url.rstrip("/") or None


def get_jwt_secret() -> str | None:
    load_dotenv()
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    return secret or None


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient | None:
    base = get_supabase_url()
    if not base:
        return None
    return PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json")


def _decode_with_jwks(token: str) -> dict:
    client = _jwks_client()
    if client is None:
        raise jwt.PyJWTError("SUPABASE_URL not configured for JWKS")
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256", "RS256"],
        audience="authenticated",
    )


def _decode_with_secret(token: str) -> dict:
    secret = get_jwt_secret()
    if not secret:
        raise jwt.PyJWTError("SUPABASE_JWT_SECRET not configured")
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience="authenticated",
    )


def verify_token(token: str) -> dict:
    """Valida access_token de Supabase Auth."""
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
    except jwt.PyJWTError:
        alg = ""

    if alg == "HS256":
        try:
            return _decode_with_secret(token)
        except jwt.PyJWTError:
            pass

    try:
        return _decode_with_jwks(token)
    except jwt.PyJWTError:
        pass

    try:
        return _decode_with_secret(token)
    except jwt.PyJWTError:
        pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    if not auth_enabled():
        return None
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return verify_token(credentials.credentials)


def operator_id_from_user(user: dict | None) -> str:
    """ID del Operator: JWT sub en prod, LOCAL_OPERATOR_ID (UUID) en dev sin auth."""
    if user:
        sub = user.get("sub")
        if sub:
            return str(sub)
    load_dotenv()
    default = "00000000-0000-0000-0000-000000000001"
    raw = os.getenv("LOCAL_OPERATOR_ID", default).strip() or default
    return raw
