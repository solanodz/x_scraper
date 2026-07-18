export function normalizeDossierSymbol(symbol: string): string {
  return symbol.replace(/^\$/, "").trim().toUpperCase();
}

export function dossierPath(symbol: string): string {
  const normalized = normalizeDossierSymbol(symbol);
  return `/dossier?symbol=${encodeURIComponent(normalized)}`;
}
