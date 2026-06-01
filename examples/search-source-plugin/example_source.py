class ExampleSearchSource:
    """A deterministic SearchSource example that can run without API keys."""

    name = "example-source"
    source_type = "forum"

    def search(self, query: dict) -> list[dict]:
        query_id = query["id"]
        query_text = query.get("query", "").lower()
        focus = query.get("source_focus", "search_engine")

        candidates = []
        if focus in {"forum", "search_engine", "freshness"}:
            candidates.append(
                {
                    "title": "Example Robotics backend intern interview notes",
                    "url": "https://example.com/community/backend-intern-interview",
                    "source_type": "forum",
                    "publisher": "Example Community",
                    "snippet": (
                        "Candidate notes mention Python services, FastAPI design, "
                        "SQL indexes, Redis caching, and project review."
                    ),
                    "published_at": "2026-02-18T00:00:00",
                    "retrieved_by": self.name,
                    "query_ids": [query_id],
                }
            )

        if focus in {"official", "search_engine", "freshness"} or "engineering blog" in query_text:
            candidates.append(
                {
                    "title": "Example Robotics engineering blog",
                    "url": "https://example.com/engineering/backend-platform",
                    "source_type": "official",
                    "publisher": "Example Robotics",
                    "snippet": (
                        "Official engineering article about Python backend services, "
                        "async workflows, and data quality for candidate products."
                    ),
                    "published_at": "2026-03-22T00:00:00",
                    "retrieved_by": self.name,
                    "query_ids": [query_id],
                }
            )

        return candidates
