"""Source Adapter: Marketaux financial news API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

from scraper.adapters.base import SourceAdapter

MARKETAUX_NEWS_URL = "https://api.marketaux.com/v1/news/all"

last_fetch_status: str | None = None
last_fetch_message: str | None = None


def _sentiment_label(score: float) -> str:
    if score >= 0.35:
        return "Bullish"
    if score >= 0.15:
        return "Somewhat-Bullish"
    if score <= -0.35:
        return "Bearish"
    if score <= -0.15:
        return "Somewhat-Bearish"
    return "Neutral"


def _parse_published(raw: str) -> datetime:
    if not raw:
        return datetime.now(tz=timezone.utc)
    try:
        normalized = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(tz=timezone.utc)


def _normalize_tickers(entities: list[Any]) -> list[str]:
    tickers: list[str] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        symbol = str(entity.get("symbol") or "").strip().upper()
        if symbol and symbol not in tickers:
            tickers.append(symbol)
    return tickers


def _average_sentiment(entities: list[Any]) -> float | None:
    scores: list[float] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        raw = entity.get("sentiment_score")
        if raw is None:
            continue
        try:
            scores.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not scores:
        return None
    return sum(scores) / len(scores)


def _primary_topic(entities: list[Any]) -> str | None:
    if not entities or not isinstance(entities[0], dict):
        return None
    industry = str(entities[0].get("industry") or "").strip()
    return industry or None


class MarketauxNewsAdapter(SourceAdapter):
    """Marketaux /v1/news/all → Signals con tickers y sentiment."""

    @property
    def name(self) -> str:
        return "Marketaux News"

    @property
    def source_type(self) -> str:
        return "marketaux"

    def _get_api_token(self) -> str | None:
        load_dotenv()
        token = os.getenv("MARKETAUX_API_KEY", "").strip()
        return token or None

    def _request_limit(self, limit: int) -> int:
        load_dotenv()
        raw = os.getenv("MARKETAUX_LIMIT_PER_REQUEST", "3").strip()
        plan_max = int(raw) if raw.isdigit() else 3
        return max(1, min(limit, plan_max))

    def _watchlist_symbols(self) -> str | None:
        load_dotenv()
        raw = os.getenv("WATCHLIST", "").strip()
        if not raw:
            return None
        symbols = [part.strip().upper() for part in raw.split(",") if part.strip()]
        if not symbols:
            return None
        return ",".join(symbols[:20])

    async def fetch(self, *, limit: int = 50) -> list[dict[str, Any]]:
        global last_fetch_status, last_fetch_message

        api_token = self._get_api_token()
        if not api_token:
            last_fetch_status = "no_api_key"
            last_fetch_message = "MARKETAUX_API_KEY no configurada"
            return []

        params: dict[str, str] = {
            "api_token": api_token,
            "language": "en",
            "must_have_entities": "true",
            "filter_entities": "true",
            "limit": str(self._request_limit(limit)),
        }
        symbols = self._watchlist_symbols()
        if symbols:
            params["symbols"] = symbols
        else:
            params["entity_types"] = "equity,index"
            params["countries"] = "us"

        url = f"{MARKETAUX_NEWS_URL}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "XScraperTerminal/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode()
                err_payload = json.loads(body)
                msg = str(err_payload.get("error") or err_payload.get("message") or body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                msg = body or str(exc)
            last_fetch_status = "http_error"
            last_fetch_message = msg
            print(f"  ⚠ Marketaux HTTP {exc.code}: {msg[:160]}", flush=True)
            return []
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            last_fetch_status = "network_error"
            last_fetch_message = str(exc)
            return []

        if payload.get("error"):
            msg = str(payload.get("error") or payload.get("message") or "unknown error")
            last_fetch_status = "api_error"
            last_fetch_message = msg
            print(f"  ⚠ Marketaux: {msg[:160]}", flush=True)
            return []

        articles = payload.get("data")
        if not isinstance(articles, list):
            last_fetch_status = "invalid_response"
            last_fetch_message = f"unexpected keys: {list(payload.keys())[:5]}"
            return []

        last_fetch_status = "ok"
        last_fetch_message = None

        records: list[dict[str, Any]] = []
        for item in articles:
            if not isinstance(item, dict):
                continue

            canonical_url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            summary = str(
                item.get("description") or item.get("snippet") or ""
            ).strip()
            if not canonical_url or not title:
                continue

            uuid = str(item.get("uuid") or canonical_url).strip()
            source_name = str(item.get("source") or "Marketaux").strip()
            published = _parse_published(str(item.get("published_at") or ""))
            entities = item.get("entities") if isinstance(item.get("entities"), list) else []
            tickers = _normalize_tickers(entities)
            cashtags = [f"${t}" for t in tickers]
            avg_sentiment = _average_sentiment(entities)
            sentiment = _sentiment_label(avg_sentiment) if avg_sentiment is not None else None
            topic = _primary_topic(entities)
            image_url = str(item.get("image_url") or "").strip() or None

            record: dict[str, Any] = {
                "id_str": f"marketaux:{uuid}",
                "source_type": self.source_type,
                "canonical_url": canonical_url,
                "title": title,
                "body": None,
                "summary": summary or title,
                "tickers": tickers,
                "sentiment": sentiment,
                "topic": topic,
                "relevance_score": None,
                "image_url": image_url,
                "date": published.isoformat(),
                "user": {"username": source_name},
                "rawContent": f"{title}\n\n{summary}" if summary else title,
                "source": "marketaux:news/all",
                "cashtags": cashtags,
                "hashtags": [],
                "replyCount": 0,
                "retweetCount": 0,
                "likeCount": 0,
                "quoteCount": 0,
                "bookmarkedCount": 0,
                "payload": {
                    "uuid": uuid,
                    "entities": entities,
                    "language": item.get("language"),
                    "image_url": image_url,
                },
            }
            records.append(record)

        return records
