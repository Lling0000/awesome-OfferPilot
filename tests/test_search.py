import pytest

from offerpilot.providers import (
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
    assert items[0]["quality_label"] in {"medium", "high"}
    assert items[0]["score_reasons"]


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
    assert result["evidence"][0]["quality_label"] in {"medium", "high"}
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


def test_canonicalize_url_removes_fragment_and_trailing_slash() -> None:
    assert canonicalize_url("HTTPS://Example.com/a/#section") == "https://example.com/a"
