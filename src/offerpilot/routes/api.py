from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select

from offerpilot.agents import MockAgentProvider
from offerpilot.db import ensure_demo_user, session_scope
from offerpilot.intake import (
    IntakeInputError,
    ResumeLookupError,
    run_job_link_intake,
    run_pasted_jd_intake,
)
from offerpilot.intelligence import (
    intelligence_child_runs,
    intelligence_item_to_dict,
    intelligence_items_for_run,
    latest_intelligence_items,
    latest_intelligence_runs,
    run_daily_intelligence,
)
from offerpilot.interviews import InterviewIntakeError, run_interview_intake
from offerpilot.models import AgentRun, Application, Interview, JobLink, Reminder, SearchReport
from offerpilot.reminders import build_daily_reminders
from offerpilot.reports import ReportValidationError, create_search_report

router = APIRouter()


class JobLinkCreate(BaseModel):
    url: HttpUrl


class PastedJobDescriptionCreate(BaseModel):
    jd_text: str
    resume_id: Optional[str] = None


class ApplicationCreate(BaseModel):
    company_name: str
    job_title: str
    city: str = None
    channel: str = None


class InterviewIntakeCreate(BaseModel):
    stage: str = "technical"
    typed_note: str = ""
    audio_file_name: str = None


class IntelligenceRunCreate(BaseModel):
    role_family: str = "backend"
    city: str = "Shanghai"


@router.get("/health")
def health() -> dict:
    return {"ok": True, "service": "offerpilot"}


@router.get("/me")
def me() -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        return {"id": user.id, "email": user.email, "display_name": user.display_name}


@router.post("/job-links")
def create_job_link(payload: JobLinkCreate) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        result = run_job_link_intake(session, user, str(payload.url))
        job_link = session.get(JobLink, result["job_link_id"])
        return {
            "id": job_link.id,
            "company_name": job_link.company_name,
            "job_title": job_link.job_title,
            "application_id": result["application_id"],
            "search_report_id": result["search_report_id"],
        }


@router.post("/job-descriptions")
def create_pasted_job_description(payload: PastedJobDescriptionCreate) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        try:
            result = run_pasted_jd_intake(
                session,
                user,
                payload.jd_text,
                resume_id=payload.resume_id,
            )
        except (IntakeInputError, ResumeLookupError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result


@router.post("/job-links/{job_link_id}/create-application")
def create_application_from_job_link(job_link_id: str) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        job_link = session.get(JobLink, job_link_id)
        if not job_link or job_link.user_id != user.id:
            raise HTTPException(status_code=404, detail="Job link not found")
        app = Application(
            user_id=user.id,
            job_link_id=job_link.id,
            company_name=job_link.company_name or "Unknown Company",
            job_title=job_link.job_title or "Unknown Role",
            city=(job_link.parsed_payload or {}).get("city"),
            channel=job_link.platform,
            status="saved",
        )
        session.add(app)
        session.flush()
        return {"id": app.id, "company_name": app.company_name, "job_title": app.job_title}


@router.post("/job-links/{job_link_id}/search")
def forced_search_job_link(job_link_id: str) -> dict:
    provider = MockAgentProvider()
    with session_scope() as session:
        user = ensure_demo_user(session)
        job_link = session.get(JobLink, job_link_id)
        if not job_link or job_link.user_id != user.id:
            raise HTTPException(status_code=404, detail="Job link not found")
        run = AgentRun(
            user_id=user.id,
            run_type="forced_search",
            status="succeeded",
            input_json={"job_link_id": job_link.id, "url": job_link.raw_url},
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
        )
        session.add(run)
        session.flush()
        result = provider.forced_search(
            job_link.company_name or "Unknown Company",
            job_link.job_title or "Unknown Role",
            job_link.jd_text or "",
        )
        try:
            report = create_search_report(
                session=session,
                user_id=user.id,
                job_link_id=job_link.id,
                agent_run_id=run.id,
                query=result["query"],
                summary_md=result["summary_md"],
                source_urls=result["source_urls"],
                evidence=result["evidence"],
                confidence_score=result["confidence_score"],
            )
        except ReportValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"id": report.id, "sourceUrls": report.source_urls_json}


@router.get("/applications")
def list_applications() -> list:
    with session_scope() as session:
        user = ensure_demo_user(session)
        apps = session.scalars(select(Application).where(Application.user_id == user.id)).all()
        return [
            {
                "id": app.id,
                "company_name": app.company_name,
                "job_title": app.job_title,
                "status": app.status,
            }
            for app in apps
        ]


@router.post("/applications")
def create_application(payload: ApplicationCreate) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        app = Application(user_id=user.id, **payload.model_dump())
        session.add(app)
        session.flush()
        return {"id": app.id}


