from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from offerpilot.agents import MockAgentProvider
from offerpilot.models import AgentRun, Application, JobLink, Resume, User
from offerpilot.reminders import build_daily_reminders
from offerpilot.reports import create_search_report


class ResumeLookupError(ValueError):
    pass


def run_job_link_intake(
    session: Session,
    user: User,
    url: str,
    resume_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Turn a job URL into an application, evidence report, and reminders."""

    provider = MockAgentProvider()
    canonical_url = url.strip()

    if resume_id:
        default_resume = session.get(Resume, resume_id)
        if default_resume is None or default_resume.user_id != user.id:
            raise ResumeLookupError(f"Resume id is not available for this user: {resume_id}")
    else:
        default_resume = session.scalar(
            select(Resume).where(Resume.user_id == user.id, Resume.is_default.is_(True))
        )

    parsed = provider.parse_job_link(canonical_url)

    job_link = session.scalar(
        select(JobLink).where(
            JobLink.user_id == user.id,
            JobLink.canonical_url == canonical_url,
        )
    )
    if job_link is None:
        job_link = JobLink(user_id=user.id, raw_url=url, canonical_url=canonical_url)
        session.add(job_link)

    job_link.platform = parsed["platform"]
    job_link.company_name = parsed["company_name"]
    job_link.job_title = parsed["job_title"]
    job_link.jd_text = parsed["jd_text"]
    job_link.parsed_payload = parsed
    job_link.status = "parsed"
    job_link.last_fetched_at = datetime.utcnow()
    session.flush()

    application = Application(
        user_id=user.id,
        resume_id=default_resume.id if default_resume else None,
        job_link_id=job_link.id,
        company_name=parsed["company_name"],
        job_title=parsed["job_title"],
        city=parsed.get("city"),
        channel=parsed["platform"],
        status="saved",
        notes="Created from job-link intake.",
        next_action_at=datetime.utcnow(),
    )
    session.add(application)
    session.flush()

    run = AgentRun(
        user_id=user.id,
        run_type="forced_search",
        status="succeeded",
        input_json={
            "url": url,
            "job_link_id": job_link.id,
            "resume_id": default_resume.id if default_resume else None,
        },
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    session.add(run)
    session.flush()

    search = provider.forced_search(parsed["company_name"], parsed["job_title"], parsed["jd_text"])
    report = create_search_report(
        session=session,
        user_id=user.id,
        application_id=application.id,
        job_link_id=job_link.id,
        agent_run_id=run.id,
        query=search["query"],
        summary_md=search["summary_md"],
        source_urls=search["source_urls"],
        evidence=search["evidence"],
        confidence_score=search["confidence_score"],
    )
    run.output_json = {"search_report_id": report.id, "sourceUrls": report.source_urls_json}

    reminders = build_daily_reminders(session, user.id, datetime.utcnow())
    return {
        "job_link_id": job_link.id,
        "application_id": application.id,
        "search_report_id": report.id,
        "company_name": parsed["company_name"],
        "job_title": parsed["job_title"],
        "platform": parsed["platform"],
        "resume_id": application.resume_id,
        "sourceUrls": report.source_urls_json,
        "evidence_items": len(search["evidence"]),
        "reminders_created": len(reminders),
    }
