"""Trigger Refresh de Ingestion (Worker --once)."""

from __future__ import annotations

import asyncio
import subprocess
import sys

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.app.schemas import IngestRefreshResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _build_worker_cmd(
    limit_per_account: int | None = None,
    limit_per_search: int | None = None,
    accounts_only: bool = False,
    search_only: bool = False,
    max_accounts: int | None = None,
    skip_embeddings: bool = False,
) -> list[str]:
    cmd = [sys.executable, "-m", "scraper.worker", "--once"]
    if limit_per_account is not None:
        cmd.extend(["--limit-per-account", str(limit_per_account)])
    if limit_per_search is not None:
        cmd.extend(["--limit-per-search", str(limit_per_search)])
    if accounts_only:
        cmd.append("--accounts-only")
    if search_only:
        cmd.append("--search-only")
    if max_accounts is not None:
        cmd.extend(["--max-accounts", str(max_accounts)])
    if skip_embeddings:
        cmd.append("--skip-embeddings")
    return cmd


def _run_worker(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=_project_root(), check=False)


def _project_root() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[3])


@router.post("/refresh", status_code=202, response_model=IngestRefreshResponse)
async def refresh_ingest(
    limit_per_account: int | None = Query(None, ge=1),
    limit_per_search: int | None = Query(None, ge=1),
    accounts_only: bool = False,
    search_only: bool = False,
    max_accounts: int | None = Query(None, ge=1),
    skip_embeddings: bool = False,
) -> JSONResponse:
    cmd = _build_worker_cmd(
        limit_per_account=limit_per_account,
        limit_per_search=limit_per_search,
        accounts_only=accounts_only,
        search_only=search_only,
        max_accounts=max_accounts,
        skip_embeddings=skip_embeddings,
    )
    asyncio.create_task(asyncio.to_thread(_run_worker, cmd))
    return JSONResponse(
        status_code=202,
        content=IngestRefreshResponse().model_dump(),
    )
