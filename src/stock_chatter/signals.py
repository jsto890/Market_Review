from __future__ import annotations

import re
from collections.abc import Iterable

from .accounts import account_for_handle

TICKER_RE = re.compile(r"(?<![A-Za-z0-9_])\$([A-Za-z][A-Za-z0-9.]{0,9})\b")

LONG_PATTERNS = (
    r"\bbuy\b",
    r"\bbought\b",
    r"\badd(?:ed|ing)?\b",
    r"\blong\b",
    r"\bbullish\b",
    r"\bbreakout\b",
    r"\bstarter\b",
)
SHORT_PATTERNS = (r"\bshort\b", r"\bputs?\b", r"\bbearish\b", r"\bfad(?:e|ing)\b")
AVOID_PATTERNS = (r"\bavoid\b",)
EXIT_PATTERNS = (r"\bsell\b", r"\bsold\b", r"\btrim(?:med|ming)?\b", r"\bexit(?:ed|ing)?\b")
WATCH_PATTERNS = (r"\bwatch(?:ing|list)?\b", r"\bsetup\b", r"\binteresting\b", r"\bkeeping an eye\b")

CATALYST_KEYWORDS = {
    "earnings": ("earnings", "eps", "revenue", "guide", "guidance", "quarter"),
    "analyst": ("upgrade", "downgrade", "price target", "initiated", "analyst"),
    "filing": ("sec", "s-1", "10-q", "10-k", "8-k", "offering", "atm"),
    "ai_infrastructure": ("ai", "data center", "datacenter", "gpu", "hbm", "memory", "nvidia"),
    "semis": ("semi", "semiconductor", "foundry", "wafer", "chip"),
    "biotech": ("fda", "trial", "phase", "pdufa", "clinical"),
    "crypto": ("bitcoin", "btc", "ethereum", "eth", "crypto"),
    "macro": ("fed", "rates", "cpi", "jobs", "treasury", "yield"),
    "mna": ("acquire", "acquisition", "merger", "takeover", "deal"),
}

HYPE_WORDS = ("moon", "squeeze", "rocket", "guaranteed", "100x", "10x", "can't lose", "load the boat")

# Splits a sentence into directional sub-phrases at commas, semicolons, and
# pivot conjunctions (but/however/while/although/yet). "and"/"also"/"plus" are
# intentionally excluded — "bought $X and $Y" should keep both tickers in one phrase.
_PHRASE_SPLIT_RE = re.compile(
    r",\s*|;\s*|\s+but\s+|\s+however\s+|\s+while\s+|\s+although\s+|\s+though\s+|\s+yet\s+"
)


def _ticker_phrase(sentence: str, ticker: str) -> str:
    """Return the smallest comma/conjunction sub-phrase containing the ticker cashtag."""
    pattern = re.compile(rf'(?<![A-Za-z0-9_])\${re.escape(ticker)}\b', re.IGNORECASE)
    for phrase in _PHRASE_SPLIT_RE.split(sentence):
        phrase = phrase.strip()
        if phrase and pattern.search(phrase):
            return phrase
    return sentence


def extract_ticker_context(text: str, ticker: str, all_tickers: list[str]) -> dict:
    """Return the context phrase/sentence and co-ticker relationships for one ticker."""
    sentences = [s.strip() for s in re.split(r'(?<!\d)\.(?!\d)|[!?\n]+', text) if s.strip()]
    ticker_re = re.compile(rf'(?<![A-Za-z0-9_])\${re.escape(ticker)}\b', re.IGNORECASE)

    containing = [s for s in sentences if ticker_re.search(s)]
    context_sentence = " | ".join(containing) if containing else ""
    # Sub-phrase: the comma/conjunction-delimited fragment that actually names this ticker
    context_phrase = _ticker_phrase(containing[0], ticker) if containing else ""

    others = [t for t in all_tickers if t != ticker]
    co_same: list[str] = []
    co_other: list[str] = []
    for t in others:
        pattern = rf'(?<![A-Za-z0-9_])\${re.escape(t)}\b'
        in_same = any(re.search(pattern, s, re.IGNORECASE) for s in containing)
        if in_same:
            co_same.append(t)
        else:
            co_other.append(t)

    co_relation = "none"
    if co_same:
        low = context_sentence.lower()
        if any(w in low for w in ("vs", "versus", "compared", "over", "instead", "rotating", "swap")):
            co_relation = "comparison"
        elif any(w in low for w in ("and", "also", "plus", "with", "along")):
            co_relation = "confirmation"
        else:
            co_relation = "co_mention"
    elif co_other:
        co_relation = "separate_mention"

    return {
        "context_phrase": context_phrase,
        "context_sentence": context_sentence,
        "co_tickers_same_sentence": co_same,
        "co_tickers_other_sentence": co_other,
        "co_relation": co_relation,
    }


