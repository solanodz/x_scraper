const CRYPTO_SYMBOLS: Record<string, string> = {
  BTC: "BINANCE:BTCUSDT",
  ETH: "BINANCE:ETHUSDT",
  SOL: "BINANCE:SOLUSDT",
};

const AMEX_SYMBOLS = new Set(["SPY", "GLD", "SLV", "DIA", "IWM", "TLT", "HYG"]);

const NYSE_SYMBOLS = new Set([
  "VIST",
  "YPF",
  "KO",
  "BBD",
  "JPM",
  "V",
  "MA",
  "XOM",
  "JNJ",
  "WMT",
  "HD",
  "BAC",
  "DIS",
  "COST",
  "PG",
  "PFE",
  "NKE",
  "T",
  "CVX",
  "UNH",
  "ABBV",
  "MRK",
]);

const NASDAQ_SYMBOLS = new Set([
  "QQQ",
  "AMZN",
  "AAPL",
  "MSFT",
  "MU",
  "TSLA",
  "NVDA",
  "GOOGL",
  "MELI",
  "META",
  "GGAL",
]);

/** Símbolo en formato TradingView (EXCHANGE:TICKER). */
export function tradingViewSymbol(ticker: string): string {
  const symbol = ticker.replace(/^\$/, "").toUpperCase();
  if (CRYPTO_SYMBOLS[symbol]) return CRYPTO_SYMBOLS[symbol];
  if (AMEX_SYMBOLS.has(symbol)) return `AMEX:${symbol}`;
  if (NYSE_SYMBOLS.has(symbol)) return `NYSE:${symbol}`;
  if (NASDAQ_SYMBOLS.has(symbol)) return `NASDAQ:${symbol}`;
  return `NASDAQ:${symbol}`;
}

export type TradingViewEmbedMode = "compact" | "full";

/** URL del iframe widgetembed. `compact` oculta toolbars para paneles chicos. */
export function buildTradingViewEmbedUrl(
  ticker: string,
  interval = "D",
  mode: TradingViewEmbedMode = "compact",
): string {
  const tvSymbol = encodeURIComponent(tradingViewSymbol(ticker));
  const compact = mode === "compact";
  return (
    `https://s.tradingview.com/widgetembed/?` +
    `symbol=${tvSymbol}&interval=${interval}` +
    `&hidesidetoolbar=${compact ? 1 : 0}&hidetoptoolbar=${compact ? 1 : 0}` +
    `&symboledit=0&saveimage=0&toolbarbg=09090b&theme=dark&style=1` +
    `&timezone=America%2FNew_York&withdateranges=${compact ? 0 : 1}` +
    `&hideideas=1&locale=en`
  );
}
