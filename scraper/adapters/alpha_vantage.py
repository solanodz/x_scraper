"""Source Adapter: Alpha Vantage NEWS_SENTIMENT."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

from scraper.adapters.base import SourceAdapter

AV_NEWS_URL = "https://www.alphavantage.co/query"

# Último estado de fetch (diagnóstico para ingest/verify).
last_fetch_status: str | None = None
last_fetch_message: str | None = None


def _parse_av_time(raw: str) -> datetime:
    """Parsea time_published de AV (YYYYMMDDTHHMMSS)."""
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(tz=timezone.utc)


def _stable_id(url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"av:{digest}"


def _normalize_tickers(raw: list[Any]) -> list[str]:
    tickers: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            symbol = str(item.get("ticker") or "").strip().upper()
        else:
            symbol = str(item).strip().lstrip("$").upper()
        if symbol and symbol not in tickers:
            tickers.append(symbol)
    return tickers


class AlphaVantageNewsAdapter(SourceAdapter):
    """NEWS_SENTIMENT → Signals source-agnostic."""

    @property
    def name(self) -> str:
        return "Alpha Vantage NEWS_SENTIMENT"

    @property
    def source_type(self) -> str:
        return "alpha_vantage"

    def _get_api_key(self) -> str | None:
        load_dotenv()
        key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
        return key or None

    async def fetch(self, *, limit: int = 50) -> list[dict[str, Any]]:
        global last_fetch_status, last_fetch_message
        api_key = self._get_api_key()
        if not api_key:
            last_fetch_status = "no_api_key"
            last_fetch_message = "ALPHA_VANTAGE_API_KEY no configurada"
            return []

        params = urllib.parse.urlencode(
            {
                "function": "NEWS_SENTIMENT",
                "sort": "LATEST",
                "limit": str(min(max(limit, 1), 1000)),
                "apikey": api_key,
            }
        )
        url = f"{AV_NEWS_URL}?{params}"

        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                payload = json.loads(response.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            last_fetch_status = "network_error"
            last_fetch_message = str(exc)
            return []

        if payload.get("Note") or payload.get("Information"):
            msg = str(payload.get("Information") or payload.get("Note") or "")
            last_fetch_status = "rate_limited"
            last_fetch_message = msg
            print(
                f"  ⚠ Alpha Vantage: cuota agotada o throttled — comparte límite "
                f"diario con Quotes (QUOTE_MAX_DAILY_REQUESTS). {msg[:120]}",
                flush=True,
            )
            return []

        feed = payload.get("feed")
        if not isinstance(feed, list):
            last_fetch_status = "invalid_response"
            last_fetch_message = f"unexpected keys: {list(payload.keys())[:5]}"
            return []

        last_fetch_status = "ok"
        last_fetch_message = None

        records: list[dict[str, Any]] = []
        for item in feed:
            if not isinstance(item, dict):
                continue
            canonical_url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if not canonical_url or not title:
                continue

            source_name = str(item.get("source") or "Alpha Vantage").strip()
            published = _parse_av_time(str(item.get("time_published") or ""))
            tickers = _normalize_tickers(item.get("ticker_sentiment") or [])
            cashtags = [f"${t}" for t in tickers]

            topics = item.get("topics") or []
            topic = ""
            if topics and isinstance(topics[0], dict):
                topic = str(topics[0].get("topic") or "").strip()

            sentiment = str(item.get("overall_sentiment_label") or "").strip() or None

            record: dict[str, Any] = {
                "id_str": _stable_id(canonical_url),
                "source_type": self.source_type,
                "canonical_url": canonical_url,
                "title": title,
                "body": None,
                "summary": summary,
                "tickers": tickers,
                "sentiment": sentiment,
                "topic": topic or None,
                "relevance_score": None,
                "date": published.isoformat(),
                "user": {"username": source_name},
                "rawContent": f"{title}\n\n{summary}" if summary else title,
                "source": "alpha_vantage:NEWS_SENTIMENT",
                "cashtags": cashtags,
                "hashtags": [],
                "replyCount": 0,
                "retweetCount": 0,
                "likeCount": 0,
                "quoteCount": 0,
                "bookmarkedCount": 0,
            }
            records.append(record)

        return records
