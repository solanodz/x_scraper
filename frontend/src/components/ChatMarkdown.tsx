"use client";

import { isValidElement, useMemo } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  alignmentSentiment,
  briefingSectionTitleClass,
  briefingSectionWrapperClass,
  briefingSubheadingClass,
  isDeltaSection,
  isPrioritySection,
  sentimentBlockClass,
  sentimentFromText,
  sentimentParagraphClass,
  sentimentTextClass,
  splitBriefingSections,
  stripSentimentMarker,
} from "@/lib/briefingMarkdown";
import type { ChatCitation } from "@/lib/types";
import { colorizeSignedPrices } from "@/lib/signedPriceText";

/** ISO FX codes are not Tickers — never open Dossier/Chart Plan for them. */
const FX_CURRENCY_CODES = new Set([
  "USD",
  "ARS",
  "EUR",
  "GBP",
  "JPY",
  "BRL",
  "CNY",
  "MXN",
  "CLP",
  "UYU",
  "CAD",
  "AUD",
  "CHF",
  "NZD",
]);

function isFxCurrencyCode(symbol: string): boolean {
  return FX_CURRENCY_CODES.has(symbol.trim().toUpperCase());
}

interface ChatMarkdownProps {
  content: string;
  streaming?: boolean;
  citations?: ChatCitation[];
  onCitationClick?: (idStr: string) => void;
  onDossierClick?: (symbol: string) => void;
  variant?: "default" | "briefing";
}

const linkClassName =
  "text-amber-400 underline decoration-amber-800/60 underline-offset-2 transition-colors hover:text-amber-300";

const briefingLinkClassName =
  "text-zinc-400 underline decoration-zinc-600/50 underline-offset-2 transition-colors hover:text-zinc-300";

function citationUrlIndex(citations: ChatCitation[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const citation of citations) {
    map.set(citation.url, citation.id_str);
    const trimmed = citation.url.replace(/\/$/, "");
    if (trimmed !== citation.url) {
      map.set(trimmed, citation.id_str);
    }
  }
  return map;
}

function nodeText(node: React.ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (isValidElement<{ children?: React.ReactNode }>(node)) {
    return nodeText(node.props.children);
  }
  return "";
}

function renderSentimentText(
  children: React.ReactNode,
  raw: string,
): React.ReactNode {
  if (sentimentFromText(raw) && typeof children === "string") {
    return stripSentimentMarker(raw);
  }
  return children;
}

