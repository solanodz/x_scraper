"""Source Adapter: X (twscrape) como complemento de reacción/chatter."""

from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv
from twscrape import API, gather

from scraper.adapters.base import SourceAdapter
from scraper.serialize import tweet_to_record
from scraper.sources import FINANCIAL_ACCOUNTS, SEARCH_QUERIES


def _has_x_cookies() -> bool:
    load_dotenv()
    cookies = os.getenv("X_COOKIES", "").strip()
    return bool(cookies and "auth_token=" in cookies and "ct0=" in cookies)


def x_complement_enabled() -> bool:
    load_dotenv()
    raw = os.getenv("X_COMPLEMENT_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _x_search_enabled() -> bool:
    load_dotenv()
    return os.getenv("X_INCLUDE_SEARCH", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _resolve_max_accounts(explicit: int | None) -> int:
    """Todas las cuentas por defecto; X_COMPLEMENT_MAX_ACCOUNTS o --max-accounts opcionales."""
    if explicit is not None:
        return max(0, explicit)
    load_dotenv()
    raw = os.getenv("X_COMPLEMENT_MAX_ACCOUNTS", "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return len(FINANCIAL_ACCOUNTS)


async def _setup_api() -> API | None:
    if not _has_x_cookies():
        return None

    load_dotenv()
    account_name = os.getenv("X_ACCOUNT_NAME", "default").strip()
    db_path = os.getenv("ACCOUNTS_DB", "accounts.db").strip()
    cookies = os.getenv("X_COOKIES", "").strip()

    api = API(db_path)
    await api.pool.add_account_cookies(account_name, cookies)
    return api


class XComplementAdapter(SourceAdapter):
    """X → Signals; complemento best-effort (no aborta si twscrape falla)."""

    def __init__(
        self,
        *,
        limit_per_account: int = 10,
        limit_per_search: int = 15,
        max_accounts: int | None = None,
        accounts_only: bool = False,
        search_only: bool = False,
    ) -> None:
        self._limit_per_account = limit_per_account
        self._limit_per_search = limit_per_search
        self._max_accounts = _resolve_max_accounts(max_accounts)
        self._accounts_only = accounts_only
        self._search_only = search_only

    @property
    def name(self) -> str:
        return "X Complement (twscrape)"

    @property
    def source_type(self) -> str:
        return "x"

    async def fetch(self, *, limit: int = 0) -> list[dict[str, Any]]:
        if not x_complement_enabled():
            print("  ⚠ X complement deshabilitado (X_COMPLEMENT_ENABLED=false)")
            return []

        if not _has_x_cookies():
            print(
                "  ⚠ X_COOKIES no configuradas — omitiendo complemento X",
                file=sys.stderr,
            )
            return []

        try:
            return await self._fetch_safe(limit=limit)
        except Exception as exc:
            print(
                f"  ⚠ X complement falló (ingesta de noticias sigue): {exc}",
                file=sys.stderr,
            )
            return []

    async def _fetch_safe(self, *, limit: int) -> list[dict[str, Any]]:
        api = await _setup_api()
        if api is None:
            print("  ⚠ No se pudo inicializar twscrape — omitiendo X", file=sys.stderr)
            return []

        records: list[dict[str, Any]] = []
        run_accounts = not self._search_only
        run_search = not self._accounts_only and (
            self._search_only or _x_search_enabled()
        )

        if run_accounts:
            accounts = FINANCIAL_ACCOUNTS[: self._max_accounts]
            for username in accounts:
                print(f"  → Timeline @{username} (límite: {self._limit_per_account})")
                try:
                    user = await api.user_by_login(username)
                    if user is None:
                        print(f"    ⚠ Usuario @{username} no encontrado")
                        continue
                    tweets = await gather(
                        api.user_tweets(user.id, limit=self._limit_per_account)
                    )
                    print(f"    ✓ {len(tweets)} tweets")
                    for tweet in tweets:
                        records.append(tweet_to_record(tweet, f"account:{username}"))
                except Exception as exc:
                    print(f"    ⚠ @{username}: {exc}", file=sys.stderr)
                    continue

        if run_search:
            for query in SEARCH_QUERIES:
                print(f"  → Búsqueda X: {query!r} (límite: {self._limit_per_search})")
                try:
                    tweets = await gather(
                        api.search(
                            query,
                            limit=self._limit_per_search,
                            kv={"product": "Latest"},
                        )
                    )
                    print(f"    ✓ {len(tweets)} tweets")
                    for tweet in tweets:
                        records.append(tweet_to_record(tweet, f"search:{query}"))
                except Exception as exc:
                    print(f"    ⚠ búsqueda falló: {exc}", file=sys.stderr)
                    continue

        if limit > 0 and len(records) > limit:
            records = records[:limit]

        return records
