import pytest

from offerpilot.models import EvidenceItem
from offerpilot.reports import ReportValidationError, build_claim_sections, validate_source_urls


def test_source_urls_required() -> None:
    with pytest.raises(ReportValidationError):
        validate_source_urls([])


def test_source_urls_must_be_valid_http_urls() -> None:
    with pytest.raises(ReportValidationError):
        validate_source_urls(["not-a-url"])


def test_source_urls_accept_http_and_https() -> None:
    assert validate_source_urls([" https://example.com/a ", "http://example.com/b"]) == [
        "https://example.com/a",
        "http://example.com/b",
    ]


def test_claim_sections_reference_supported_evidence_ids() -> None:
    strong = EvidenceItem(
        id="src-strong",
        url="https://example.com/strong",
        title="Official backend internship page",
        relevance_score=0.88,
        freshness_score=0.91,
        credibility_score=0.95,
        raw_json={
            "overall_score": 0.91,
            "quality_label": "excellent",
            "usage_guidance": "Safe to use for normal report claims.",
        },
    )
    limited = EvidenceItem(
        id="src-limited",
        url="https://example.com/limited",
        title="Older candidate interview note",
        relevance_score=0.42,
        freshness_score=0.35,
        credibility_score=0.58,
        raw_json={
            "overall_score": 0.44,
            "quality_label": "background",
            "usage_guidance": "Use only for historical context.",
        },
    )

    sections = build_claim_sections([limited, strong])

    assert sections[0]["claims"][0]["sourceIds"] == ["src-strong"]
    assert sections[0]["claims"][0]["status"] == "supported"
    assert sections[0]["unknowns"][0]["sourceIds"] == ["src-limited"]
    assert sections[0]["unknowns"][0]["status"] == "needs_verification"


def test_claim_sections_keep_weak_evidence_in_unknowns() -> None:
    weak = EvidenceItem(
        id="src-weak",
        url="https://example.com/weak",
        title="Unverified social post",
        relevance_score=0.28,
        freshness_score=0.6,
        credibility_score=0.4,
        raw_json={
            "overall_score": 0.38,
            "quality_label": "background",
            "usage_guidance": "Do not use for claims until a more credible source confirms it.",
        },
    )

    sections = build_claim_sections([weak])

    assert sections[0]["claims"] == []
    assert sections[0]["unknowns"][0]["sourceIds"] == ["src-weak"]
    assert "Verify Unverified social post" in sections[0]["unknowns"][0]["unknown"]
