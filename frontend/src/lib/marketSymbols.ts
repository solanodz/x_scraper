/** Símbolos para Yahoo Finance / yfinance (OHLC). Crypto usa par -USD. */
const YAHOO_FINANCE_SYMBOLS: Record<string, string> = {
  BTC: "BTC-USD",
  ETH: "ETH-USD",
  SOL: "SOL-USD",
};

export function normalizeMarketSymbol(ticker: string): string {
  return ticker.trim().replace(/^\$/, "").toUpperCase();
}

export function yahooFinanceSymbol(ticker: string): string {
  const symbol = normalizeMarketSymbol(ticker);
  return YAHOO_FINANCE_SYMBOLS[symbol] ?? symbol;
}

/** Evita mezclar quote en vivo si las velas parecen de otro ticker. */
export function canMergeLiveQuote(
  lastClose: number,
  livePrice: number,
): boolean {
  if (lastClose <= 0 || livePrice <= 0) return false;
  const ratio = livePrice / lastClose;
  return ratio >= 0.5 && ratio <= 2;
}
