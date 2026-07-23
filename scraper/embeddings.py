"""Embedding Document y Vector Index para Signals."""

from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536


def build_embedding_document(record: dict[str, Any]) -> str:
    """Construye el Embedding Document: title + summary + body; fallback X (rawContent + article)."""
    parts: list[str] = []

    title = (record.get("title") or "").strip()
    summary = (record.get("summary") or "").strip()
    body = (record.get("body") or "").strip()

    if title:
        parts.append(title)
    if summary and summary != title:
        parts.append(summary)
    if body and body not in {title, summary}:
        parts.append(body)

    if parts:
        return "\n\n".join(parts)

    raw_content = (record.get("rawContent") or "").strip()
    if raw_content:
        parts.append(raw_content)

    article = record.get("article")
    if isinstance(article, dict):
        article_title = (article.get("title") or "").strip()
        description = (article.get("description") or "").strip()
        if article_title:
            parts.append(article_title)
        if description:
            parts.append(description)

    return "\n\n".join(parts)


class EmbeddingError(RuntimeError):
    """Fallo de embeddings (key ausente, cuota, red). No usa sys.exit."""


def _get_openai_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise EmbeddingError(
            "OPENAI_API_KEY no configurada en .env (requerida para Vector Index)."
        )
    return OpenAI(api_key=api_key)


def embed_texts_safe(texts: list[str]) -> list[list[float]] | None:
    """Genera embeddings en batch; devuelve None si falta API key o hay error."""
    if not texts:
        return []

    try:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None

        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
            dimensions=EMBEDDING_DIMS,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]
    except Exception as exc:  # noqa: BLE001 — degradación controlada
        print(
            f"Warning: embeddings OpenAI fallaron ({type(exc).__name__}); "
            "continuando sin Vector Index.",
            file=sys.stderr,
        )
        return None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Genera embeddings en batch vía OpenAI API. Raises EmbeddingError (no sys.exit)."""
    if not texts:
        return []

    result = embed_texts_safe(texts)
    if result is None:
        load_dotenv()
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise EmbeddingError(
                "OPENAI_API_KEY no configurada en .env (requerida para Vector Index)."
            )
        raise EmbeddingError("Falló la API de embeddings de OpenAI.")
    return result
