import pytest

from offerpilot.providers import (
    ExternalSearchAPISource,
    LocalFixtureSearchSource,
    MockSearchProvider,
    SearchSourceNotConfigured,
    UnconfiguredExternalSearchSource,
)
from offerpilot.search import build_query_plan, canonicalize_url, normalize_evidence_items


def test_query_plan_includes_company_role_skills_and_freshness() -> None:
    plan = build_query_plan(
        "Example Robotics",
        "Backend Engineer Intern",
        "Python FastAPI SQL Redis role",
    )

    assert len(plan) >= 4
    assert any("Example Robotics" in item["query"] for item in plan)
    assert any("Python" in item["query"] for item in plan)
    assert any(item["id"] == "freshness" for item in plan)


def test_evidence_normalizer_dedupes_and_scores() -> None:
    raw = [
        {
            "title": "Example Robotics backend interview",
            "url": "https://example.com/interview/",
            "snippet": "Python FastAPI SQL questions",
        },
        {
            "title": "Duplicate",
            "url": "https://example.com/interview",
            "snippet": "Duplicate URL with trailing slash",
        },
    ]

    items = normalize_evidence_items(
        raw,
        company_name="Example Robotics",
        job_title="Backend Engineer Intern",
        skills=["Python", "FastAPI", "SQL"],
    )

    assert len(items) == 1
    assert items[0]["canonical_url"] == "https://example.com/interview"
    assert items[0]["relevance_score"] > 0.6
    assert items[0]["credibility_score"] >= 0.5
    assert items[0]["overall_score"] > 0.6
    assert items[0]["quality_label"] in {"limited", "strong", "excellent"}
    assert items[0]["score_reasons"]
    assert items[0]["display_domain"] == "example.com"
    assert "usage_guidance" in items[0]


def test_mock_search_provider_returns_query_plan_and_scored_evidence() -> None:
    result = MockSearchProvider().search(
        "Example Robotics",
        "Backend Engineer Intern",
        "Python FastAPI SQL Redis role",
    )

    assert result["query_plan"]
    assert result["source_urls"]
    assert result["evidence"][0]["relevance_score"] is not None
    assert result["evidence"][0]["overall_score"] is not None
    assert result["evidence"][0]["quality_label"] in {"limited", "strong", "excellent"}
    assert result["search_coverage"]["query_count"] == len(result["query_plan"])
    assert result["search_coverage"]["search_sources"] == ["local-fixtures"]


def test_search_source_plugin_contract_can_be_replaced() -> None:
    class TinySource:
        name = "tiny"
        source_type = "forum"

        def search(self, query: dict) -> list:
            return [
                {
                    "title": "Example Robotics FastAPI interview",
                    "url": "https://example.com/tiny-source",
                    "snippet": "Example Robotics asks Python FastAPI questions.",
                    "source_type": "forum",
                    "query_ids": [query["id"]],
                }
            ]

    result = MockSearchProvider(sources=[TinySource()]).search(
        "Example Robotics",
        "Backend Engineer Intern",
        "Python FastAPI SQL Redis role",
    )

    assert result["search_coverage"]["search_sources"] == ["tiny"]
    assert result["evidence"][0]["query_ids"]


def test_official_current_sources_score_above_stale_weak_background() -> None:
    items = normalize_evidence_items(
        [
            {
                "title": "Example Robotics Backend Engineer Intern official role",
                "url": "https://example.com/careers/backend-intern",
                "snippet": "Official backend internship page mentions Python FastAPI SQL Redis.",
                "source_type": "official",
                "publisher": "Example Robotics",
                "published_at": "2099-01-01T00:00:00",
                "query_ids": ["company-official-stack"],
            },
            {
                "title": "Old forum thread with generic internship advice",
                "url": "https://nowcoder.com/discuss/old-general-advice",
                "snippet": "Generic advice from an old thread without company details.",
                "source_type": "forum",
                "publisher": "Nowcoder",
                "published_at": "2020-01-01T00:00:00",
                "query_ids": ["role-skills-questions"],
            },
        ],
        company_name="Example Robotics",
        job_title="Backend Engineer Intern",
        skills=["Python", "FastAPI", "SQL", "Redis"],
    )

    official = items[0]
    stale = items[1]
    assert official["url"] == "https://example.com/careers/backend-intern"
    assert official["overall_score"] > stale["overall_score"]
    assert official["quality_label"] in {"strong", "excellent"}
    assert stale["quality_label"] == "background"
    assert "high-trust publisher" in official["score_reasons"]
    assert "stale evidence" in " ".join(stale["score_reasons"])
    assert "historical context" in stale["usage_guidance"]


