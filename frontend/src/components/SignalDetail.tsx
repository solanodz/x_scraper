"use client";

import { useEffect, useState } from "react";
import TickerLogo from "@/components/TickerLogo";
import { fetchQuotes, fetchSignal } from "@/lib/api";
import { formatEngagement, timeAgo } from "@/lib/format";
import {
  clusterSourcesLabel,
  displayAuthor,
  externalLinkHref,
  externalLinkLabel,
  isXSignal,
  linkedArticleLabel,
  sourceBadgeLabel,
} from "@/lib/signalSource";
import type { Quote, SignalDetail as SignalDetailType } from "@/lib/types";

interface SignalDetailProps {
  idStr: string | null;
}

/** True when Article Body is real content, not a summary echo. */
function hasFullArticleBody(
  body?: string | null,
  summary?: string | null,
): boolean {
  const trimmedBody = body?.trim() ?? "";
  if (!trimmedBody) return false;

  const trimmedSummary = summary?.trim() ?? "";
  if (trimmedSummary && trimmedBody === trimmedSummary) return false;

  // Meaningful length, or clearly longer than the summary when both exist.
  if (trimmedBody.length >= 200) return true;
  if (trimmedSummary && trimmedBody.length > trimmedSummary.length * 1.5) {
    return true;
  }
  return false;
}

