"""Verificación F40: get_dossier (missing dossier + tool wiring)."""

from __future__ import annotations

import json
import sys
from unittest.mock import patch

from backend.services.tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    reset_research_operator_id,
    set_research_operator_id,
)


def main() -> int:
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "get_dossier" in names, "get_dossier missing from TOOL_DEFINITIONS"

    # Sin operator_id: mensaje honesto
    raw, hits = execute_tool("get_dossier", {"symbol": "NVDA"}, operator_id=None)
    assert hits == []
    payload = json.loads(raw)
    assert "operator_id" in (payload.get("error") or "").lower() or payload.get(
        "message"
    )

    # Con operator_id pero sin Dossier en Store
    token = set_research_operator_id("verify-operator-f40")
    try:
        with patch(
            "backend.app.services.dossier_repo.get_latest",
            return_value=None,
        ):
            raw2, hits2 = execute_tool(
                "get_dossier",
                {"symbol": "NVDA"},
                operator_id="verify-operator-f40",
            )
        assert hits2 == []
        missing = json.loads(raw2)
        assert missing.get("found") is False
        assert "No hay Dossier" in (missing.get("message") or "")
        assert missing.get("symbol") == "NVDA"
    finally:
        reset_research_operator_id(token)

    # Con Dossier mock condensado
    fake_row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "symbol": "NVDA",
        "content": {
            "blocks": {
                "panorama_mercado": "Precio estable en el mock.",
                "narrativa_7d": "Catalizador mock.",
            }
        },
        "created_at": None,
    }
    with patch(
        "backend.app.services.dossier_repo.get_latest",
        return_value=fake_row,
    ):
        raw3, _ = execute_tool(
            "get_dossier",
            {"symbol": "NVDA"},
            operator_id="verify-operator-f40",
        )
    found = json.loads(raw3)
    assert found.get("found") is True
    assert "panorama_mercado" in (found.get("blocks") or {})

    print("verify_f40_dossier OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