def extract_tickers(text: str) -> list[str]:
    seen: set[str] = set()
    tickers: list[str] = []
    for match in TICKER_RE.finditer(text or ""):
        ticker = match.group(1).upper().rstrip(".")
        if ticker and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def extract_tickers_from_post(post: dict) -> list[str]:
    entity_tickers = [
        cashtag.get("tag", "").upper().rstrip(".")
        for cashtag in post.get("entities", {}).get("cashtags", [])
        if cashtag.get("tag")
    ]
    if entity_tickers:
        seen: set[str] = set()
        return [ticker for ticker in entity_tickers if ticker and not (ticker in seen or seen.add(ticker))]
    return extract_tickers(post.get("text", ""))


def classify_text(text: str) -> dict:
    lowered = (text or "").lower()
    action = "mention"
    direction = "neutral"
    confidence = 0.35

    if _matches(lowered, EXIT_PATTERNS):
        action = "exit"
        direction = "sell"
        confidence = 0.75
    elif _matches(lowered, AVOID_PATTERNS):
        action = "avoid"
        direction = "avoid"
        confidence = 0.65
    elif _matches(lowered, SHORT_PATTERNS):
        action = "short"
        direction = "short"
        confidence = 0.75
    elif _matches(lowered, LONG_PATTERNS):
        action = "entry"
        direction = "long"
        confidence = 0.75
    elif _matches(lowered, WATCH_PATTERNS):
        action = "watch"
        direction = "watch"
        confidence = 0.55

    catalysts = [
        catalyst
        for catalyst, keywords in CATALYST_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    hype_score = min(1.0, sum(1 for word in HYPE_WORDS if word in lowered) * 0.25 + text.count("!") * 0.05)
    if hype_score >= 0.5:
        confidence = max(0.2, confidence - 0.15)

    return {
        "action": action,
        "direction": direction,
        "confidence": f"{confidence:.2f}",
        "catalysts": ";".join(catalysts),
        "hype_score": f"{hype_score:.2f}",
    }


def extract_signals(posts: Iterable[dict]) -> list[dict]:
    signals: list[dict] = []
    for post in posts:
        text = post.get("text", "")
        tickers = extract_tickers_from_post(post)
        if not tickers:
            continue
        account = post.get("account", "")
        account_meta = account_for_handle(account)
        post_classification = classify_text(text)
        for ticker in tickers:
            ctx = extract_ticker_context(text, ticker, tickers)
            # Classify on the sub-phrase (e.g. "bought $AAPL") when available,
            # fall back to full sentence, then whole-post classification.
            classify_text_on = ctx["context_phrase"] or ctx["context_sentence"] or None
            classification = classify_text(classify_text_on) if classify_text_on else post_classification
            signals.append(
                {
                    "account": account,
                    "account_tier": account_meta.tier if account_meta else "unknown",
                    "account_weight": f"{account_meta.score_weight if account_meta else 0.25:.2f}",
                    "tweet_id": post.get("id", ""),
                    "tweet_created_at": post.get("created_at", ""),
                    "ticker": ticker,
                    "action": classification["action"],
                    "direction": classification["direction"],
                    "confidence": classification["confidence"],
                    "catalysts": classification["catalysts"],
                    "hype_score": classification["hype_score"],
                    "url": post.get("url", ""),
                    "text": text.replace("\n", " ").strip(),
                    "context_phrase": ctx["context_phrase"],
                    "context_sentence": ctx["context_sentence"],
                    "co_tickers": ",".join(ctx["co_tickers_same_sentence"] + ctx["co_tickers_other_sentence"]),
                    "co_tickers_same_sentence": ",".join(ctx["co_tickers_same_sentence"]),
                    "co_tickers_other_sentence": ",".join(ctx["co_tickers_other_sentence"]),
                    "co_relation": ctx["co_relation"],
                }
            )
    return signals


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)
