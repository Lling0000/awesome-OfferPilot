import json
from pathlib import Path

import pytest
from sqlalchemy import select

from offerpilot.db import ensure_demo_user, reset_db, session_scope
from offerpilot.interviews import InterviewIntakeError, run_interview_intake
from offerpilot.models import AgentRun, Application, Interview, SearchReport
from offerpilot.providers import (
    ExternalTranscriptionProvider,
    TranscriptionProviderNotConfigured,
    TranscriptionProviderResponseError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "examples" / "interview-notes"


def _interview_note_fixtures() -> list[dict]:
    fixture_path = FIXTURE_DIR / "interview-notes.jsonl"
    return [
        json.loads(line)
        for line in fixture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _interview_note_fixture(fixture_id: str) -> dict:
    return next(fixture for fixture in _interview_note_fixtures() if fixture["id"] == fixture_id)


def _question_lines(note_text: str) -> list[str]:
    questions = []
    in_questions = False
    for raw_line in note_text.splitlines():
        line = raw_line.strip()
        if line == "## Questions Asked":
            in_questions = True
            continue
        if in_questions and line.startswith("## "):
            break
        if in_questions and line.startswith("- "):
            questions.append(line[2:])
    return questions


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
    assert interview.summary_json["transcription"]["sourceUrls"] == []
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


def test_interview_note_metadata_matches_fixture_files() -> None:
    fixtures = _interview_note_fixtures()
    assert fixtures
    assert all(fixture["input_type"] == "typed_interview_note" for fixture in fixtures)
    assert all(fixture["source_type"] == "interview_note" for fixture in fixtures)
    assert all(fixture["privacy"] == "private_user_context" for fixture in fixtures)
    assert all(fixture["public_evidence"] is False for fixture in fixtures)
    assert all(fixture["sourceUrls"] == [] for fixture in fixtures)
    assert all("sourceUrls" in fixture["completed_report_requirement"] for fixture in fixtures)

    for fixture in fixtures:
        note_text = (REPO_ROOT / fixture["file_path"]).read_text(encoding="utf-8")
        questions = _question_lines(note_text)
        question_text = " ".join(questions).lower()

        assert "fictional" in note_text.lower()
        assert len(questions) == fixture["expected_question_count"]
        for keyword in fixture["expected_question_keywords"]:
            assert keyword.lower() in question_text


def test_interview_fixture_notes_are_safe_private_context(tmp_path) -> None:
    fixture = _interview_note_fixture("interview-note/technical-round")
    fixture_text = (REPO_ROOT / fixture["file_path"]).read_text(encoding="utf-8")
    assert "fictional sample data" in fixture_text
    assert "Must not be used as `sourceUrls`" in fixture_text
    assert fixture["privacy"] == "private_user_context"
    assert fixture["sourceUrls"] == []

    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        app = Application(
            user_id=user.id,
            company_name=fixture["company_name"],
            job_title=fixture["job_title"],
        )
        session.add(app)
        session.flush()
        result = run_interview_intake(
            session=session,
            user=user,
            application_id=app.id,
            stage=fixture["stage"],
            typed_note=fixture_text,
        )

    with session_scope(db_url) as session:
        interview = session.get(Interview, result["interview_id"])
        run = session.get(AgentRun, result["agent_run_id"])
        reports = session.scalars(select(SearchReport)).all()

    assert "SQL index choices" in interview.transcript_text
    assert interview.stage == fixture["stage"]
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


def test_external_transcription_provider_fails_closed_without_credentials(monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTION_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("TRANSCRIPTION_PROVIDER_ENDPOINT", raising=False)

    provider = ExternalTranscriptionProvider()

    with pytest.raises(TranscriptionProviderNotConfigured, match="TRANSCRIPTION_PROVIDER_API_KEY"):
        provider.transcribe("interview.m4a")


def test_external_transcription_provider_requires_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTION_PROVIDER_API_KEY", "test-key")
    monkeypatch.delenv("TRANSCRIPTION_PROVIDER_ENDPOINT", raising=False)

    provider = ExternalTranscriptionProvider()

    with pytest.raises(TranscriptionProviderNotConfigured, match="TRANSCRIPTION_PROVIDER_ENDPOINT"):
        provider.transcribe("interview.m4a")


def test_external_transcription_provider_requires_transport(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTION_PROVIDER_API_KEY", "test-key")
    monkeypatch.setenv("TRANSCRIPTION_PROVIDER_ENDPOINT", "https://stt.example.test/api")

    provider = ExternalTranscriptionProvider()

    with pytest.raises(TranscriptionProviderNotConfigured, match="no transport configured"):
        provider.transcribe("interview.m4a")


def test_external_transcription_provider_marks_transcript_private() -> None:
    captured = {}

    def transport(endpoint: str, payload: dict, headers: dict) -> dict:
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        captured["headers"] = headers
        return {
            "transcript": "The interviewer asked about project depth and SQL indexes.",
            "confidence": "0.86",
            "language": "en",
            "sourceUrls": ["https://example.com/should-not-survive"],
        }

    provider = ExternalTranscriptionProvider(
        api_key="test-key",
        endpoint="https://stt.example.test/api",
        transport=transport,
    )

    result = provider.transcribe("interview.m4a")

    assert captured["endpoint"] == "https://stt.example.test/api"
    assert captured["payload"]["privacy"] == "private_user_context"
    assert captured["payload"]["sourceUrls"] == []
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert result["transcript"].startswith("The interviewer asked")
    assert result["privacy"] == "private_user_context"
    assert result["sourceUrls"] == []
    assert result["confidence"] == 0.86
    assert result["language"] == "en"


def test_external_transcription_provider_rejects_empty_transcripts() -> None:
    provider = ExternalTranscriptionProvider(
        api_key="test-key",
        endpoint="https://stt.example.test/api",
        transport=lambda endpoint, payload, headers: {"transcript": ""},
    )

    with pytest.raises(TranscriptionProviderResponseError, match="no transcript text"):
        provider.transcribe("interview.m4a")
