import json
from pathlib import Path

import pytest

from offerpilot.models import EvidenceItem
from offerpilot.reports import ReportValidationError, build_claim_sections, validate_source_urls

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_FIXTURE_METADATA = REPO_ROOT / "examples" / "reports" / "report-fixtures.jsonl"


def _report_fixture_metadata() -> list[dict]:
    return [
        json.loads(line)
        for line in REPORT_FIXTURE_METADATA.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_report(fixture: dict) -> dict:
    return json.loads((REPO_ROOT / fixture["report_fixture"]).read_text(encoding="utf-8"))


def _source_url_values(report: dict) -> list[str]:
    values = report["sourceUrls"]
    if all(isinstance(item, str) for item in values):
        return values
    return [item["url"] for item in values]


def _quality_label(score: float) -> str:
    if score >= 0.9:
        return "excellent"
    if score >= 0.75:
        return "strong"
    if score >= 0.5:
        return "limited"
    return "background"


def _claim_source_ids(report: dict) -> set[str]:
    source_ids = set()
    for item in report.get("evidenceItems", []):
        source_ids.update(item.get("sourceIds", []))
    return source_ids


def _unknowns(report: dict) -> list:
    return report.get("unknowns") or report.get("summary", {}).get("unknowns", [])


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


def test_report_fixture_metadata_declares_source_backed_contract() -> None:
    fixtures = _report_fixture_metadata()
    assert fixtures
    assert len({fixture["id"] for fixture in fixtures}) == len(fixtures)

    for fixture in fixtures:
        assert fixture["fixture_type"] == "source_backed_report_case"
        assert fixture["report_fixture"].startswith("examples/reports/")
        assert fixture["report_type"]
        assert fixture["sourceUrls_shape"] in {"object_list", "string_list"}
        assert (
            validate_source_urls(fixture["retained_sourceUrls"]) == fixture["retained_sourceUrls"]
        )
        assert fixture["retained_sourceUrls_count"] > 0
        assert fixture["requires_top_level_sourceUrls"] is True
        assert fixture["expected_evidence_quality_labels"]
        assert fixture["expected_unknown_count_min"] >= 1
        assert "unknowns_not_confident_claims" in fixture["weak_or_missing_evidence_policy"]
        assert fixture["sourceUrls_refresh_required"] is True
        assert "sourceUrls" in fixture["completed_report_requirement"]


def test_report_fixture_metadata_matches_report_files() -> None:
    for fixture in _report_fixture_metadata():
        report = _load_report(fixture)
        urls = _source_url_values(report)

        assert validate_source_urls(urls) == urls
        assert set(urls) == set(fixture["retained_sourceUrls"])
        assert len(urls) == fixture["retained_sourceUrls_count"]
        assert len(_unknowns(report)) >= fixture["expected_unknown_count_min"]

        if fixture["sourceUrls_shape"] == "object_list":
            assert all(isinstance(item, dict) for item in report["sourceUrls"])
            source_ids = {item["id"] for item in report["sourceUrls"]}
            assert set(fixture["required_claim_sourceIds"]).issubset(_claim_source_ids(report))
            assert _claim_source_ids(report).issubset(source_ids)
            claim_groups = [
                set(item.get("sourceIds", [])) for item in report.get("evidenceItems", [])
            ]
            for expected_group in fixture["required_claim_sourceId_groups"]:
                assert set(expected_group) in claim_groups
            for source in report["sourceUrls"]:
                expected = fixture["expected_evidence_quality_labels"][source["id"]]
                assert _quality_label(source["qualityScore"]) == expected
        else:
            assert all(isinstance(item, str) for item in report["sourceUrls"])
            assert report["briefType"] == fixture["report_type"]
            finding_urls = {item["sourceUrl"] for item in report.get("findings", [])}
            assert set(fixture["required_finding_sourceUrls"]).issubset(finding_urls)
            source_types = {item["sourceType"] for item in report.get("findings", [])}
            assert source_types.issubset(fixture["expected_evidence_quality_labels"])
            for expected_unknown in fixture["expected_unknowns_contain"]:
                assert expected_unknown in _unknowns(report)


def test_claim_sections_follow_structured_report_metadata() -> None:
    fixture = next(
        item
        for item in _report_fixture_metadata()
        if item["id"] == "report/job-link-interview-prep"
    )
    evidence = [
        EvidenceItem(
            id=item["id"],
            url=item["url"],
            title=item["title"],
            relevance_score=item["relevance_score"],
            freshness_score=item["freshness_score"],
            credibility_score=item["credibility_score"],
            raw_json={
                "overall_score": item["overall_score"],
                "quality_label": item["quality_label"],
                "usage_guidance": item["usage_guidance"],
            },
        )
        for item in fixture["expected_evidence"]
    ]

    sections = build_claim_sections(evidence)
    claim_source_ids = {
        source_id for claim in sections[0]["claims"] for source_id in claim.get("sourceIds", [])
    }
    unknown_source_ids = {
        source_id
        for unknown in sections[0]["unknowns"]
        for source_id in unknown.get("sourceIds", [])
    }

    supported_ids = {item["id"] for item in fixture["expected_evidence"] if item["supports_claims"]}
    assert supported_ids.issubset(claim_source_ids)
    assert set(fixture["expected_unknown_sourceIds"]).issubset(unknown_source_ids)


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
