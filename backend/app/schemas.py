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
    logo: str | None = None


class TickerLogo(BaseModel):
    symbol: str
    logo: str | None = None


class TickerSuggestion(BaseModel):
    symbol: str
    description: str = ""
    source: str = "finnhub"


class PriceCandle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    time: int | None = None


class PriceCandlesResponse(BaseModel):
    symbol: str
    period: str
    interval: str = "1d"
    candles: list[PriceCandle] = Field(default_factory=list)
    data_points: int = 0
    error: str | None = None


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


class DossierBlockContent(BaseModel):
    blocks: dict[str, str]
    sentiment_stats: dict[str, Any] | None = None


class DossierVersion(BaseModel):
    id: str
    symbol: str
    content: DossierBlockContent
    citations: list[ChatCitation] = Field(default_factory=list)
    created_at: datetime


class DossierRefreshResponse(BaseModel):
    version: DossierVersion


class ChartPlanAssessmentDimension(BaseModel):
    summary: str = ""
    stance: str | None = None
    findings: list[str] = Field(default_factory=list)


class ChartPlanAssessment(BaseModel):
    summary: str = ""
    visual: ChartPlanAssessmentDimension | dict[str, Any] | None = None
    narrative: ChartPlanAssessmentDimension | dict[str, Any] | None = None
    sentiment_vs_price: ChartPlanAssessmentDimension | dict[str, Any] | None = None
    multi_tf: ChartPlanAssessmentDimension | dict[str, Any] | None = None
    conflicts: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    bias_check: str = ""
    bullish_count: int | None = None
    bearish_count: int | None = None


class ChartPlanView(BaseModel):
    type: str
    enabled: bool = True
    interval: str | None = None
    rationale: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ChartPlanPineScript(BaseModel):
    title: str = ""
    purpose: str = ""
    limitations: str = ""
    code: str = ""


class ChartPlanChartData(BaseModel):
    sentiment_bars: list[dict[str, Any]] = Field(default_factory=list)
    signals_timeline: list[dict[str, Any]] = Field(default_factory=list)


class ChartPlanIndicatorReading(BaseModel):
    name: str = ""
    stance: str = "neutral"
    reading: str = ""
    tv_study: dict[str, Any] | None = None


class ChartPlanTradingViewStudy(BaseModel):
    id: str
    inputs: dict[str, Any] = Field(default_factory=dict)


class ChartPlanSmaSlot(BaseModel):
    enabled: bool = True
    length: int = 20


class ChartPlanDonchianSlot(BaseModel):
    enabled: bool = True
    period: int = 20


class ChartPlanSuggestedView(BaseModel):
    """Vista soft sugerida para el Ticker Chart (Operator-first, ADR-0011)."""

    interval: str = "1d"
    period: str = "1y"
    sma_a: ChartPlanSmaSlot | dict[str, Any] = Field(
        default_factory=lambda: ChartPlanSmaSlot(enabled=True, length=20)
    )
    sma_b: ChartPlanSmaSlot | dict[str, Any] = Field(
        default_factory=lambda: ChartPlanSmaSlot(enabled=True, length=50)
    )
    donchian: ChartPlanDonchianSlot | dict[str, Any] = Field(
        default_factory=lambda: ChartPlanDonchianSlot(enabled=True, period=20)
    )
    fib: bool = True
    volume: bool = True


class ChartPlanContent(BaseModel):
    timeframes: list[Any] = Field(default_factory=list)
    views: list[ChartPlanView | dict[str, Any]] = Field(default_factory=list)
    suggested_view: ChartPlanSuggestedView | dict[str, Any] | None = None
    pine_scripts: list[ChartPlanPineScript | dict[str, Any]] = Field(
        default_factory=list
    )
    indicator_readings: list[ChartPlanIndicatorReading | dict[str, Any]] = Field(
        default_factory=list
    )
    tradingview_studies: list[ChartPlanTradingViewStudy | dict[str, Any]] = Field(
        default_factory=list
    )
    assessment: ChartPlanAssessment | dict[str, Any]
    chart_data: ChartPlanChartData | dict[str, Any] | None = None
    summary: str | None = None
    vision_used: bool | None = None


class ChartPlanVersion(BaseModel):
    id: str
    symbol: str
    content: ChartPlanContent | dict[str, Any]
    dossier_version_id: str | None = None
    created_at: datetime


class ChartPlanAnalyzeResponse(BaseModel):
    version: ChartPlanVersion


class ChartPlanAnalyzeRequest(BaseModel):
    """Body opcional del analyze: captura real del Ticker Chart para visión."""

    chart_image_base64: str | None = None
    chart_image_media_type: str = "image/png"
    # Vista Operator al momento de capturar (prefs del Ticker Chart).
    chart_view: dict[str, Any] | None = None
