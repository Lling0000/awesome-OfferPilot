from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from starlette import status

from offerpilot.db import ensure_demo_user, session_scope
from offerpilot.doctor import run_doctor
from offerpilot.intake import IntakeInputError, run_job_link_intake, run_pasted_jd_intake
from offerpilot.intelligence import (
    COMPANY_SCALES,
    filtered_intelligence_items,
    intelligence_child_runs,
    intelligence_items_for_run,
    latest_intelligence_items,
    latest_intelligence_runs,
    run_daily_intelligence,
)
from offerpilot.interviews import InterviewIntakeError, run_interview_intake
from offerpilot.models import AgentRun, Application, Interview, Reminder, SearchReport

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with session_scope() as session:
        user = ensure_demo_user(session)
        apps = session.scalars(select(Application).where(Application.user_id == user.id)).all()
        reminders = session.scalars(
            select(Reminder).where(Reminder.user_id == user.id, Reminder.status == "pending")
        ).all()
        reports = session.scalars(select(SearchReport).where(SearchReport.user_id == user.id)).all()
        intel_items = latest_intelligence_items(session, user.id, limit=6)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "applications": apps,
                "reminders": reminders,
                "reports": reports,
                "intelligence_items": intel_items,
            },
        )


@router.post("/intake/job-link")
def intake_job_link(url: str = Form(...)):
    with session_scope() as session:
        user = ensure_demo_user(session)
        try:
            result = run_job_link_intake(session, user, url)
        except IntakeInputError:
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(
            url=f"/applications/{result['application_id']}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.post("/intake/job-description")
def intake_job_description(jd_text: str = Form(...)):
    with session_scope() as session:
        user = ensure_demo_user(session)
        try:
            result = run_pasted_jd_intake(session, user, jd_text)
        except IntakeInputError:
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(
            url=f"/applications/{result['application_id']}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.post("/intelligence/daily")
def refresh_daily_intelligence(
    role_family: str = Form("backend"),
    city: str = Form("Shanghai"),
):
    with session_scope() as session:
        user = ensure_demo_user(session)
        result = run_daily_intelligence(session, user, role_family=role_family, city=city)
        return RedirectResponse(
            url=f"/intelligence/{result['agent_run_id']}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/intelligence", response_class=HTMLResponse)
def intelligence_page(
    request: Request,
    company_scale: str = "",
    signal_type: str = "",
):
    with session_scope() as session:
        user = ensure_demo_user(session)
        runs = latest_intelligence_runs(session, user.id)
        items = filtered_intelligence_items(
            session,
            user.id,
            company_scale=company_scale,
            signal_type=signal_type,
        )
        signal_types = sorted(
            {item.signal_type for item in items}
            | {
                "manager_round",
                "group_discussion",
                "technical_interview",
                "founder_round",
            }
        )
        return templates.TemplateResponse(
            request,
            "intelligence.html",
            {
                "runs": runs,
                "items": items,
                "company_scales": COMPANY_SCALES,
                "signal_types": signal_types,
                "selected_company_scale": company_scale,
                "selected_signal_type": signal_type,
            },
        )


@router.get("/intelligence/{run_id}", response_class=HTMLResponse)
def intelligence_detail(request: Request, run_id: str):
    with session_scope() as session:
        user = ensure_demo_user(session)
        run = session.get(AgentRun, run_id)
        if not run or run.user_id != user.id or run.run_type != "daily_intelligence":
            return templates.TemplateResponse(
                request,
                "intelligence_detail.html",
                {"run": None, "items": [], "child_runs": []},
            )
        items = intelligence_items_for_run(session, user.id, run)
        child_runs = intelligence_child_runs(session, user.id, run.id)
        return templates.TemplateResponse(
            request,
            "intelligence_detail.html",
            {"run": run, "items": items, "child_runs": child_runs},
        )


@router.get("/applications", response_class=HTMLResponse)
def applications(request: Request):
    with session_scope() as session:
        user = ensure_demo_user(session)
        apps = session.scalars(select(Application).where(Application.user_id == user.id)).all()
        return templates.TemplateResponse(request, "applications.html", {"applications": apps})


@router.get("/applications/{application_id}", response_class=HTMLResponse)
def application_detail(request: Request, application_id: str):
    with session_scope() as session:
        app = session.get(Application, application_id)
        reports = session.scalars(
            select(SearchReport).where(SearchReport.application_id == application_id)
        ).all()
        interviews = session.scalars(
            select(Interview)
            .where(Interview.application_id == application_id)
            .order_by(Interview.created_at.desc())
        ).all()
        return templates.TemplateResponse(
            request,
            "application_detail.html",
            {"application": app, "reports": reports, "interviews": interviews, "error": None},
        )


@router.post("/applications/{application_id}/interviews")
def create_interview_from_artifact(
    application_id: str,
    stage: str = Form("technical"),
    typed_note: str = Form(""),
    audio_file: Annotated[Optional[UploadFile], File()] = None,
):
    with session_scope() as session:
        user = ensure_demo_user(session)
        file_name = audio_file.filename if audio_file and audio_file.filename else None
        try:
            run_interview_intake(
                session=session,
                user=user,
                application_id=application_id,
                stage=stage,
                typed_note=typed_note,
                audio_file_name=file_name,
            )
        except InterviewIntakeError:
            return RedirectResponse(
                url=f"/applications/{application_id}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/reports/{report_id}", response_class=HTMLResponse)
def report_detail(request: Request, report_id: str):
    with session_scope() as session:
        report = session.get(SearchReport, report_id)
        evidence_items = list(report.evidence_items) if report else []
        return templates.TemplateResponse(
            request,
            "reports.html",
            {"report": report, "evidence_items": evidence_items},
        )


@router.get("/doctor", response_class=HTMLResponse)
def doctor_page(request: Request):
    checks = run_doctor(strict_publish=False)
    return templates.TemplateResponse(request, "doctor.html", {"checks": checks})
