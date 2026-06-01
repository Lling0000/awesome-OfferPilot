import hashlib
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


class IntakeInputError(ValueError):
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
    if not canonical_url:
        raise IntakeInputError("Job URL is required.")

    default_resume = _resolve_resume(session, user, resume_id)
    parsed = provider.parse_job_link(canonical_url)
    return _run_parsed_intake(
        session=session,
        user=user,
        parsed=parsed,
        raw_input=url,
        canonical_source=canonical_url,
        source_type="job_link",
        default_resume=default_resume,
    )


def run_pasted_jd_intake(
    session: Session,
    user: User,
    jd_text: str,
    resume_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Turn pasted JD text into an application, evidence report, and reminders."""

    provider = MockAgentProvider()
    normalized_jd = jd_text.strip()
    if len(normalized_jd) < 20:
        raise IntakeInputError("Pasted JD text is too short to analyze.")

    default_resume = _resolve_resume(session, user, resume_id)
    parsed = provider.parse_job_description(normalized_jd)
    fingerprint = hashlib.sha256(normalized_jd.encode("utf-8")).hexdigest()[:16]
    return _run_parsed_intake(
        session=session,
        user=user,
        parsed=parsed,
        raw_input=f"pasted-jd://{fingerprint}",
        canonical_source=f"pasted-jd://{fingerprint}",
        source_type="pasted_jd",
        default_resume=default_resume,
    )


def _resolve_resume(session: Session, user: User, resume_id: Optional[str]) -> Optional[Resume]:
    if resume_id:
        resume = session.get(Resume, resume_id)
        if resume is None or resume.user_id != user.id:
            raise ResumeLookupError(f"Resume id is not available for this user: {resume_id}")
        return resume
    return session.scalar(
        select(Resume).where(Resume.user_id == user.id, Resume.is_default.is_(True))
    )


def _run_parsed_intake(
    session: Session,
    user: User,
    parsed: dict,
    raw_input: str,
    canonical_source: str,
    source_type: str,
    default_resume: Optional[Resume],
) -> Dict[str, Any]:
    provider = MockAgentProvider()
    job_link = session.scalar(
        select(JobLink).where(
            JobLink.user_id == user.id,
            JobLink.canonical_url == canonical_source,
        )
    )
    if job_link is None:
        job_link = JobLink(user_id=user.id, raw_url=raw_input, canonical_url=canonical_source)
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
        notes=(
            "Created from pasted JD intake."
            if source_type == "pasted_jd"
            else "Created from job-link intake."
        ),
        next_action_at=datetime.utcnow(),
    )
    session.add(application)
    session.flush()

    run = AgentRun(
        user_id=user.id,
        run_type="forced_search",
        status="succeeded",
        input_json={
            "source_type": source_type,
            "job_link_id": job_link.id,
            "resume_id": default_resume.id if default_resume else None,
            **(
                {"url": raw_input}
                if source_type == "job_link"
                else {"jd_text_chars": len(parsed["jd_text"])}
            ),
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
        "input_type": source_type,
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
