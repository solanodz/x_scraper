#!/usr/bin/env python3
"""Verificación F46: Morning Briefing Email con mocks (sin Resend ni DB real)."""

from __future__ import annotations

import sys
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend.services.briefing_email_render import build_email_bodies


SAMPLE_ARS_USD = {
    "scope": "ars_usd",
    "quotes": [
        {
            "label": "oficial",
            "casa": "oficial",
            "nombre": "Oficial",
            "bid": 1000.0,
            "ask": 1050.0,
            "currency_pair": "USD/ARS",
            "updated_at": "2026-07-23T08:00:00.000Z",
            "source": "dolarapi.com",
        },
        {
            "label": "blue",
            "casa": "blue",
            "nombre": "Blue",
            "bid": 1200.0,
            "ask": 1220.0,
            "currency_pair": "USD/ARS",
            "updated_at": "2026-07-23T08:05:00.000Z",
            "source": "dolarapi.com",
        },
    ],
    "fetched_at": "2026-07-23T11:00:00+00:00",
    "source": "dolarapi.com",
}

BRIEFING_MD = (
    "## Prioridad alta\n\n- **AAPL**: noticia material del día.\n\n"
    "## Otras novedades\n\nSin más."
)


def _assert_fx_body_clean(body: str) -> None:
    lower = body.lower()
    assert "blue" in lower, "body debe mencionar blue"
    assert "oficial" in lower, "body debe mencionar oficial"
    assert "eur" not in lower, "body no debe mencionar EUR"
    assert "frankfurter" not in lower, "body no debe mencionar Frankfurter"
    assert "brl" not in lower, "body no debe mencionar BRL"


def test_render_ars_usd_only() -> None:
    now_local = datetime(2026, 7, 23, 8, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
    subject, text, html = build_email_bodies(
        briefing_markdown=BRIEFING_MD,
        fx_payload=SAMPLE_ARS_USD,
        frontend_base_url="http://localhost:3000",
        now_local=now_local,
        has_prioridad_alta=True,
    )
    assert subject.startswith("Briefing · 23/07")
    combined = text + "\n" + html
    _assert_fx_body_clean(combined)
    assert "/terminal" in text
    assert "/research" in text
    assert "consejo de inversión" in text.lower()


def test_orchestrator_dry_run_force_already_sent() -> None:
    send_calls: list[dict] = []
    log_state: dict[tuple[str, date], str] = {}

    def fake_send_email(*, to, subject, html, text, dry_run=False):
        send_calls.append(
            {"to": to, "subject": subject, "html": html, "text": text}
        )
        return "re_mock_123"

    def fake_already_sent(*, operator_id, sent_on):
        return (operator_id, sent_on) in log_state

    def fake_insert_sent_log(*, operator_id, sent_on, resend_id):
        log_state[(operator_id, sent_on)] = resend_id or ""
        return {
            "id": "log-1",
            "operator_id": operator_id,
            "sent_on": sent_on,
            "resend_id": resend_id,
        }

    def fake_iter_briefing_stream(operator_id, **kwargs):
        yield BRIEFING_MD
        yield []

    env = {
        "BRIEFING_EMAIL_ENABLED": "true",
        "BRIEFING_EMAIL_TO": "op@example.com",
        "BRIEFING_EMAIL_TZ": "America/Argentina/Buenos_Aires",
        "BRIEFING_OPERATOR_ID": "00000000-0000-0000-0000-000000000099",
        "FRONTEND_BASE_URL": "http://localhost:3000",
        "LOCAL_OPERATOR_ID": "00000000-0000-0000-0000-000000000001",
    }

    with (
        patch.dict("os.environ", env, clear=False),
        patch(
            "backend.services.briefing_email.get_fx_quotes",
            return_value=SAMPLE_ARS_USD,
        ) as mock_fx,
        patch(
            "backend.services.briefing_email.iter_briefing_stream",
            side_effect=fake_iter_briefing_stream,
        ),
        patch(
            "backend.services.briefing_email.send_email",
            side_effect=fake_send_email,
        ),
        patch(
            "backend.services.briefing_email.log_table_ready",
            return_value=True,
        ),
        patch(
            "backend.services.briefing_email.already_sent",
            side_effect=fake_already_sent,
        ),
        patch(
            "backend.services.briefing_email.insert_sent_log",
            side_effect=fake_insert_sent_log,
        ),
        patch(
            "backend.services.briefing_email.chat_tables_ready",
            return_value=False,
        ),
    ):
        from backend.services.briefing_email import run_morning_briefing

        # 1) dry_run: no Resend, no log
        dry = run_morning_briefing(dry_run=True, force=False)
        assert dry.get("skipped") is False
        assert dry.get("dry_run") is True
        assert dry.get("resend_id") is None
        assert dry.get("text")
        assert dry.get("html")
        _assert_fx_body_clean(dry["text"] + "\n" + dry["html"])
        assert len(send_calls) == 0
        assert len(log_state) == 0
        mock_fx.assert_called_with(scope="ars_usd")

        # 2) force path: envía una vez + log
        sent = run_morning_briefing(dry_run=False, force=True)
        assert sent.get("skipped") is False
        assert sent.get("resend_id") == "re_mock_123"
        assert len(send_calls) == 1
        _assert_fx_body_clean(send_calls[0]["text"] + "\n" + send_calls[0]["html"])
        assert len(log_state) == 1

        # 3) already_sent skips (sin force)
        skip = run_morning_briefing(dry_run=False, force=False)
        assert skip.get("skipped") is True
        assert skip.get("reason") == "already_sent"
        assert len(send_calls) == 1  # no second send


def test_disabled_skips_unless_dry_run() -> None:
    env = {
        "BRIEFING_EMAIL_ENABLED": "false",
        "BRIEFING_EMAIL_TO": "op@example.com",
        "BRIEFING_OPERATOR_ID": "00000000-0000-0000-0000-000000000099",
    }
    with patch.dict("os.environ", env, clear=False):
        from backend.services.briefing_email import run_morning_briefing

        out = run_morning_briefing(dry_run=False, force=False)
        assert out.get("skipped") is True
        assert out.get("reason") == "disabled"


def main() -> int:
    test_render_ars_usd_only()
    test_orchestrator_dry_run_force_already_sent()
    test_disabled_skips_unless_dry_run()
    print("verify_f46_briefing_email OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