function createBaseComponents(
  urlToId: Map<string, string>,
  onCitationClick?: (idStr: string) => void,
  onDossierClick?: (symbol: string) => void,
): Components {
  return {
    h1: ({ children }) => (
      <h1 className="mb-2 mt-3 font-sans text-sm font-semibold text-zinc-100 first:mt-0">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="mb-2 mt-3 font-sans text-xs font-semibold uppercase tracking-wide text-amber-500/90 first:mt-0">
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="mb-1.5 mt-2.5 font-sans text-xs font-semibold text-zinc-200 first:mt-0">
        {children}
      </h3>
    ),
    p: ({ children }) => (
      <p className="mb-2 leading-relaxed text-zinc-200 last:mb-0">
        {colorizeSignedPrices(children)}
      </p>
    ),
    strong: ({ children }) => (
      <strong className="font-semibold text-zinc-50">
        {colorizeSignedPrices(children)}
      </strong>
    ),
    em: ({ children }) => (
      <em className="text-zinc-300">{colorizeSignedPrices(children)}</em>
    ),
    ul: ({ children }) => (
      <ul className="mb-2 list-disc space-y-1 pl-4 text-zinc-200 last:mb-0">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="mb-2 list-decimal space-y-1 pl-4 text-zinc-200 last:mb-0">
        {children}
      </ol>
    ),
    li: ({ children }) => (
      <li className="leading-relaxed">{colorizeSignedPrices(children)}</li>
    ),
    a: ({ href, children }) => {
      if (href?.startsWith("dossier:") && onDossierClick) {
        const symbol = href.slice("dossier:".length).trim().toUpperCase();
        if (symbol && isFxCurrencyCode(symbol)) {
          return <span className="font-mono text-zinc-400">{children}</span>;
        }
        if (symbol) {
          return (
            <button
              type="button"
              onClick={() => onDossierClick(symbol)}
              title={`Abrir Dossier de ${symbol}`}
              className={`${linkClassName} cursor-pointer bg-transparent p-0 font-inherit`}
            >
              {children}
            </button>
          );
        }
      }

      const normalized = href?.replace(/\/$/, "") ?? "";
      const idStr =
        (href ? urlToId.get(href) : undefined) ??
        (normalized ? urlToId.get(normalized) : undefined);

      if (idStr && onCitationClick) {
        return (
          <button
            type="button"
            onClick={() => onCitationClick(idStr)}
            title="Abrir Signal en Terminal"
            className={`${linkClassName} cursor-pointer bg-transparent p-0 font-inherit`}
          >
            {children}
          </button>
        );
      }

      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className={linkClassName}
        >
          {children}
        </a>
      );
    },
    blockquote: ({ children }) => (
      <blockquote className="mb-2 border-l-2 border-zinc-700 pl-3 text-zinc-400 last:mb-0">
        {children}
      </blockquote>
    ),
    hr: () => <hr className="my-3 border-zinc-800" />,
    code: ({ className, children }) => {
      const isBlock = className?.includes("language-");
      if (isBlock) {
        return (
          <code className="block overflow-x-auto rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5 font-mono text-[11px] text-emerald-300/90">
            {children}
          </code>
        );
      }
      return (
        <code className="rounded bg-zinc-800 px-1 py-0.5 font-mono text-[11px] text-emerald-300/90">
          {children}
        </code>
      );
    },
    pre: ({ children }) => (
      <pre className="mb-2 overflow-x-auto rounded border border-zinc-800 bg-zinc-950 p-2 last:mb-0">
        {children}
      </pre>
    ),
    table: ({ children }) => (
      <div className="mb-3 overflow-x-auto rounded-md border border-zinc-800 last:mb-0">
        <table className="w-full min-w-[16rem] border-collapse font-mono text-[11px] leading-snug text-zinc-200">
          {children}
        </table>
      </div>
    ),
    thead: ({ children }) => (
      <thead className="bg-zinc-900/90 text-zinc-400">{children}</thead>
    ),
    tbody: ({ children }) => (
      <tbody className="[&_tr:nth-child(even)]:bg-zinc-950/60">{children}</tbody>
    ),
    th: ({ children }) => (
      <th className="whitespace-nowrap border-b border-zinc-700 px-2.5 py-1.5 text-left font-semibold">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="border-t border-zinc-800/80 px-2.5 py-1.5 align-top text-zinc-300">
        {colorizeSignedPrices(children)}
      </td>
    ),
  };
}

