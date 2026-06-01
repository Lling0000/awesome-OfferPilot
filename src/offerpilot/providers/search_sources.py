from dataclasses import dataclass
from typing import List, Protocol


class SearchSourceNotConfigured(RuntimeError):
    pass


class SearchSource(Protocol):
    name: str
    source_type: str

    def search(self, query: dict) -> List[dict]:
        """Return raw source candidates for one query-plan item."""


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
class UnconfiguredExternalSearchSource:
    name: str = "external-search"
    source_type: str = "search_engine"

    def search(self, query: dict) -> List[dict]:
        raise SearchSourceNotConfigured(
            f"{self.name} is not configured. Provide a real search adapter before use."
        )
