import json

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from offerpilot.cli import app
from offerpilot.db import ensure_demo_user, reset_db, session_scope
from offerpilot.intake import ResumeLookupError, run_job_link_intake
from offerpilot.models import Application, EvidenceItem, Resume, SearchReport
from offerpilot.providers import MockProviderBundle


def test_provider_bundle_exposes_replaceable_interfaces() -> None:
    bundle = MockProviderBundle()
    parsed = bundle.job_link_parser.parse("https://www.zhipin.com/job_detail/example.html")
    search = bundle.search_provider.search(
        parsed["company_name"], parsed["job_title"], parsed["jd_text"]
    )
    transcript = bundle.transcription_provider.transcribe("interview.mp3")
    analysis = bundle.interview_analyzer.analyze(transcript["transcript"])

    assert parsed["company_name"] == "Example Robotics"
    assert search["source_urls"]
    assert "transcript" in transcript
    assert analysis["questions"]


def test_run_job_link_intake_creates_source_backed_flow(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        result = run_job_link_intake(
            session,
            user,
            "https://www.zhipin.com/job_detail/provider-test.html",
        )

    with session_scope(db_url) as session:
        app_record = session.get(Application, result["application_id"])
        report = session.get(SearchReport, result["search_report_id"])
        evidence = session.scalars(select(EvidenceItem)).all()

    assert app_record.company_name == "Example Robotics"
    assert report.source_urls_json
    assert evidence


def test_run_job_link_intake_can_use_explicit_resume(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        resume = Resume(
            user_id=user.id,
            title="Explicit Resume",
            source_type="text",
            content_text="Python FastAPI SQL",
            is_default=False,
        )
        session.add(resume)
        session.flush()
        result = run_job_link_intake(
            session,
            user,
            "https://www.zhipin.com/job_detail/explicit-resume.html",
            resume_id=resume.id,
        )

    with session_scope(db_url) as session:
        app_record = session.get(Application, result["application_id"])

    assert app_record.resume_id == resume.id


def test_run_job_link_intake_rejects_missing_explicit_resume(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        with pytest.raises(ResumeLookupError, match="missing-resume-id"):
            run_job_link_intake(
                session,
                user,
                "https://www.zhipin.com/job_detail/missing-resume.html",
                resume_id="missing-resume-id",
            )


def test_cli_analyze_link_creates_flow(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["analyze-link", "https://www.zhipin.com/job_detail/cli-provider-test.html"],
    )

    assert result.exit_code == 0
    assert "Job link analyzed" in result.output
    assert "search_report_id" in result.output


def test_cli_analyze_link_json_output(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "analyze-link",
            "https://www.zhipin.com/job_detail/cli-json-test.html",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["application_id"]
    assert payload["search_report_id"]
    assert payload["sourceUrls"]


def test_cli_analyze_link_accepts_resume_id_option(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", db_url)
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        resume = Resume(
            user_id=user.id,
            title="CLI Resume",
            source_type="text",
            content_text="Python FastAPI SQL",
            is_default=False,
        )
        session.add(resume)
        session.flush()
        resume_id = resume.id

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "analyze-link",
            "https://www.zhipin.com/job_detail/cli-resume-test.html",
            "--resume-id",
            resume_id,
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["resume_id"] == resume_id

    with session_scope(db_url) as session:
        app_record = session.get(Application, payload["application_id"])

    assert app_record.resume_id == resume_id


def test_cli_analyze_link_rejects_unknown_resume_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "analyze-link",
            "https://www.zhipin.com/job_detail/cli-missing-resume.html",
            "--resume-id",
            "missing-resume-id",
        ],
    )

    assert result.exit_code != 0
    assert "missing-resume-id" in result.output
