from typing import Iterable, List, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from offerpilot.models import EvidenceItem, SearchReport


class ReportValidationError(ValueError):
    pass


def normalize_url(url: str) -> str:
    return url.strip()


def validate_source_urls(source_urls: Iterable[str]) -> List[str]:
    normalized = [normalize_url(url) for url in source_urls if url and normalize_url(url)]
    if not normalized:
        raise ReportValidationError("A completed report must include at least one source URL.")

    invalid = []
    for url in normalized:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            invalid.append(url)
    if invalid:
        raise ReportValidationError("Invalid source URLs: " + ", ".join(invalid))
    return normalized


def build_claim_sections(evidence_items: Iterable[EvidenceItem]) -> list[dict]:
    """Build deterministic claim sections that reference stored evidence IDs."""
    items = _rank_evidence_items(evidence_items)
    supported = [item for item in items if _quality_label(item) in {"excellent", "strong"}]
    supported_ids = {item.id for item in supported}
    needs_verification = [item for item in items if item.id not in supported_ids]

    claims = []
    if supported:
        top = supported[0]
        claims.append(
            {
                "id": "claim_public_evidence_001",
                "claim": (
                    f"{_source_title(top)} is strong enough to support normal report claims."
                ),
                "sourceIds": [top.id],
                "confidence": "high" if _quality_label(top) == "excellent" else "medium",
                "status": "supported",
            }
        )
    if len(supported) >= 2:
        claims.append(
            {
                "id": "claim_corrob_001",
                "claim": (
                    "Multiple source-backed records can be used together for preparation "
                    "priorities."
                ),
                "sourceIds": [item.id for item in supported[:2]],
                "confidence": "medium",
                "status": "supported",
            }
        )

    unknowns = [
        {
            "id": f"unknown_evidence_{index:03d}",
            "unknown": (
                f"Verify {_source_title(item)} with stronger or newer evidence before treating "
                "it as current interview-process guidance."
            ),
            "sourceIds": [item.id],
            "reason": _usage_guidance(item),
            "status": "needs_verification",
        }
        for index, item in enumerate(needs_verification[:3], start=1)
    ]

    if not items:
        unknowns.append(
            {
                "id": "unknown_no_evidence",
                "unknown": "No stored evidence item can support report claims yet.",
                "sourceIds": [],
                "reason": "A completed report needs public evidence before confident claims.",
                "status": "needs_evidence",
            }
        )

    return [
        {
            "id": "public-evidence",
            "title": "Public Evidence",
            "claims": claims,
            "unknowns": unknowns,
        }
    ]


def _rank_evidence_items(evidence_items: Iterable[EvidenceItem]) -> list[EvidenceItem]:
    return sorted(
        list(evidence_items),
        key=lambda item: (
            _raw_score(item, "overall_score"),
            item.credibility_score or 0,
            item.freshness_score or 0,
            item.relevance_score or 0,
            item.id or "",
        ),
        reverse=True,
    )


def _raw_score(item: EvidenceItem, key: str) -> float:
    value = (item.raw_json or {}).get(key)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _quality_label(item: EvidenceItem) -> str:
    return str((item.raw_json or {}).get("quality_label") or "unknown")


def _source_title(item: EvidenceItem) -> str:
    return item.title or (item.raw_json or {}).get("display_domain") or item.url


def _usage_guidance(item: EvidenceItem) -> str:
    return str(
        (item.raw_json or {}).get("usage_guidance")
        or "Review this source before using it for confident claims."
    )


def create_search_report(
    session: Session,
    user_id: str,
    query: str,
    summary_md: str,
    source_urls: Iterable[str],
    evidence: Iterable[dict],
    application_id: Optional[str] = None,
    job_link_id: Optional[str] = None,
    agent_run_id: Optional[str] = None,
    report_type: str = "interview_prep",
    confidence_score: float = 0.72,
) -> SearchReport:
    valid_urls = validate_source_urls(source_urls)
    report = SearchReport(
        user_id=user_id,
        application_id=application_id,
        job_link_id=job_link_id,
        agent_run_id=agent_run_id,
        report_type=report_type,
        query=query,
        summary_md=summary_md,
        status="completed",
        confidence_score=confidence_score,
        source_urls_json=valid_urls,
    )
    session.add(report)
    session.flush()

    seen = set()
    for item in evidence:
        url = normalize_url(str(item.get("url", "")))
        if not url or url in seen:
            continue
        seen.add(url)
        validate_source_urls([url])
        session.add(
            EvidenceItem(
                search_report_id=report.id,
                url=url,
                canonical_url=item.get("canonical_url") or url,
                title=item.get("title"),
                snippet=item.get("snippet"),
                source_type=item.get("source_type") or "unknown",
                publisher=item.get("publisher"),
                relevance_score=item.get("relevance_score"),
                freshness_score=item.get("freshness_score"),
                credibility_score=item.get("credibility_score"),
                raw_json=item,
            )
        )
    session.flush()
    return report
