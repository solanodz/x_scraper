#!/usr/bin/env python3
"""
Extracción de ejemplo de noticias financieras y globales desde X.

Punto de entrada legacy; delega en scraper.ingest (persistencia en Store).

Requisitos:
  - Python 3.10+
  - pip install -r requirements.txt
  - Archivo .env con X_COOKIES y DATABASE_URL (ver .env.example)

Uso:
  python scrape_example.py
  python scrape_example.py --limit-per-account 5 --limit-per-search 10
  python scrape_example.py --accounts-only
  python scrape_example.py --search-only
"""

from __future__ import annotations

import asyncio

from scraper.ingest import main

if __name__ == "__main__":
    asyncio.run(main())
