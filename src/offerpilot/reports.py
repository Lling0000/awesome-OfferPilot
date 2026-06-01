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
    return report
