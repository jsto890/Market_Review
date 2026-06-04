from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .accounts import usernames

RECENT_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
MAX_QUERY_CHARS = 450


class XCostApprovalRequired(RuntimeError):
    """Raised before a potentially paid X API request when approval is missing."""


class XApiError(RuntimeError):
    """Raised when X returns a non-successful API response."""


@dataclass(frozen=True)
class XRequestEstimate:
    query_count: int
    max_pages_per_query: int
    initial_requests: int
    max_requests: int
    endpoint: str
    note: str

    def human(self) -> str:
        return (
            f"X API estimate: endpoint={self.endpoint}, query_groups={self.query_count}, "
            f"initial_requests={self.initial_requests}, max_requests={self.max_requests}. "
            f"{self.note}"
        )


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_recent_search_queries(handles: Iterable[str] | None = None) -> list[str]:
    names = [handle.removeprefix("@") for handle in (handles or usernames())]
    groups: list[list[str]] = []
    current: list[str] = []

    def rendered(terms: list[str]) -> str:
        joined = " OR ".join(f"from:{name}" for name in terms)
        return f"({joined}) has:cashtags -is:retweet"

    for name in names:
        candidate = current + [name]
        if current and len(rendered(candidate)) > MAX_QUERY_CHARS:
            groups.append(current)
            current = [name]
        else:
            current = candidate
    if current:
        groups.append(current)
    return [rendered(group) for group in groups]


def estimate_recent_search(handles: Iterable[str] | None = None, max_pages: int = 1) -> XRequestEstimate:
    queries = build_recent_search_queries(handles)
    return XRequestEstimate(
        query_count=len(queries),
        max_pages_per_query=max_pages,
        initial_requests=len(queries),
        max_requests=len(queries) * max_pages,
        endpoint=RECENT_SEARCH_URL,
        note="X describes read endpoints as pay-per-use. Review current X pricing before approving.",
    )


def fetch_recent_cashtag_posts(
    *,
    start_time: datetime,
    end_time: datetime,
    handles: Iterable[str] | None = None,
    max_pages: int = 1,
    bearer_token: str | None = None,
    approve_cost: bool = False,
) -> list[dict]:
    estimate = estimate_recent_search(handles, max_pages=max_pages)
    if not approve_cost:
        raise XCostApprovalRequired(estimate.human())

    token = bearer_token or os.environ.get("X_BEARER_TOKEN")
    if not token:
        raise RuntimeError("X_BEARER_TOKEN is missing")

    rows: list[dict] = []
    for query in build_recent_search_queries(handles):
        next_token: str | None = None
        for page in range(max_pages):
            params = {
                "query": query,
                "start_time": iso_utc(start_time),
                "end_time": iso_utc(end_time),
                "max_results": "100",
                "tweet.fields": "author_id,conversation_id,created_at,entities,public_metrics,referenced_tweets",
                "expansions": "author_id",
                "user.fields": "username",
            }
            if next_token:
                params["next_token"] = next_token

            payload = _get_json(RECENT_SEARCH_URL, params, token)
            users = {
                user.get("id"): user.get("username")
                for user in payload.get("includes", {}).get("users", [])
            }
            meta_next_token = payload.get("meta", {}).get("next_token")
            for tweet in payload.get("data", []):
                username = users.get(tweet.get("author_id"), "")
                tweet_id = tweet["id"]
                rows.append(
                    {
                        "id": tweet_id,
                        "account": f"@{username}" if username else "",
                        "created_at": tweet.get("created_at", ""),
                        "text": tweet.get("text", ""),
                        "entities": tweet.get("entities", {}),
                        "url": f"https://x.com/{username}/status/{tweet_id}" if username else "",
                        "public_metrics": tweet.get("public_metrics", {}),
                        "referenced_tweets": tweet.get("referenced_tweets", []),
                        "query": query,
                        "query_page": page + 1,
                        "page_has_next_token": bool(meta_next_token),
                    }
                )

            next_token = meta_next_token
            if not next_token:
                break
            if page + 1 >= max_pages:
                break
    return rows


def _get_json(url: str, params: dict[str, str], bearer_token: str) -> dict:
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"Authorization": f"Bearer {bearer_token}", "User-Agent": "stock-chatter-monitor/0.1"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = body[:500].replace("\n", " ")
        if exc.code == 402:
            raise XApiError(
                "X API returned 402 Payment Required. Add pay-per-use credits or enable access in the X Developer Console."
            ) from exc
        raise XApiError(f"X API returned HTTP {exc.code}: {detail}") from exc
