"""Verifica un access_token de Supabase contra el API (JWKS + HS256)."""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from backend.app.auth import verify_token


def main() -> int:
    load_dotenv()
    if len(sys.argv) < 2:
        print("Uso: .venv/bin/python -m backend.scripts.verify_auth_token <access_token>")
        print("Obtené el token: logueate → DevTools → http://localhost:3000/api/auth/token")
        return 1

    token = sys.argv[1].strip()
    try:
        claims = verify_token(token)
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1

    print("PASS: token válido")
    print(f"  sub: {claims.get('sub')}")
    print(f"  email: {claims.get('email')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
