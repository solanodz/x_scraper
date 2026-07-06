"""Pydantic schemas para la API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Engagement(BaseModel):
    reply_count: int = 0
    retweet_count: int = 0
    like_count: int = 0
    quote_count: int = 0
    bookmarked_count: int = 0


class ClusterSource(BaseModel):
    id_str: str
    source_type: str = "x"
    username: str = ""


class SignalSummary(BaseModel):
    id_str: str
    published_at: datetime
    username: str
    raw_content: str
    source: str
    cashtags: list[str] = Field(default_factory=list)
    url: str
    engagement: Engagement
    source_type: str = "x"
    title: str | None = None
    summary: str | None = None
    body: str | None = None
    canonical_url: str | None = None
    relevance_score: float | None = None
    topic: str | None = None
    sentiment: str | None = None
    cluster_id: str | None = None
    cluster_sources: list[ClusterSource] = Field(default_factory=list)


class SignalDetail(SignalSummary):
    hashtags: list[str] = Field(default_factory=list)
    article: dict[str, Any] | None = None
    payload: dict[str, Any]


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: str | None = None


class BriefingRequest(BaseModel):
    session_id: str | None = None


class ChatCitation(BaseModel):
    id_str: str
    username: str
    url: str
    excerpt: str


class ChatMessageRecord(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    citations: list[ChatCitation] | None = None
    created_at: datetime


class ChatSessionSummary(BaseModel):
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatSessionCreate(BaseModel):
    title: str | None = None


class SignalCountResponse(BaseModel):
    total: int = Field(ge=0)


class IngestRefreshResponse(BaseModel):
    status: str = "started"


class Quote(BaseModel):
    symbol: str
    price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    timestamp: datetime | None = None
    delayed: bool = True
    available: bool = True


class TickerSuggestion(BaseModel):
    symbol: str
    description: str = ""
    source: str = "finnhub"


class TickerWatchEntry(BaseModel):
    id: str
    symbol: str
    note: str | None = None
    created_at: datetime


class TickerWatchAddRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    note: str | None = None


class TickerWatchUpdateRequest(BaseModel):
    note: str | None = Field(default=None, max_length=280)
