"""Copia signals del Store local (Docker :5433) a Supabase."""

from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Json

LOCAL_DSN = "postgresql://xscraper:xscraper@localhost:5433/xscraper"
BATCH_SIZE = 25

SELECT_SQL = """
SELECT
    id_str, published_at, username, raw_content, source,
    cashtags, hashtags, article,
    reply_count, retweet_count, like_count, quote_count, bookmarked_count,
    payload, embedding::text
FROM signals
ORDER BY published_at
"""

INSERT_SQL = """
INSERT INTO signals (
    id_str, published_at, username, raw_content, source,
    cashtags, hashtags, article,
    reply_count, retweet_count, like_count, quote_count, bookmarked_count,
    payload, embedding
) VALUES (
    %(id_str)s, %(published_at)s, %(username)s, %(raw_content)s, %(source)s,
    %(cashtags)s, %(hashtags)s, %(article)s,
    %(reply_count)s, %(retweet_count)s, %(like_count)s, %(quote_count)s,
    %(bookmarked_count)s, %(payload)s,
    %(embedding)s::vector
)
ON CONFLICT (id_str) DO NOTHING
"""


def _row_to_params(row: tuple) -> dict:
    embedding = row[14]
    return {
        "id_str": row[0],
        "published_at": row[1],
        "username": row[2],
        "raw_content": row[3],
        "source": row[4],
        "cashtags": row[5],
        "hashtags": row[6],
        "article": Json(row[7]) if row[7] is not None else None,
        "reply_count": row[8],
        "retweet_count": row[9],
        "like_count": row[10],
        "quote_count": row[11],
        "bookmarked_count": row[12],
        "payload": Json(row[13]),
        "embedding": embedding,
    }


def main() -> int:
    load_dotenv()
    remote_dsn = os.getenv("DATABASE_URL", "").strip()
    if not remote_dsn or "localhost:5433" in remote_dsn:
        print("DATABASE_URL debe apuntar a Supabase (pooler), no a local.")
        return 1

    print("== Migración signals: local → Supabase ==\n")

    try:
        with psycopg.connect(LOCAL_DSN) as local:
            with local.cursor() as lcur:
                lcur.execute("SELECT count(*) FROM signals")
                local_count = lcur.fetchone()[0]
    except psycopg.Error as exc:
        print(f"No se pudo conectar al Store local (:5433): {exc}")
        print("¿Está corriendo? → docker compose up -d")
        return 1

    print(f"Local: {local_count} signals")

    with psycopg.connect(remote_dsn) as remote:
        with remote.cursor() as rcur:
            rcur.execute("SELECT count(*) FROM signals")
            remote_before = rcur.fetchone()[0]
        print(f"Supabase (antes): {remote_before} signals\n")

        if local_count == 0:
            print("Nada que migrar.")
            return 0

        if remote_before > 0:
            print("Supabase ya tiene signals. Abortando para evitar duplicados.")
            print("Si querés reemplazar, vaciá la tabla en SQL Editor: TRUNCATE signals;")
            return 1

        with psycopg.connect(LOCAL_DSN) as local:
            with local.cursor() as lcur:
                lcur.execute(SELECT_SQL)
                rows = lcur.fetchall()

        print(f"Migrando {len(rows)} filas en lotes de {BATCH_SIZE}…")

        with remote.cursor() as rcur:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i : i + BATCH_SIZE]
                for row in batch:
                    rcur.execute(INSERT_SQL, _row_to_params(row))
                remote.commit()
                done = min(i + BATCH_SIZE, len(rows))
                print(f"  {done}/{len(rows)}")

        with remote.cursor() as rcur:
            rcur.execute("SELECT count(*) FROM signals")
            remote_count = rcur.fetchone()[0]
            rcur.execute("SELECT count(embedding) FROM signals")
            with_emb = rcur.fetchone()[0]

    print(f"\nSupabase (después): {remote_count} signals ({with_emb} con embedding)")
    print("== Migración OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
