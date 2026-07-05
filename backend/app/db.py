"""Acceso al Store (Postgres). Conexión desde DATABASE_URL."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DSN = "postgresql://xscraper:xscraper@localhost:5433/xscraper"


def get_dsn() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DSN).strip() or DEFAULT_DSN


def _connect_kwargs(dsn: str) -> dict:
    """PgBouncer (Supabase transaction pooler) no soporta prepared statements."""
    lowered = dsn.lower()
    if "pooler" in lowered or ":6543/" in lowered or ":6543?" in lowered:
        return {"prepare_threshold": None}
    return {}


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """Conexión al Store con commit/rollback automático."""
    dsn = get_dsn()
    conn = psycopg.connect(dsn, **_connect_kwargs(dsn))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
