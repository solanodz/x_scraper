"""Verificación F5: API REST + Feed Stream SSE + Chat Stream."""

from __future__ import annotations

import asyncio
import json
import sys
import time

from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routes.signals import _sse_signal_stream, stream_signals


async def _read_first_sse_chunk(timeout: float = 5.0) -> str:
    gen = _sse_signal_stream(None, None)
    return await asyncio.wait_for(gen.__anext__(), timeout=timeout)


def _read_chat_stream(response, timeout: float = 60.0) -> tuple[str, list[dict]]:
    """Lee Chat Stream: tokens acumulados + evento citations."""
    tokens: list[str] = []
    citations: list[dict] = []
    current_event: str | None = None
    deadline = time.monotonic() + timeout

    for raw_line in response.iter_lines():
        if time.monotonic() > deadline:
            break
        if raw_line is None:
            continue
        line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            data = line.split(":", 1)[1].strip()
            if current_event == "citations":
                citations = json.loads(data)
                break
            token = json.loads(data)
            if isinstance(token, str):
                tokens.append(token)

    return "".join(tokens), citations


def main() -> int:
    print("== F5 verification: API ==\n")
    client = TestClient(app)

    # 1. GET /signals
    print("1. GET /signals")
    response = client.get("/signals?limit=10")
    if response.status_code != 200:
        print(f"   FAIL: status {response.status_code}")
        return 1
    signals = response.json()
    print(f"   count: {len(signals)}")
    if not signals:
        print("   FAIL: empty list")
        return 1
    print(f"   first: {signals[0]['id_str']} @{signals[0]['username']}")
    print("   PASS\n")

    # 2. Feed Stream SSE — heartbeat from generator + StreamingResponse type
    print("2. GET /signals/stream (SSE heartbeat)")
    try:
        first_chunk = asyncio.run(_read_first_sse_chunk(timeout=5.0))
    except Exception as exc:
        print(f"   FAIL: {exc}")
        return 1
    print(f"   first_chunk: {first_chunk.strip()!r}")
    if "heartbeat" not in first_chunk:
        print("   FAIL: no heartbeat in first SSE chunk")
        return 1

    route_response = asyncio.run(stream_signals(None, None))
    if not isinstance(route_response, StreamingResponse):
        print("   FAIL: endpoint did not return StreamingResponse")
        return 1
    print(f"   media_type: {route_response.media_type}")
    print("   PASS\n")

    # 3. POST /chat — streamed content + citations
    print("3. POST /chat (stream + citations)")
    with client.stream(
        "POST",
        "/chat",
        json={"query": "resumen mercados hoy"},
        timeout=90.0,
    ) as response:
        if response.status_code != 200:
            print(f"   FAIL: status {response.status_code}")
            return 1
        answer, citations = _read_chat_stream(response, timeout=75.0)

    print(f"   answer_len: {len(answer)}")
    print(f"   answer_preview: {answer[:120]}...")
    print(f"   citations: {len(citations)}")
    if not answer.strip():
        print("   FAIL: empty streamed answer")
        return 1
    if not citations:
        print("   FAIL: no citations event")
        return 1
    print("   PASS\n")

    print("== F5 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
