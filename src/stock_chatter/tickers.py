from __future__ import annotations

import re

_PLAUSIBLE_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")


def is_plausible_ticker(ticker: str) -> bool:
    """Return True for tickers that could be a real US equity/ETF symbol.

    Rejects garbage strings from X posts (e.g. AMDDDDDDDD, MUUUUUUUUUUU)
    before they hit yfinance and trigger multi-hour curl timeouts.
    """
    return bool(_PLAUSIBLE_RE.match(normalize_ticker(ticker)))


CRYPTO_TICKERS = {
    "BTC", "ETH", "DOGE", "SOL", "XRP", "ADA", "AVAX", "MATIC", "DOT", "LINK",
    "LTC", "BCH", "ATOM", "NEAR", "APT", "ARB", "OP", "ZEC", "CRO", "TON",
    "TRUMP", "PEPE", "SHIB", "FLOKI", "WIF", "BONK", "MEME", "POPCAT",
    "TRX", "ETC", "HBAR", "VET", "FIL", "ICP", "ALGO", "XLM", "SAND",
    "MANA", "AXS", "ENJ", "THETA", "FTM", "ONE", "EGLD", "KAVA", "ZIL",
    "CELO", "RVN", "DASH", "XMR", "EOS", "NEO", "WAVES", "QTUM", "ONT",
    "ICX", "ZRX", "BAT", "GRT", "SNX", "UNI", "AAVE", "COMP", "MKR",
    "CRV", "SUSHI", "YFI", "1INCH", "LDO", "RPL", "STX", "CFX", "SUI",
    "SEI", "TIA", "PYTH", "JTO", "ONDO", "WLD", "STRK", "MANTA", "ALT",
    "PIXEL", "PORTAL", "DYM", "AIT", "ZETA", "SAGA", "REZ", "BB",
}
INDEX_TICKERS = {"SPX", "VIX", "DJI", "NDX"}
COMMODITY_TICKERS = {"SILVER", "GOLD", "OIL"}
ETF_TICKERS = {
    "ARKK",
    "BUG",
    "ETHA",
    "EWY",
    "IBIT",
    "IGV",
    "KWEB",
    "QQQ",
    "SMH",
    "SOXX",
    "SPY",
    "TAN",
}
AMBIGUOUS_TICKERS = {"DRAM", "OTHERS", "GAMEBEY"}

YFINANCE_SYMBOL_OVERRIDES = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "DOGE": "DOGE-USD",
    "SPX": "^GSPC",
    "VIX": "^VIX",
    "SILVER": "SI=F",
    "GOLD": "GC=F",
    "BRK.A": "BRK-A",
    "BRK.B": "BRK-B",
}


def asset_type(ticker: str) -> str:
    symbol = normalize_ticker(ticker)
    if symbol in CRYPTO_TICKERS:
        return "crypto"
    if symbol in INDEX_TICKERS:
        return "index"
    if symbol in COMMODITY_TICKERS:
        return "commodity"
    if symbol in ETF_TICKERS:
        return "etf"
    if symbol in AMBIGUOUS_TICKERS:
        return "ambiguous"
    if "." in symbol:
        return "class_or_foreign"
    return "equity"


def normalize_ticker(ticker: str) -> str:
    return (ticker or "").upper().strip().removeprefix("$").rstrip(".")


def yfinance_symbol(ticker: str) -> str:
    symbol = normalize_ticker(ticker)
    return YFINANCE_SYMBOL_OVERRIDES.get(symbol, symbol)


def asset_warning(ticker: str) -> str:
    kind = asset_type(ticker)
    if kind in {"crypto", "index", "commodity", "ambiguous", "class_or_foreign"}:
        return f"asset_{kind}"
    return ""
