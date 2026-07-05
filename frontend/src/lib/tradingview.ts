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
