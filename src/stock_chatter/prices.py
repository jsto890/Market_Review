from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from .io_utils import write_csv_dicts
from .tickers import yfinance_symbol


PRICE_FIELDS = ["ticker", "date", "open", "high", "low", "close", "volume"]
UNSUPPORTED_TICKER_FIELDS = ["ticker", "provider_symbol", "reason"]


def tickers_from_signals(signals: list[dict]) -> list[str]:
    return sorted({row["ticker"].upper() for row in signals if row.get("ticker")})


def fetch_yfinance_prices(
    tickers: list[str],
    start: str,
    end: str,
    out_path: str | Path,
    unsupported_out_path: str | Path | None = None,
) -> int:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Install market extras first: python -m pip install -e '.[market]'") from exc

    rows: list[dict] = []
    unsupported: list[dict] = []
    for ticker in tickers:
        provider_symbol = yfinance_symbol(ticker)
        try:
            frame = yf.download(provider_symbol, start=start, end=_exclusive_end(end), auto_adjust=True, progress=False)
        except Exception as exc:  # yfinance can throw provider-specific transient errors.
            unsupported.append({"ticker": ticker, "provider_symbol": provider_symbol, "reason": type(exc).__name__})
            continue
        if frame.empty:
            unsupported.append({"ticker": ticker, "provider_symbol": provider_symbol, "reason": "empty_frame"})
            continue
        for index, values in frame.iterrows():
            rows.append(
                {
                    "ticker": ticker,
                    "date": index.date().isoformat(),
                    "open": f"{_scalar_float(values['Open']):.6f}",
                    "high": f"{_scalar_float(values['High']):.6f}",
                    "low": f"{_scalar_float(values['Low']):.6f}",
                    "close": f"{_scalar_float(values['Close']):.6f}",
                    "volume": str(int(_scalar_float(values["Volume"]))),
                }
            )
    if unsupported_out_path:
        write_csv_dicts(unsupported_out_path, unsupported, UNSUPPORTED_TICKER_FIELDS)
    return write_csv_dicts(out_path, rows, PRICE_FIELDS)


def _exclusive_end(end: str) -> str:
    return (date.fromisoformat(end) + timedelta(days=1)).isoformat()


def _scalar_float(value) -> float:
    if hasattr(value, "iloc"):
        value = value.iloc[0]
    return float(value)
