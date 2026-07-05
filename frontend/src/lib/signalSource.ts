/** Labels y URLs según source_type del Signal. */

export function isXSignal(sourceType?: string | null): boolean {
  return !sourceType || sourceType === "x";
}

export function sourceTypeFromId(idStr: string): string {
  if (idStr.startsWith("rss:")) return "rss";
  if (idStr.startsWith("marketaux:")) return "marketaux";
  if (idStr.startsWith("av:")) return "alpha_vantage";
  return "x";
}

export function resolveSourceType(
  sourceType?: string | null,
  idStr?: string,
): string {
  if (sourceType && sourceType !== "x") return sourceType;
  if (idStr) return sourceTypeFromId(idStr);
  return "x";
}

export function displayAuthor(
  username: string,
  sourceType?: string | null,
): string {
  if (isXSignal(sourceType)) return `@${username}`;
  return username;
}

export function externalLinkLabel(sourceType?: string | null): string {
  if (isXSignal(sourceType)) return "Ver en X";
  if (sourceType === "rss") return "Leer noticia";
  if (sourceType === "marketaux" || sourceType === "alpha_vantage") {
    return "Leer noticia";
  }
  return "Ver fuente";
}

export function linkedArticleLabel(): string {
  return "Leer artículo enlazado";
}

export function externalLinkHref(signal: {
  url: string;
  canonical_url?: string | null;
  source_type?: string | null;
}): string {
  if (!isXSignal(signal.source_type)) {
    return signal.canonical_url?.trim() || signal.url;
  }
  return signal.url;
}

export function citationChipLabel(
  username: string,
  idStr: string,
  sourceType?: string | null,
): string {
  const resolved = resolveSourceType(sourceType, idStr);
  if (isXSignal(resolved)) return `@${username}`;
  return username;
}

export function citationOpenLabel(
  idStr: string,
  sourceType?: string | null,
): string {
  return externalLinkLabel(resolveSourceType(sourceType, idStr));
}

export function sourceBadgeLabel(sourceType?: string | null): string {
  if (!sourceType || sourceType === "x") return "X";
  if (sourceType === "alpha_vantage") return "AV";
  if (sourceType === "marketaux") return "MA";
  return sourceType.slice(0, 6).toUpperCase();
}

export function clusterSourcesLabel(
  sources: { source_type: string }[] | undefined,
): string | null {
  if (!sources || sources.length <= 1) return null;
  const labels = sources.map((s) => sourceBadgeLabel(s.source_type));
  return Array.from(new Set(labels)).join(" · ");
}
