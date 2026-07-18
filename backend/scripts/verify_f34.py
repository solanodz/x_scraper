"""Verificación F34 (smoke): GET /quotes/candles con interval+period."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    load_dotenv(ROOT / ".env")
    os.environ["AUTH_ENABLED"] = "false"

    from backend.app.main import app

    client = TestClient(app)
    failures: list[str] = []

    for symbol in ("NVDA", "BTC"):
        res = client.get(
            "/quotes/candles",
            params={"symbol": symbol, "period": "3mo", "interval": "1d"},
        )
        if res.status_code != 200:
            failures.append(f"{symbol}: HTTP {res.status_code}")
            continue

        body = res.json()
        if body.get("error"):
            failures.append(f"{symbol}: error={body['error']!r}")
            continue

        candles = body.get("candles") or []
        if not candles:
            failures.append(f"{symbol}: sin velas")
            continue

        if body.get("interval") != "1d":
            failures.append(f"{symbol}: interval={body.get('interval')!r} (esperado 1d)")
        if body.get("period") not in {"3mo", "1mo"}:
            # clamp no debería tocar 3mo+1d; aceptar period efectivo
            failures.append(f"{symbol}: period={body.get('period')!r}")

        last = candles[-1]
        for key in ("date", "open", "high", "low", "close", "volume"):
            if key not in last:
                failures.append(f"{symbol}: falta campo {key} en vela")

        close = float(last["close"])
        print(
            f"OK {symbol}: {len(candles)} velas, "
            f"period={body.get('period')}, interval={body.get('interval')}, "
            f"last_close={close}"
        )

        if symbol == "BTC" and close <= 1000:
            failures.append(
                f"BTC: last_close={close} (<=1000; probable símbolo sin mapear a BTC-USD)"
            )

    if failures:
        print("FAIL:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("verify_f34: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
