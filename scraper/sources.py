"""Sources estáticas del Worker (cuentas y búsquedas)."""

# Cuentas de referencia: medios financieros, organismos y voces globales.
FINANCIAL_ACCOUNTS = [
    "Reuters",
    "Bloomberg",
    "WSJ",
    "FT",
    "CNBC",
    "business",
    "ecb",
    "federalreserve",
    "IMFNews",
]

# Búsquedas globales en X (opcional). Por defecto desactivadas: traen mucho ruido.
# Activar con X_INCLUDE_SEARCH=true. Requieren cashtag o filter:links + min_faves.
SEARCH_QUERIES = [
    "($SPY OR $QQQ OR $NVDA OR $AAPL OR $MSFT OR $TSLA OR $AMZN) lang:en filter:links -is:retweet",
    "(CPI OR FOMC OR \"rate decision\" OR earnings beat) lang:en filter:links min_faves:25 -is:retweet",
]
