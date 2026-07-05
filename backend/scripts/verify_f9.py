"""Verificación F9: Auth + health."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.app.main import app


def main() -> int:
    load_dotenv()
    print("== F9 verification: Platform Auth ==\n")
    client = TestClient(app)

    print("1. GET /health (public)")
    r = client.get("/health")
    if r.status_code != 200:
        print(f"   FAIL: {r.status_code}")
        return 1
    print("   PASS\n")

    auth_on = os.getenv("AUTH_ENABLED", "true").lower() not in {"0", "false", "no", "off"}
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()

    print("2. GET /signals without token")
    r = client.get("/signals?limit=1")
    if auth_on and secret:
        if r.status_code != 401:
            print(f"   FAIL: expected 401, got {r.status_code}")
            return 1
        print("   PASS (401 as expected)\n")
    else:
        print("   SKIP (AUTH_ENABLED=false or no JWT secret)\n")

    print("== F9 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
