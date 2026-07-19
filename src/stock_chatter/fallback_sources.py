from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

STOCKTWITS_SYMBOL_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
STOCKTWITS_TRENDING_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"
REDDIT_NEW_URL = "https://www.reddit.com/r/{subreddits}/new.json"
USER_AGENT = "stock-chatter-monitor/0.1 (fallback feed)"

DEFAULT_SUBREDDITS = "wallstreetbets+stocks+StockMarket"


class FallbackSourceError(RuntimeError):
    """Raised when a fallback source returns an unusable response."""


def _get_json(url: str, params: dict[str, str] | None = None) -> dict:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise FallbackSourceError(f"{url} returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise FallbackSourceError(f"{url} unreachable: {exc.reason}") from exc


def _stocktwits_row(message: dict) -> dict:
    user = message.get("user") or {}
    username = user.get("username", "")
    symbols = message.get("symbols") or []
    likes = message.get("likes") or {}
    conversation = message.get("conversation") or {}
    message_id = message.get("id")
    return {
        "id": f"st-{message_id}",
        "account": f"@st:{username}" if username else "",
        "created_at": message.get("created_at", ""),
        "text": message.get("body", ""),
        "entities": {"cashtags": [{"tag": s.get("symbol", "")} for s in symbols if s.get("symbol")]},
        "url": f"https://stocktwits.com/{username}/message/{message_id}" if username else "",
        "public_metrics": {
            "like_count": likes.get("total", 0),
            "reply_count": conversation.get("replies", 0),
        },
        "source": "stocktwits",
    }


def fetch_stocktwits_posts(tickers: list[str], max_symbols: int = 40) -> list[dict]:
    rows: list[dict] = []
    for ticker in list(dict.fromkeys(t.upper().removeprefix("$") for t in tickers if t))[:max_symbols]:
        try:
            payload = _get_json(STOCKTWITS_SYMBOL_URL.format(symbol=ticker))
        except FallbackSourceError:
            continue
        rows.extend(_stocktwits_row(message) for message in payload.get("messages", []))
    return rows


def fetch_stocktwits_trending_posts(max_symbols: int = 15) -> list[dict]:
    payload = _get_json(STOCKTWITS_TRENDING_URL)
    symbols = [s.get("symbol", "") for s in payload.get("symbols", []) if s.get("symbol")]
    return fetch_stocktwits_posts(symbols, max_symbols=max_symbols)


def _reddit_row(child: dict) -> dict:
    data = child.get("data") or {}
    author = data.get("author", "")
    created = data.get("created_utc")
    created_at = (
        datetime.fromtimestamp(created, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if created
        else ""
    )
    text = data.get("title", "")
    selftext = (data.get("selftext") or "").strip()
    if selftext:
        text = f"{text}\n{selftext[:2000]}"
    return {
        "id": f"rd-{data.get('name', '')}",
        "account": f"@rd:{author}" if author else "",
        "created_at": created_at,
        "text": text,
        "entities": {},
        "url": f"https://www.reddit.com{data.get('permalink', '')}" if data.get("permalink") else "",
        "public_metrics": {
            "like_count": data.get("score", 0),
            "reply_count": data.get("num_comments", 0),
        },
        "source": "reddit",
    }


def fetch_reddit_posts(subreddits: str = DEFAULT_SUBREDDITS, limit: int = 100) -> list[dict]:
    payload = _get_json(REDDIT_NEW_URL.format(subreddits=subreddits), {"limit": str(min(limit, 100))})
    children = payload.get("data", {}).get("children", [])
    rows = [_reddit_row(child) for child in children]
    return [row for row in rows if row["id"] != "rd-"]


def fetch_fallback_posts(
    tickers: list[str],
    subreddits: str = DEFAULT_SUBREDDITS,
    max_symbols: int = 40,
) -> tuple[list[dict], list[str]]:
    """Fetch from all fallback sources, tolerating individual source failures.

    Returns (rows, sources_that_succeeded). Raises FallbackSourceError only if
    every source failed outright.
    """
    rows: list[dict] = []
    sources: list[str] = []
    errors: list[str] = []
    try:
        stocktwits_rows = fetch_stocktwits_posts(tickers, max_symbols=max_symbols)
        rows.extend(stocktwits_rows)
        if stocktwits_rows:
            sources.append("stocktwits")
    except FallbackSourceError as exc:
        errors.append(str(exc))
    try:
        reddit_rows = fetch_reddit_posts(subreddits)
        rows.extend(reddit_rows)
        if reddit_rows:
            sources.append("reddit")
    except FallbackSourceError as exc:
        errors.append(str(exc))
    if not rows and errors:
        raise FallbackSourceError("; ".join(errors))
    return rows, sources