@router.post("/applications/{application_id}/interviews")
def create_interview(application_id: str, payload: InterviewIntakeCreate) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        try:
            result = run_interview_intake(
                session=session,
                user=user,
                application_id=application_id,
                stage=payload.stage,
                typed_note=payload.typed_note,
                audio_file_name=payload.audio_file_name,
            )
        except InterviewIntakeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        interview = session.get(Interview, result["interview_id"])
        return {
            "id": interview.id,
            "stage": interview.stage,
            "status": interview.status,
            "questions": (interview.summary_json or {}).get("questions", []),
            "summary": (interview.summary_json or {}).get("summary"),
            "next_focus": (interview.summary_json or {}).get("next_focus", []),
        }


@router.post("/reminders/generate-daily")
def generate_daily_reminders() -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        reminders = build_daily_reminders(session, user.id, datetime.utcnow())
        return {"created": len(reminders)}


@router.post("/intelligence/daily")
def generate_daily_intelligence(payload: IntelligenceRunCreate = None) -> dict:
    payload = payload or IntelligenceRunCreate()
    with session_scope() as session:
        user = ensure_demo_user(session)
        return run_daily_intelligence(
            session,
            user,
            role_family=payload.role_family,
            city=payload.city,
        )


@router.get("/intelligence")
def list_intelligence(limit: int = 8) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        items = latest_intelligence_items(session, user.id, limit=limit)
        return {
            "items": [intelligence_item_to_dict(item) for item in items],
            "sourceUrls": [item.source_url for item in items],
        }


@router.get("/intelligence/runs")
def list_intelligence_runs(limit: int = 10) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        runs = latest_intelligence_runs(session, user.id, limit=limit)
        return {
            "runs": [
                {
                    "id": run.id,
                    "status": run.status,
                    "started_at": run.started_at,
                    "sourceUrls": (run.output_json or {}).get("sourceUrls", []),
                    "digest": (run.output_json or {}).get("digest", {}),
                }
                for run in runs
            ]
        }


@router.get("/intelligence/{run_id}")
def get_intelligence_run(run_id: str) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        run = session.get(AgentRun, run_id)
        if not run or run.user_id != user.id or run.run_type != "daily_intelligence":
            raise HTTPException(status_code=404, detail="Intelligence run not found")
        child_runs = intelligence_child_runs(session, user.id, run.id)
        items = intelligence_items_for_run(session, user.id, run)
        return {
            "id": run.id,
            "status": run.status,
            "input": run.input_json,
            "sourceUrls": (run.output_json or {}).get("sourceUrls", []),
            "digest": (run.output_json or {}).get("digest", {}),
            "agentRuns": [
                {
                    "id": child.id,
                    "run_type": child.run_type,
                    "status": child.status,
                    "query": child.input_json,
                    "coverage": child.output_json,
                }
                for child in child_runs
            ],
            "items": [intelligence_item_to_dict(item) for item in items],
        }


@router.get("/reminders")
def list_reminders(status: str = "pending") -> list:
    with session_scope() as session:
        user = ensure_demo_user(session)
        reminders = session.scalars(
            select(Reminder).where(Reminder.user_id == user.id, Reminder.status == status)
        ).all()
        return [
            {"id": item.id, "priority": item.priority, "title": item.title, "due_at": item.due_at}
            for item in reminders
        ]


@router.post("/reminders/{reminder_id}/done")
def complete_reminder(reminder_id: str) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        reminder = session.get(Reminder, reminder_id)
        if not reminder or reminder.user_id != user.id:
            raise HTTPException(status_code=404, detail="Reminder not found")
        reminder.status = "done"
        return {"id": reminder.id, "status": reminder.status}


@router.get("/search-reports/{report_id}")
def get_search_report(report_id: str) -> dict:
    with session_scope() as session:
        user = ensure_demo_user(session)
        report = session.get(SearchReport, report_id)
        if not report or report.user_id != user.id:
            raise HTTPException(status_code=404, detail="Report not found")
        return {
            "id": report.id,
            "query": report.query,
            "summary_md": report.summary_md,
            "sourceUrls": report.source_urls_json,
            "evidence": [
                {
                    "title": item.title,
                    "url": item.url,
                    "source_type": item.source_type,
                    "relevance_score": item.relevance_score,
                    "freshness_score": item.freshness_score,
                    "credibility_score": item.credibility_score,
                    "overall_score": (item.raw_json or {}).get("overall_score"),
                    "quality_label": (item.raw_json or {}).get("quality_label"),
                    "score_reasons": (item.raw_json or {}).get("score_reasons", []),
                }
                for item in report.evidence_items
            ],
        }
