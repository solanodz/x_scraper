"""Source Adapter: RSS feeds de noticias financieras (sin API key)."""

from __future__ import annotations

import hashlib
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any

from dotenv import load_dotenv

from scraper.adapters.base import SourceAdapter

# Feeds globales con URLs directas extraíbles (trafilatura). Google News = metadata.
DEFAULT_FEEDS: list[tuple[str, str]] = [
    (
        "Yahoo Finance",
        "https://finance.yahoo.com/news/rssindex",
    ),
    (
        "CNBC Top News",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    ),
    (
        "BBC Business",
        "http://feeds.bbci.co.uk/news/business/rss.xml",
    ),
    (
        "Google News Markets",
        "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en",
    ),
]

# Medios argentinos (economía/finanzas); trafilatura OK en Ámbito, La Nación, Infobae.
ARGENTINA_FEEDS: list[tuple[str, str]] = [
    (
        "Ámbito Economía",
        "https://www.ambito.com/rss/pages/economia.xml",
    ),
    (
        "Ámbito Finanzas",
        "https://www.ambito.com/rss/pages/finanzas.xml",
    ),
    (
        "La Nación Economía",
        "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/economia/",
    ),
    (
        "Infobae Economía",
        "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/",
    ),
    (
        "Google News AR",
        "https://news.google.com/rss/search?q=econom%C3%ADa+Argentina+OR+mercado+financiero+Argentina&hl=es-419&gl=AR&ceid=AR:es-419",
    ),
]

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return unescape(_TAG_RE.sub("", text)).strip()


def _stable_id(url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"rss:{digest}"


def _parse_pub_date(raw: str) -> datetime:
    if not raw:
        return datetime.now(tz=timezone.utc)
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return datetime.now(tz=timezone.utc)


def _find_items(root: ET.Element) -> list[ET.Element]:
    channel = root.find("channel")
    if channel is not None:
        return list(channel.findall("item"))
    atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", atom_ns)
    if entries:
        return entries
    return list(root.findall("item"))


def _item_field(item: ET.Element, tag: str, atom_ns: dict[str, str]) -> str:
    el = item.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    link = item.find("atom:link", atom_ns)
    if tag == "link" and link is not None:
        return (link.get("href") or "").strip()
    return ""


def rss_ar_feeds_enabled() -> bool:
    load_dotenv()
    raw = os.getenv("RSS_AR_FEEDS_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def get_rss_feeds() -> list[tuple[str, str]]:
    """Feeds RSS activos: globales + Argentina si RSS_AR_FEEDS_ENABLED."""
    feeds = list(DEFAULT_FEEDS)
    if rss_ar_feeds_enabled():
        feeds.extend(ARGENTINA_FEEDS)
    return feeds


class RssNewsAdapter(SourceAdapter):
    """RSS → Signals; fallback gratuito cuando Alpha Vantage agota cuota."""

    def __init__(self, feeds: list[tuple[str, str]] | None = None) -> None:
        self._feeds = feeds or get_rss_feeds()

    @property
    def name(self) -> str:
        return "RSS News Feeds"

    @property
    def source_type(self) -> str:
        return "rss"

    async def fetch(self, *, limit: int = 50) -> list[dict[str, Any]]:
        per_feed = max(limit // max(len(self._feeds), 1), 5)
        records: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for feed_name, feed_url in self._feeds:
            batch = self._fetch_feed(feed_name, feed_url, per_feed, seen_urls)
            records.extend(batch)
            if len(records) >= limit:
                break

        return records[:limit]

    def _fetch_feed(
        self,
        feed_name: str,
        feed_url: str,
        limit: int,
        seen_urls: set[str],
    ) -> list[dict[str, Any]]:
        try:
            req = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "XScraperTerminal/1.0"},
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                xml_bytes = response.read()
        except (urllib.error.URLError, TimeoutError, ET.ParseError):
            return []

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            return []

        atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = _find_items(root)
        records: list[dict[str, Any]] = []

        for item in items[:limit]:
            title = _strip_html(_item_field(item, "title", atom_ns))
            link = _item_field(item, "link", atom_ns)
            if not link:
                guid = _item_field(item, "guid", atom_ns)
                if guid.startswith("http"):
                    link = guid
            summary = _strip_html(
                _item_field(item, "description", atom_ns)
                or _item_field(item, "summary", atom_ns)
            )
            if not title or not link or link in seen_urls:
                continue
            seen_urls.add(link)

            published = _parse_pub_date(_item_field(item, "pubDate", atom_ns))
            records.append(
                {
                    "id_str": _stable_id(link),
                    "source_type": self.source_type,
                    "canonical_url": link,
                    "title": title,
                    "body": None,
                    "summary": summary or title,
                    "tickers": [],
                    "sentiment": None,
                    "topic": None,
                    "relevance_score": None,
                    "date": published.isoformat(),
                    "user": {"username": feed_name},
                    "rawContent": title,
                    "source": f"rss:{feed_name}",
                    "cashtags": [],
                    "hashtags": [],
                    "replyCount": 0,
                    "retweetCount": 0,
                    "likeCount": 0,
                    "quoteCount": 0,
                    "bookmarkedCount": 0,
                    "payload": {"feed": feed_name, "url": link, "title": title},
                }
            )

        return records
