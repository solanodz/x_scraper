"""Cliente fino Resend (HTTP) para Morning Briefing Email."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
    dry_run: bool = False,
) -> str:
    """Envía un email vía Resend. Devuelve el ``id`` del mensaje (o ``dry-run``)."""
    if dry_run:
        return "dry-run"

    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    from_addr = (os.environ.get("RESEND_FROM") or "").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY no configurada")
    if not from_addr:
        raise RuntimeError("RESEND_FROM no configurada")

    recipient = (to or "").strip()
    if not recipient:
        raise RuntimeError("destinatario (to) vacío")

    payload: dict[str, Any] = {
        "from": from_addr,
        "to": [recipient],
        "subject": subject,
        "html": html,
        "text": text,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "x-scraper-terminal/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        detail = f" {err_body}" if err_body else ""
        raise RuntimeError(f"Resend HTTP {exc.code}:{detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Resend network error: {exc}") from exc

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Resend respuesta no-JSON: {raw[:200]}") from exc

    message_id = data.get("id") if isinstance(data, dict) else None
    if not message_id:
        raise RuntimeError(f"Resend sin id en respuesta: {data!r}")
    return str(message_id)


if __name__ == "__main__":
    mid = send_email(
        to="test@example.com",
        subject="ping",
        html="<p>ping</p>",
        text="ping",
        dry_run=True,
    )
    assert mid == "dry-run", mid
    print("email_resend self-check OK")
