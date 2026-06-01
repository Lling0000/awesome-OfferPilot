import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol


class SearchSourceNotConfigured(RuntimeError):
    pass


class SearchSource(Protocol):
    name: str
    source_type: str

    def search(self, query: dict) -> List[dict]:
        """Return raw source candidates for one query-plan item."""


SearchTransport = Callable[[str, Dict[str, object], Dict[str, str]], object]


@dataclass
class LocalFixtureSearchSource:
    name: str = "local-fixtures"
    source_type: str = "fixture"

    def search(self, query: dict) -> List[dict]:
        query_id = query["id"]
        focus = query.get("source_focus")
        results = []
        if focus in {"official", "search_engine", "freshness"}:
            results.append(
                {
                    "title": "Example Robotics engineering blog: backend internships",
                    "url": "https://example.com/careers/backend-intern",
                    "source_type": "official",
                    "publisher": "Example Robotics",
                    "snippet": "Official role page describing backend internship requirements.",
                    "published_at": "2026-03-15T00:00:00",
                    "retrieved_by": self.name,
                    "query_ids": [query_id],
                }
            )
        if focus in {"forum", "search_engine", "freshness"}:
            results.append(
                {
                    "title": "Candidate interview notes for backend internship",
                    "url": "https://example.com/blog/backend-intern-interview-notes",
                    "source_type": "forum",
                    "publisher": "Example Community",
                    "snippet": (
                        "Candidate notes mention API design, SQL indexes, caching, "
                        "and project review."
                    ),
                    "published_at": "2026-01-20T00:00:00",
                    "retrieved_by": self.name,
                    "query_ids": [query_id],
                }
            )
        return results


@dataclass
class ExternalSearchAPISource:
    name: str = "external-search-api"
    source_type: str = "search_engine"
    api_key_env: str = "SEARCH_PROVIDER_API_KEY"
    endpoint_env: str = "SEARCH_PROVIDER_ENDPOINT"
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    transport: Optional[SearchTransport] = None

    def search(self, query: dict) -> List[dict]:
        api_key = _configured_value(self.api_key, self.api_key_env)
        if not api_key:
            raise SearchSourceNotConfigured(
                f"{self.name} requires {self.api_key_env}. Set it in .env or pass "
                "api_key=...; the adapter will not fabricate source URLs."
            )

        endpoint = _configured_value(self.endpoint, self.endpoint_env)
        if not endpoint:
            raise SearchSourceNotConfigured(
                f"{self.name} requires {self.endpoint_env}. Set the provider endpoint "
                "before enabling live search."
            )

        if self.transport is None:
            raise SearchSourceNotConfigured(
                f"{self.name} has credentials but no transport configured. Provide a "
                "callable that performs the vendor request and returns linked results."
            )

        payload = {
            "query": query.get("query", ""),
            "query_id": query.get("id", ""),
            "intent": query.get("intent", ""),
            "source_focus": query.get("source_focus", self.source_type),
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "OfferPilot/0.1 SearchSource",
        }
        return _normalize_external_results(
            self.transport(endpoint, payload, headers),
            query=query,
            source_name=self.name,
        )


@dataclass
class UnconfiguredExternalSearchSource(ExternalSearchAPISource):
    name: str = "external-search"


def _configured_value(explicit_value: Optional[str], env_name: str) -> str:
    return (explicit_value if explicit_value is not None else os.getenv(env_name, "")).strip()


def _normalize_external_results(
    response: object,
    query: dict,
    source_name: str,
) -> List[dict]:
    if isinstance(response, dict):
        raw_results = (
            response.get("results")
            or response.get("items")
            or response.get("organic_results")
            or []
        )
    elif isinstance(response, list):
        raw_results = response
    else:
        raise SearchSourceNotConfigured(
            f"{source_name} transport returned an unsupported payload shape; expected "
            "a list or a dict with results/items/organic_results."
        )

    normalized = []
    for raw in raw_results:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or raw.get("link") or "").strip()
        if not url:
            continue
        raw_query_ids = raw.get("query_ids") or []
        if isinstance(raw_query_ids, str):
            raw_query_ids = [raw_query_ids]
        query_ids = sorted({query.get("id", ""), *raw_query_ids} - {""})
        item = {
            "title": raw.get("title") or raw.get("name") or url,
            "url": url,
            "snippet": raw.get("snippet") or raw.get("description") or "",
            "publisher": raw.get("publisher") or raw.get("source") or raw.get("displayed_link"),
            "published_at": raw.get("published_at") or raw.get("date"),
            "retrieved_by": source_name,
            "query_ids": query_ids,
        }
        if raw.get("source_type"):
            item["source_type"] = raw["source_type"]
        if raw.get("canonical_url"):
            item["canonical_url"] = raw["canonical_url"]
        normalized.append({key: value for key, value in item.items() if value is not None})
    return normalized
