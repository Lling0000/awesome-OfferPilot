import json
from pathlib import Path

from sqlalchemy import select

from offerpilot.db import ensure_demo_user, reset_db, session_scope
from offerpilot.interviews import InterviewIntakeError, run_interview_intake
from offerpilot.models import AgentRun, Application, Interview, SearchReport

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "examples" / "interview-notes"


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
    assert interview.summary_json["privacy"]["transcript_private"] is True
    assert interview.summary_json["privacy"]["public_evidence"] is False
    assert interview.summary_json["privacy"]["sourceUrls"] == []
    assert run.run_type == "interview_analysis"
    assert "transcript" not in run.input_json


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
    assert interview.summary_json["transcription"]["provider"] == "mock-transcription"
    assert interview.summary_json["transcription"]["privacy"] == "private_user_context"
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


def test_interview_fixture_notes_are_safe_private_context(tmp_path) -> None:
    fixture_text = (FIXTURE_DIR / "technical-round.md").read_text(encoding="utf-8")
    assert "fictional sample data" in fixture_text
    assert "Must not be used as `sourceUrls`" in fixture_text

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
            stage="technical",
            typed_note=fixture_text,
        )

    with session_scope(db_url) as session:
        interview = session.get(Interview, result["interview_id"])
        run = session.get(AgentRun, result["agent_run_id"])
        reports = session.scalars(select(SearchReport)).all()

    assert "SQL index choices" in interview.transcript_text
    assert interview.summary_json["typed_note_present"] is True
    assert interview.summary_json["privacy"]["public_evidence"] is False
    assert interview.summary_json["privacy"]["sourceUrls"] == []
    assert reports == []
    assert "sourceUrls" not in run.output_json


def test_interview_audio_fixture_metadata_drives_uploaded_artifact_path(tmp_path) -> None:
    metadata = json.loads((FIXTURE_DIR / "audio-upload-metadata.json").read_text())
    assert metadata["fixture_policy"].startswith("Metadata only")
    assert metadata["privacy"]["public_evidence"] is False
    assert metadata["privacy"]["sourceUrls"] == []

    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        app = Application(
            user_id=user.id,
            company_name=metadata["company_name"],
            job_title=metadata["job_title"],
        )
        session.add(app)
        session.flush()
        result = run_interview_intake(
            session=session,
            user=user,
            application_id=app.id,
            stage=metadata["stage"],
            audio_file_name=metadata["file_name"],
        )

    with session_scope(db_url) as session:
        interview = session.get(Interview, result["interview_id"])

    assert interview.stage == "technical"
    assert "backend projects" in interview.transcript_text
    assert interview.summary_json["audio_file_name"] == "example-technical-round.m4a"
    assert interview.summary_json["transcription"]["file_path"] == "example-technical-round.m4a"
    assert interview.summary_json["transcription"]["provider"] == "mock-transcription"
    assert interview.summary_json["privacy"]["transcript_private"] is True
