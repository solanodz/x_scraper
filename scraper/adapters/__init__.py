"""Source Adapters: normalizan fuentes externas a registros de Signal."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

from scraper.adapters.alpha_vantage import AlphaVantageNewsAdapter
from scraper.adapters.base import SourceAdapter
from scraper.adapters.marketaux import MarketauxNewsAdapter
from scraper.adapters.rss import RssNewsAdapter
from scraper.adapters.x_complement import XComplementAdapter


def get_enabled_adapters() -> list[SourceAdapter]:
    """Adapters habilitados según env (MARKETAUX_API_KEY, RSS_NEWS_ENABLED, etc.)."""
    load_dotenv()
    adapters: list[SourceAdapter] = []

    rss_on = os.getenv("RSS_NEWS_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    if rss_on:
        adapters.append(RssNewsAdapter())

    if os.getenv("MARKETAUX_API_KEY", "").strip():
        adapters.append(MarketauxNewsAdapter())

    if os.getenv("ALPHA_VANTAGE_API_KEY", "").strip():
        adapters.append(AlphaVantageNewsAdapter())

    return adapters


async def fetch_all_adapters(
    adapters: list[SourceAdapter] | None = None,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Ejecuta fetch() en cada adapter habilitado."""
    enabled = adapters if adapters is not None else get_enabled_adapters()
    records: list[dict[str, Any]] = []
    for adapter in enabled:
        print(f"→ {adapter.name} (límite: {limit})")
        batch = await adapter.fetch(limit=limit)
        print(f"  ✓ {len(batch)} Signals")
        records.extend(batch)
    return records


def get_x_complement_adapter(
    *,
    limit_per_account: int = 10,
    limit_per_search: int = 15,
    max_accounts: int | None = None,
    accounts_only: bool = False,
    search_only: bool = False,
) -> XComplementAdapter:
    """Adapter X como complemento (límites bajos vs News Sources)."""
    return XComplementAdapter(
        limit_per_account=limit_per_account,
        limit_per_search=limit_per_search,
        max_accounts=max_accounts,
        accounts_only=accounts_only,
        search_only=search_only,
    )