function createBriefingComponents(
  urlToId: Map<string, string>,
  onCitationClick?: (idStr: string) => void,
  onDossierClick?: (symbol: string) => void,
  inDeltaSection = false,
  inPrioritySection = false,
): Components {
  const base = createBaseComponents(urlToId, onCitationClick, onDossierClick);

  return {
    ...base,
    a: ({ href, children }) => {
      if (href?.startsWith("dossier:") && onDossierClick) {
        const symbol = href.slice("dossier:".length).trim().toUpperCase();
        if (symbol && isFxCurrencyCode(symbol)) {
          return <span className="font-mono text-zinc-400">{children}</span>;
        }
        if (symbol) {
          return (
            <button
              type="button"
              onClick={() => onDossierClick(symbol)}
              title={`Abrir Dossier de ${symbol}`}
              className={`${briefingLinkClassName} cursor-pointer bg-transparent p-0 font-inherit`}
            >
              {children}
            </button>
          );
        }
      }

      const normalized = href?.replace(/\/$/, "") ?? "";
      const idStr =
        (href ? urlToId.get(href) : undefined) ??
        (normalized ? urlToId.get(normalized) : undefined);

      if (idStr && onCitationClick) {
        return (
          <button
            type="button"
            onClick={() => onCitationClick(idStr)}
            title="Abrir Signal en Terminal"
            className={`${briefingLinkClassName} cursor-pointer bg-transparent p-0 font-inherit`}
          >
            {children}
          </button>
        );
      }

      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className={briefingLinkClassName}
        >
          {children}
        </a>
      );
    },
    h3: ({ children }) => {
      const label = nodeText(children);
      return (
        <h3
          className={briefingSubheadingClass(
            label,
            inDeltaSection,
            inPrioritySection,
          )}
        >
          {children}
        </h3>
      );
    },
    p: ({ children }) => {
      const raw = nodeText(children);
      return (
        <p className={sentimentParagraphClass(raw)}>
          {colorizeSignedPrices(renderSentimentText(children, raw))}
        </p>
      );
    },
    ul: ({ children }) => (
      <ul className="mb-2 list-none space-y-1.5 pl-0 last:mb-0">{children}</ul>
    ),
    strong: ({ children }) => {
      const text = nodeText(children);
      const sentiment = alignmentSentiment(text);
      if (sentiment === "positive") {
        return (
          <strong className={`font-semibold ${sentimentTextClass.positive}`}>
            {colorizeSignedPrices(children)}
          </strong>
        );
      }
      if (sentiment === "negative") {
        return (
          <strong className={`font-semibold ${sentimentTextClass.negative}`}>
            {colorizeSignedPrices(children)}
          </strong>
        );
      }
      return (
        <strong className="font-semibold text-zinc-300">
          {colorizeSignedPrices(children)}
        </strong>
      );
    },
    li: ({ children }) => {
      const raw = nodeText(children);
      const marker = sentimentFromText(raw);
      if (marker === "positive") {
        return (
          <li
            className={`mb-1.5 leading-relaxed ${sentimentBlockClass.positive} ${sentimentTextClass.positive}`}
          >
            {colorizeSignedPrices(renderSentimentText(children, raw))}
          </li>
        );
      }
      if (marker === "negative") {
        return (
          <li
            className={`mb-1.5 leading-relaxed ${sentimentBlockClass.negative} ${sentimentTextClass.negative}`}
          >
            {colorizeSignedPrices(renderSentimentText(children, raw))}
          </li>
        );
      }
      return (
        <li className="leading-relaxed text-zinc-200 pl-4 before:mr-2 before:text-zinc-600 before:content-['•']">
          {colorizeSignedPrices(children)}
        </li>
      );
    },
  };
}

function BriefingSectionBlock({
  title,
  body,
  urlToId,
  onCitationClick,
  onDossierClick,
}: {
  title: string;
  body: string;
  urlToId: Map<string, string>;
  onCitationClick?: (idStr: string) => void;
  onDossierClick?: (symbol: string) => void;
}) {
  const wrapperClass = briefingSectionWrapperClass(title);
  const delta = isDeltaSection(title);
  const priority = isPrioritySection(title);
  const components = createBriefingComponents(
    urlToId,
    onCitationClick,
    onDossierClick,
    delta,
    priority,
  );

  const inner = (
    <>
      <h2 className={briefingSectionTitleClass(title)}>{title}</h2>
      {body ? (
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {body}
        </ReactMarkdown>
      ) : null}
    </>
  );

  if (wrapperClass) {
    return <section className={wrapperClass}>{inner}</section>;
  }

  return <section className="mb-2">{inner}</section>;
}

export default function ChatMarkdown({
  content,
  streaming,
  citations,
  onCitationClick,
  onDossierClick,
  variant = "default",
}: ChatMarkdownProps) {
  const urlToId = useMemo(
    () => citationUrlIndex(citations ?? []),
    [citations],
  );

  const components = useMemo(
    () => createBaseComponents(urlToId, onCitationClick, onDossierClick),
    [onCitationClick, onDossierClick, urlToId],
  );

  const briefingSections = useMemo(
    () => (variant === "briefing" ? splitBriefingSections(content) : []),
    [content, variant],
  );

  if (!content && !streaming) return null;

  return (
    <div className="chat-markdown font-mono text-xs leading-relaxed">
      {variant === "briefing" && briefingSections.length > 0 ? (
        briefingSections.map((section) => (
          <BriefingSectionBlock
            key={section.title}
            title={section.title}
            body={section.body}
            urlToId={urlToId}
            onCitationClick={onCitationClick}
            onDossierClick={onDossierClick}
          />
        ))
      ) : (
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {content}
        </ReactMarkdown>
      )}
      {streaming && (
        <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-zinc-500" />
      )}
    </div>
  );
}

export function isBriefingAssistantMessage(
  messages: { role: string; content: string }[],
  index: number,
): boolean {
  if (index === 0) return false;
  const msg = messages[index];
  const prev = messages[index - 1];
  return (
    msg?.role === "assistant" &&
    prev?.role === "user" &&
    prev.content.trim() === "Briefing de mi Ticker Watch"
  );
}
