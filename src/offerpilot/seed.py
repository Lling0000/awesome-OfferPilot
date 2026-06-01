from datetime import datetime, timedelta
from typing import Optional

from offerpilot.agents import MockAgentProvider
from offerpilot.db import ensure_demo_user, init_db, reset_db, session_scope
from offerpilot.intelligence import run_daily_intelligence
from offerpilot.models import AgentRun, Application, Interview, JobLink, Resume
from offerpilot.reminders import build_daily_reminders
from offerpilot.reports import create_search_report


def seed_demo(reset: bool = False, database_url: Optional[str] = None) -> dict:
    if reset:
        reset_db(database_url)
    else:
        init_db(database_url)

    provider = MockAgentProvider()
    with session_scope(database_url) as session:
        user = ensure_demo_user(session)

        resume = Resume(
            user_id=user.id,
            title="Backend Intern Resume",
            version_label="v1-evidence-backed",
            source_type="text",
            content_text=(
                "Python backend intern candidate with FastAPI, SQL, and data workflow projects."
            ),
            parsed_json={"skills": ["Python", "FastAPI", "SQL", "data workflows"]},
            is_default=True,
        )
        session.add(resume)
        session.flush()

        raw_url = "https://www.zhipin.com/job_detail/example-backend-intern.html"
        parsed = provider.parse_job_link(raw_url)
        job_link = JobLink(
            user_id=user.id,
            raw_url=raw_url,
            canonical_url=raw_url,
            platform=parsed["platform"],
            company_name=parsed["company_name"],
            job_title=parsed["job_title"],
            jd_text=parsed["jd_text"],
            parsed_payload=parsed,
            status="parsed",
            last_fetched_at=datetime.utcnow(),
        )
        session.add(job_link)
        session.flush()

        application = Application(
            user_id=user.id,
            resume_id=resume.id,
            job_link_id=job_link.id,
            company_name=parsed["company_name"],
            job_title=parsed["job_title"],
            city=parsed["city"],
            channel="Boss Zhipin",
            status="interviewing",
            applied_at=datetime.utcnow() - timedelta(days=8),
            next_action_at=datetime.utcnow() - timedelta(hours=2),
            notes="Demo opportunity showing source-backed interview prep.",
        )
        session.add(application)
        session.flush()

        run = AgentRun(
            user_id=user.id,
            run_type="forced_search",
            status="succeeded",
            input_json={"url": raw_url, "company": parsed["company_name"]},
            output_json={},
            started_at=datetime.utcnow() - timedelta(minutes=2),
            ended_at=datetime.utcnow() - timedelta(minutes=1),
        )
        session.add(run)
        session.flush()

        search = provider.forced_search(
            parsed["company_name"], parsed["job_title"], parsed["jd_text"]
        )
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
        run.output_json = {"search_report_id": report.id, "source_urls": search["source_urls"]}

        transcription = provider.transcribe_audio("demo-technical-interview.m4a")
        analysis = provider.analyze_interview(transcription["transcript"])
        completed_interview = Interview(
            user_id=user.id,
            application_id=application.id,
            stage="technical",
            status="completed",
            scheduled_at=datetime.utcnow() - timedelta(days=1),
            location="Uploaded interview recording",
            interviewer="Backend hiring manager",
            transcript_text=transcription["transcript"],
            summary_json={
                **analysis,
                "transcription": transcription,
                "audio_file_name": "demo-technical-interview.m4a",
                "typed_note_present": False,
            },
        )
        session.add(completed_interview)
        session.flush()

        interview = Interview(
            user_id=user.id,
            application_id=application.id,
            stage="technical",
            status="scheduled",
            scheduled_at=datetime.utcnow() + timedelta(hours=20),
            location="Video call",
            interviewer="Backend hiring manager",
            transcript_text=None,
        )
        session.add(interview)
        session.flush()

        intelligence = run_daily_intelligence(session, user, role_family="backend", city="Shanghai")
        reminders = build_daily_reminders(session, user.id, datetime.utcnow())
        return {
            "user_id": user.id,
            "resume_id": resume.id,
            "application_id": application.id,
            "search_report_id": report.id,
            "intelligence_items": len(intelligence["items"]),
            "reminders_created": len(reminders),
        }
