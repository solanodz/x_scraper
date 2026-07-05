"""Filtro de relevancia para Signals (Ingestion + Feed + RAG)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from scraper.sources import FINANCIAL_ACCOUNTS

# Keywords orientadas a mercados (sin war/conflict/crisis — generan falsos positivos).
DEFAULT_KEYWORDS = (
    "stock,stocks,market,markets,earnings,ticker,fed,inflation,rates,GDP,tariff,"
    "tariffs,oil,gold,bond,yield,IPO,merger,acquisition,SEC,ECB,NYSE,NASDAQ,"
    "S&P,SPX,bitcoin,crypto,forex,dollar,euro,recession,CPI,FOMC,"
    "sanction,commodity,energy,bank,profit,revenue,forecast,dividend,analyst,"
    "ETF,futures,volatility,VIX,debt,fiscal,monetary,Argentina,LatAm,Latinoamérica,"
    "peso,central bank,interest rate,economy,economic,finance,financial,"
    "trading,investor,investment,portfolio,quarter,guidance,outlook,"
    "opec,crude,petróleo,acciones,mercado,bonos,inflación,banco,gdp,pmi,"
    "jobs report,rate cut,rate hike,central bank,monetary policy,trade deficit,"
    "current account,balance sheet,share price,stock price,equity,benchmark"
)

# Humanitario / conflicto sin ángulo de mercado — aplica a X, RSS y News APIs.
DEFAULT_TOPIC_BLOCKLIST = (
    "conflict is driving,driving hunger,food insecurity,hunger crisis,WFP,UNOCHA,"
    "UN_HRC,humanitarian aid,humanitarian crisis,civilians were killed,civilian casualties,"
    "civilian deaths,refugee crisis,internally displaced,displaced persons,"
    "human rights catastrophe,peacekeeping mission,ceasefire agreement,aid workers,"
    "relief convoy,cholera outbreak,measles outbreak,malaria outbreak,"
    "gender-based violence,sexual violence,landmine clearance,mass grave,"
    "war crime,ethnic cleansing,children are adopting,schools destroyed,"
    "hospital bombed,aid delivery,food aid,sanitation crisis,water shortage,"
    "RT @WFP,RT @UNOCHA,RT @UN_HRC,not seen in nearly a decade"
)

DEFAULT_BLOCKLIST = (
    "giveaway,airdrop,free money,click here,subscribe now,promo code,discount code,"
    "guaranteed returns,OnlyFans,casino,sports betting,World Cup score,NFL pick,"
    "celebrity gossip,meme coin,pump and dump,100x gem,DM me,link in bio,"
    "follow for follow,like for like,retweet to win,concursosorteo,"
    "worst president,who is worse,hot take unpopular,culture war,own the libs,"
    "triggered libs,make america great again,vote blue,vote red,ballot box"
)


@dataclass(frozen=True)
class SignalFilterConfig:
    mode: str
    keywords: tuple[str, ...]
    blocklist: tuple[str, ...]
    topic_blocklist: tuple[str, ...]
    trusted_sources: tuple[str, ...]
    min_likes: int
    require_link: bool


def _parse_csv(raw: str) -> tuple[str, ...]:
    items: list[str] = []
    for part in raw.split(","):
        value = part.strip()
        if value and value not in items:
            items.append(value)
    return tuple(items)


def get_filter_config() -> SignalFilterConfig:
    load_dotenv()
    mode = os.getenv("SIGNAL_FILTER", "relevant").strip().lower() or "relevant"
    keywords = _parse_csv(os.getenv("SIGNAL_KEYWORDS", DEFAULT_KEYWORDS))
    blocklist = _parse_csv(os.getenv("SIGNAL_BLOCKLIST", DEFAULT_BLOCKLIST))
    topic_blocklist = _parse_csv(
        os.getenv("SIGNAL_TOPIC_BLOCKLIST", DEFAULT_TOPIC_BLOCKLIST)
    )
    trusted_raw = os.getenv("SIGNAL_TRUSTED_SOURCES", "").strip()
    trusted = _parse_csv(trusted_raw) if trusted_raw else tuple(FINANCIAL_ACCOUNTS)
    min_likes_raw = os.getenv("SIGNAL_MIN_LIKES", "0").strip()
    min_likes = int(min_likes_raw) if min_likes_raw.isdigit() else 0
    require_link = os.getenv("SIGNAL_REQUIRE_LINK", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return SignalFilterConfig(
        mode=mode,
        keywords=keywords,
        blocklist=blocklist,
        topic_blocklist=topic_blocklist,
        trusted_sources=trusted,
        min_likes=max(min_likes, 0),
        require_link=require_link,
    )


def _regex_pattern(terms: tuple[str, ...]) -> str | None:
    if not terms:
        return None
    return "|".join(re.escape(term) for term in terms)


def _content_matches_any(content: str, terms: tuple[str, ...]) -> bool:
    lowered = content.lower()
    return any(term.lower() in lowered for term in terms)


def _record_username(record: dict[str, Any]) -> str:
    user = record.get("user") or {}
    return str(user.get("username") or "")


def _record_cashtags(record: dict[str, Any]) -> list[str]:
    raw = record.get("cashtags") or []
    return [str(tag) for tag in raw if str(tag).strip()]


def _record_has_link(record: dict[str, Any]) -> bool:
    if record.get("article"):
        return True
    content = str(record.get("rawContent") or "")
    return bool(re.search(r"https?://", content, re.IGNORECASE))


def _row_has_link(row: dict[str, Any]) -> bool:
    if row.get("article"):
        return True
    content = str(row.get("raw_content") or "")
    return bool(re.search(r"https?://", content, re.IGNORECASE))


def _is_topic_noise(content: str, config: SignalFilterConfig) -> bool:
    """Tema humanitario/geopolítico sin señal de mercado."""
    if not config.topic_blocklist:
        return False
    if not _content_matches_any(content, config.topic_blocklist):
        return False
    # Permitir si igual menciona mercados explícitamente (ej. oil surge on Ukraine).
    return not _content_matches_any(content, config.keywords)


def _is_relevant_x_record(
    *,
    username: str,
    content: str,
    cashtags: list[str],
    likes: int,
    has_link: bool,
    config: SignalFilterConfig,
) -> bool:
    """Reglas para X (complemento): no pasar keyword suelta de cuentas random."""
    if _content_matches_any(content, config.blocklist):
        return False
    if _is_topic_noise(content, config):
        return False
    if config.min_likes > 0 and likes < config.min_likes:
        return False
    if config.require_link and not has_link:
        return False

    if config.mode == "off":
        return True
    if config.mode == "cashtag":
        return len(cashtags) > 0

    has_cashtag = len(cashtags) > 0
    is_trusted = username in config.trusted_sources
    has_keyword = _content_matches_any(content, config.keywords)

    if has_cashtag:
        return True
    if is_trusted and has_keyword:
        return True
    if config.mode == "strict":
        return False

    # relevant (default): X endurecido — sin keyword/link suelto de no-trusted
    return False


def _record_text(record: dict[str, Any]) -> str:
    parts = [
        record.get("title"),
        record.get("summary"),
        record.get("rawContent"),
    ]
    return " ".join(str(part) for part in parts if part)


def _row_text(row: dict[str, Any]) -> str:
    parts = [row.get("title"), row.get("summary"), row.get("raw_content")]
    return " ".join(str(part) for part in parts if part)


def _is_relevant_record(record: dict[str, Any], config: SignalFilterConfig) -> bool:
    text = _record_text(record)
    if _is_topic_noise(text, config):
        return False

    source_type = str(record.get("source_type") or "x")
    if source_type in ("alpha_vantage", "rss", "marketaux"):
        summary = str(record.get("summary") or "").strip()
        title = str(record.get("title") or "").strip()
        return bool(summary or title)

    return _is_relevant_x_record(
        username=_record_username(record),
        content=str(record.get("rawContent") or ""),
        cashtags=_record_cashtags(record),
        likes=int(record.get("likeCount") or 0),
        has_link=_record_has_link(record),
        config=config,
    )


def _is_relevant_row(row: dict[str, Any], config: SignalFilterConfig) -> bool:
    if _is_topic_noise(_row_text(row), config):
        return False

    source_type = str(row.get("source_type") or "x")
    if source_type != "x":
        title = str(row.get("title") or "").strip()
        summary = str(row.get("summary") or "").strip()
        return bool(title and summary)

    return _is_relevant_x_record(
        username=str(row.get("username") or ""),
        content=str(row.get("raw_content") or ""),
        cashtags=list(row.get("cashtags") or []),
        likes=int(row.get("like_count") or 0),
        has_link=_row_has_link(row),
        config=config,
    )


def filter_records(
    records: list[dict[str, Any]],
    config: SignalFilterConfig | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Filtra registros de Ingestion. Devuelve (aceptados, descartados)."""
    cfg = config or get_filter_config()
    if cfg.mode == "off" and cfg.min_likes == 0 and not cfg.blocklist:
        return records, 0

    accepted: list[dict[str, Any]] = []
    skipped = 0
    for record in records:
        if _is_relevant_record(record, cfg):
            accepted.append(record)
        else:
            skipped += 1
    return accepted, skipped