def test_local_fixture_source_returns_query_ids() -> None:
    source = LocalFixtureSearchSource()
    results = source.search({"id": "company-role-interview", "source_focus": "forum"})
    assert results
    assert results[0]["retrieved_by"] == "local-fixtures"
    assert results[0]["query_ids"] == ["company-role-interview"]


def test_unconfigured_external_source_fails_closed() -> None:
    source = UnconfiguredExternalSearchSource(name="serp-api")
    with pytest.raises(SearchSourceNotConfigured):
        source.search({"id": "q1"})


def test_external_search_api_source_requires_clear_setup(monkeypatch) -> None:
    monkeypatch.delenv("SEARCH_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_PROVIDER_ENDPOINT", raising=False)

    source = ExternalSearchAPISource(name="live-serp")
    with pytest.raises(SearchSourceNotConfigured, match="SEARCH_PROVIDER_API_KEY"):
        source.search({"id": "q1", "query": "Example Robotics backend"})

    monkeypatch.setenv("SEARCH_PROVIDER_API_KEY", "test-key")
    with pytest.raises(SearchSourceNotConfigured, match="SEARCH_PROVIDER_ENDPOINT"):
        source.search({"id": "q1", "query": "Example Robotics backend"})

    monkeypatch.setenv("SEARCH_PROVIDER_ENDPOINT", "https://search.example.test/api")
    with pytest.raises(SearchSourceNotConfigured, match="no transport"):
        source.search({"id": "q1", "query": "Example Robotics backend"})


def test_external_search_api_source_maps_transport_results_without_fake_urls() -> None:
    calls = []

    def fake_transport(endpoint: str, payload: dict, headers: dict) -> dict:
        calls.append((endpoint, payload, headers))
        return {
            "results": [
                {
                    "title": "Example Robotics backend interview report",
                    "link": "https://example.com/search-result",
                    "snippet": "Candidate notes mention FastAPI and SQL.",
                    "source": "Example Search",
                    "date": "2026-04-01T00:00:00",
                },
                {
                    "title": "Unlinked result should be ignored",
                    "snippet": "No URL means no source-backed evidence.",
                },
            ]
        }

    source = ExternalSearchAPISource(
        name="live-serp",
        api_key="test-key",
        endpoint="https://search.example.test/api",
        transport=fake_transport,
    )
    results = source.search(
        {
            "id": "role-skills-questions",
            "query": "Example Robotics backend interview",
            "intent": "Find public evidence.",
            "source_focus": "search_engine",
        }
    )

    assert calls[0][0] == "https://search.example.test/api"
    assert calls[0][1]["query"] == "Example Robotics backend interview"
    assert calls[0][2]["Authorization"] == "Bearer test-key"
    assert results == [
        {
            "title": "Example Robotics backend interview report",
            "url": "https://example.com/search-result",
            "snippet": "Candidate notes mention FastAPI and SQL.",
            "publisher": "Example Search",
            "published_at": "2026-04-01T00:00:00",
            "retrieved_by": "live-serp",
            "query_ids": ["role-skills-questions"],
        }
    ]


def test_canonicalize_url_removes_fragment_and_trailing_slash() -> None:
    assert canonicalize_url("HTTPS://Example.com/a/#section") == "https://example.com/a"
