from sqlalchemy import select

from offerpilot.db import ensure_demo_user, reset_db, session_scope
from offerpilot.interviews import InterviewIntakeError, run_interview_intake
from offerpilot.models import AgentRun, Application, Interview


def test_interview_intake_creates_summary_from_typed_notes(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        app = Application(
            user_id=user.id,
            company_name="Example Robotics",
            job_title="Backend Engineer Intern",
            status="interviewing",
        )
        session.add(app)
        session.flush()
        result = run_interview_intake(
            session=session,
            user=user,
            application_id=app.id,
            stage="technical",
            typed_note="The interviewer asked about SQL indexes and project tradeoffs.",
        )

    with session_scope(db_url) as session:
        interview = session.get(Interview, result["interview_id"])
        run = session.get(AgentRun, result["agent_run_id"])

    assert interview.status == "completed"
    assert "SQL indexes" in interview.transcript_text
    assert interview.summary_json["questions"]
    assert interview.summary_json["next_focus"]
    assert run.run_type == "interview_analysis"


def test_interview_intake_combines_audio_transcript_and_notes(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        app = Application(
            user_id=user.id,
            company_name="Example Robotics",
            job_title="Backend Engineer Intern",
        )
        session.add(app)
        session.flush()
        result = run_interview_intake(
            session=session,
            user=user,
            application_id=app.id,
            stage="manager",
            typed_note="I should prepare a clearer project story.",
            audio_file_name="interview.m4a",
        )

    with session_scope(db_url) as session:
        interview = session.get(Interview, result["interview_id"])

    assert "backend projects" in interview.transcript_text
    assert "clearer project story" in interview.transcript_text
    assert interview.summary_json["transcription"]["file_path"] == "interview.m4a"
    assert interview.summary_json["audio_file_name"] == "interview.m4a"


def test_interview_intake_requires_audio_or_notes(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        app = Application(
            user_id=user.id,
            company_name="Example Robotics",
            job_title="Backend Engineer Intern",
        )
        session.add(app)
        session.flush()

        try:
            run_interview_intake(session, user, app.id)
        except InterviewIntakeError as exc:
            assert "audio file or typed notes" in str(exc)
        else:
            raise AssertionError("empty interview intake should fail")


def test_interview_intake_rejects_other_user_application(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        app = Application(
            user_id="other-user",
            company_name="Example Robotics",
            job_title="Backend Engineer Intern",
        )
        session.add(app)
        session.flush()

        try:
            run_interview_intake(session, user, app.id, typed_note="notes")
        except InterviewIntakeError as exc:
            assert "Application not found" in str(exc)
        else:
            raise AssertionError("cross-user interview intake should fail")


def test_interview_intake_persists_one_completed_record(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        app = Application(
            user_id=user.id,
            company_name="Example Robotics",
            job_title="Backend Engineer Intern",
        )
        session.add(app)
        session.flush()
        run_interview_intake(session, user, app.id, typed_note="Asked about FastAPI.")

    with session_scope(db_url) as session:
        interviews = session.scalars(select(Interview)).all()

    assert len(interviews) == 1
    assert interviews[0].summary_json["summary"]