export default function SignalDetail({ idStr }: SignalDetailProps) {
  const [signal, setSignal] = useState<SignalDetailType | null>(null);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [heroBroken, setHeroBroken] = useState(false);

  useEffect(() => {
    if (!idStr) {
      setSignal(null);
      setQuotes([]);
      setError(null);
      setHeroBroken(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    setHeroBroken(false);

    fetchSignal(idStr)
      .then((data) => {
        if (!cancelled) setSignal(data);
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load signal");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [idStr]);

  useEffect(() => {
    if (!signal?.cashtags.length) {
      setQuotes([]);
      return;
    }

    let cancelled = false;

    fetchQuotes(signal.cashtags)
      .then((data) => {
        if (!cancelled) setQuotes(data);
      })
      .catch(() => {
        if (!cancelled) setQuotes([]);
      });

    return () => {
      cancelled = true;
    };
  }, [signal?.cashtags]);

  const articleTitle =
    signal?.article && typeof signal.article.title === "string"
      ? signal.article.title
      : null;
  const articleDescription =
    signal?.article && typeof signal.article.description === "string"
      ? signal.article.description
      : null;
  const articleUrl =
    signal?.article && typeof signal.article.url === "string"
      ? signal.article.url
      : null;

  const isX = signal ? isXSignal(signal.source_type) : true;
  const hasFullBody =
    !isX && signal
      ? hasFullArticleBody(signal.body, signal.summary)
      : false;
  const newsReadingText = !isX
    ? hasFullBody
      ? (signal?.body?.trim() ?? "")
      : signal?.summary?.trim() ||
        signal?.body?.trim() ||
        signal?.raw_content ||
        ""
    : "";

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-900">
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800 px-3 py-1.5">
        <h2 className="font-sans text-xs font-semibold uppercase tracking-wider text-amber-500">
          Signal Detail
        </h2>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-4">
        {!idStr && (
          <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
            <p className="font-mono text-xs text-zinc-500">
              Seleccioná un Signal del Feed.
            </p>
          </div>
        )}
        {loading && (
          <p className="font-mono text-xs text-zinc-500">Loading…</p>
        )}
        {error && (
          <p className="font-mono text-xs text-red-400">{error}</p>
        )}
        {signal && (
          <div className="space-y-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono text-sm font-semibold text-amber-400">
                {displayAuthor(signal.username, signal.source_type)}
              </span>
              <span className="font-mono text-[10px] text-zinc-500">
                {timeAgo(signal.published_at)}
              </span>
            </div>

            {!isX && signal.title?.trim() && (
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-sans text-sm font-semibold leading-snug text-zinc-100">
                    {signal.title.trim()}
                  </h3>
                  {hasFullBody ? (
                    <span className="shrink-0 rounded border border-emerald-800/40 bg-emerald-950/25 px-1.5 py-0.5 font-sans text-[10px] font-medium text-emerald-400/90">
                      Artículo completo
                    </span>
                  ) : (
                    <span className="shrink-0 rounded border border-zinc-700 bg-zinc-800/60 px-1.5 py-0.5 font-sans text-[10px] font-medium text-zinc-400">
                      Solo summary
                    </span>
                  )}
                </div>
              </div>
            )}

            {!isX && !signal.title?.trim() && (
              <div>
                {hasFullBody ? (
                  <span className="inline-block rounded border border-emerald-800/40 bg-emerald-950/25 px-1.5 py-0.5 font-sans text-[10px] font-medium text-emerald-400/90">
                    Artículo completo
                  </span>
                ) : (
                  <span className="inline-block rounded border border-zinc-700 bg-zinc-800/60 px-1.5 py-0.5 font-sans text-[10px] font-medium text-zinc-400">
                    Solo summary
                  </span>
                )}
              </div>
            )}

            {!isX && signal.image_url && !heroBroken && (
              // eslint-disable-next-line @next/next/no-img-element -- hotlinked publisher URLs; not in next/image remotePatterns
              <img
                src={signal.image_url}
                alt=""
                loading="lazy"
                decoding="async"
                onError={() => setHeroBroken(true)}
                className="max-h-56 w-full rounded-md object-cover"
              />
            )}

            {signal.cluster_sources && signal.cluster_sources.length > 1 && (
              <div className="rounded border border-amber-900/40 bg-amber-950/20 px-2 py-1.5">
                <p className="font-sans text-[10px] font-semibold uppercase tracking-wide text-amber-600">
                  Story Cluster
                </p>
                <p className="mt-1 font-mono text-[11px] text-zinc-300">
                  {clusterSourcesLabel(signal.cluster_sources)}
                </p>
                <ul className="mt-1 space-y-0.5">
                  {signal.cluster_sources.map((member) => (
                    <li
                      key={member.id_str}
                      className="font-mono text-[10px] text-zinc-500"
                    >
                      {sourceBadgeLabel(member.source_type)} ·{" "}
                      {displayAuthor(member.username, member.source_type)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {isX ? (
              <p className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-zinc-200">
                {signal.raw_content}
              </p>
            ) : (
              <div className="space-y-3">
                {newsReadingText && (
                  <p className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-zinc-200">
                    {newsReadingText}
                  </p>
                )}
                {!hasFullBody && (
                  <a
                    href={externalLinkHref(signal)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center font-sans text-sm font-medium text-amber-500 hover:text-amber-400"
                  >
                    Leer en la fuente →
                  </a>
                )}
              </div>
            )}

            {signal.cashtags.length > 0 && (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-2">
                  {signal.cashtags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded border border-emerald-800/50 bg-emerald-950/30 px-1.5 py-0.5 font-mono text-[10px] text-emerald-400"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                {quotes.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {quotes.map((quote) => (
                      <CashtagQuoteCard key={quote.symbol} quote={quote} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {isX && articleTitle && (
              <a
                href={articleUrl ?? signal.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded border border-zinc-700 bg-zinc-950 p-3 transition-colors hover:border-amber-700"
              >
                <p className="font-sans text-[10px] font-semibold uppercase tracking-wide text-amber-600">
                  {linkedArticleLabel()}
                </p>
                <p className="mt-1 font-sans text-xs font-semibold text-zinc-200">
                  {articleTitle}
                </p>
                {articleDescription && (
                  <p className="mt-1 font-mono text-[11px] leading-relaxed text-zinc-500">
                    {articleDescription}
                  </p>
                )}
              </a>
            )}

            {isX && (
              <div className="grid grid-cols-3 gap-2 border-t border-zinc-800 pt-3">
                <Stat label="Likes" value={signal.engagement.like_count} />
                <Stat
                  label="Retweets"
                  value={signal.engagement.retweet_count}
                />
                <Stat label="Replies" value={signal.engagement.reply_count} />
              </div>
            )}

            {(isX || hasFullBody) && (
              <a
                href={externalLinkHref(signal)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block font-mono text-[11px] text-amber-600 hover:text-amber-400"
              >
                {externalLinkLabel(signal.source_type)} →
              </a>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function CashtagQuoteCard({ quote }: { quote: Quote }) {
  if (quote.price == null) return null;

  const positive = (quote.change_percent ?? 0) >= 0;
  const colorClass = positive ? "text-emerald-400" : "text-red-400";

  return (
    <div className="flex items-center gap-1.5 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 font-mono text-[10px]">
      <TickerLogo symbol={quote.symbol} logoUrl={quote.logo} size="xs" />
      <span className="font-semibold text-zinc-300">{quote.symbol}</span>
      <span className="text-zinc-100">${quote.price.toFixed(2)}</span>
      <span className={colorClass}>
        {(quote.change_percent ?? 0) >= 0 ? "+" : ""}
        {(quote.change_percent ?? 0).toFixed(2)}%
      </span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <p className="font-mono text-sm text-zinc-200">
        {formatEngagement(value)}
      </p>
      <p className="font-sans text-[10px] text-zinc-500">{label}</p>
    </div>
  );
}
