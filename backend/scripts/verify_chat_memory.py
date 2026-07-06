"""Verificación de memoria conversacional del Research Chat."""

from __future__ import annotations

import sys

from backend.services.chat_history import prepare_chat_history
from backend.services.llm import _build_synthesis_messages


def main() -> int:
    print("== Chat memory verification ==\n")

    history = [
        {"role": "user", "content": "¿Cómo está NVDA?"},
        {"role": "assistant", "content": "NVDA cotiza a $140 con suba del 2%."},
    ]
    prepared = prepare_chat_history(history)
    print(f"1. prepare_chat_history => {len(prepared)} messages")
    if len(prepared) != 2:
        print("   FAIL")
        return 1
    print("   PASS\n")

    messages = _build_synthesis_messages(
        "Market Data: NVDA $140",
        "¿y comparado con el mes pasado?",
        history=prepared,
    )
    print(f"2. synthesis messages => {len(messages)} turns")
    roles = [m["role"] for m in messages]
    if roles != ["system", "user", "assistant", "user"]:
        print(f"   FAIL: unexpected roles {roles}")
        return 1
    if "comparado con el mes pasado" not in messages[-1]["content"]:
        print("   FAIL: current query missing")
        return 1
    print("   PASS\n")

    print("== Chat memory verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