def build_sql_filter(
    config: SignalFilterConfig | None = None,
) -> tuple[str, dict[str, Any]]:
    """Genera cláusula SQL AND para filtrar Signals en el Store."""
    cfg = config or get_filter_config()
    clauses: list[str] = []
    params: dict[str, Any] = {}

    blocklist_re = _regex_pattern(cfg.blocklist)
    if blocklist_re:
        clauses.append("NOT (raw_content ~* %(blocklist_re)s)")
        params["blocklist_re"] = blocklist_re

    topic_re = _regex_pattern(cfg.topic_blocklist)
    if topic_re:
        keywords_re_for_topic = _regex_pattern(cfg.keywords)
        if keywords_re_for_topic:
            params["keywords_re"] = keywords_re_for_topic
            clauses.append(
                "NOT ("
                "(COALESCE(title, '') || ' ' || COALESCE(summary, '') || ' ' || raw_content) ~* %(topic_re)s "
                f"AND NOT (COALESCE(title, '') || ' ' || COALESCE(summary, '') || ' ' || raw_content) ~* %(keywords_re)s"
                ")"
            )
        else:
            clauses.append(
                "NOT ((COALESCE(title, '') || ' ' || COALESCE(summary, '') || ' ' || raw_content) ~* %(topic_re)s)"
            )
        params["topic_re"] = topic_re

    if cfg.min_likes > 0:
        clauses.append("like_count >= %(min_likes)s")
        params["min_likes"] = cfg.min_likes

    if cfg.mode == "off":
        return (" AND ".join(clauses) if clauses else "TRUE"), params

    if cfg.require_link:
        clauses.append(
            "(article IS NOT NULL OR raw_content ~* 'https?://')"
        )

    if cfg.mode == "cashtag":
        clauses.append(
            "(cardinality(cashtags) > 0 OR cardinality(tickers) > 0)"
        )
        return " AND ".join(clauses), params

    news_pass = (
        "(source_type <> 'x' AND title IS NOT NULL AND summary IS NOT NULL "
        "AND length(trim(summary)) > 0)"
    )

    if cfg.trusted_sources:
        params["trusted_sources"] = list(cfg.trusted_sources)

    keywords_re = _regex_pattern(cfg.keywords)
    if keywords_re:
        params["keywords_re"] = keywords_re

    trusted_clause = "username = ANY(%(trusted_sources)s)" if cfg.trusted_sources else "FALSE"
    keyword_clause = "raw_content ~* %(keywords_re)s" if keywords_re else "FALSE"
    clauses.append(
        f"({news_pass} OR cardinality(cashtags) > 0 "
        f"OR ({trusted_clause} AND {keyword_clause}))"
    )

    from scraper.relevance import feed_min_relevance

    min_rel = feed_min_relevance()
    if min_rel is not None:
        clauses.append(
            "(relevance_score IS NULL OR relevance_score >= %(min_relevance)s)"
        )
        params["min_relevance"] = min_rel

    return " AND ".join(clauses), params
