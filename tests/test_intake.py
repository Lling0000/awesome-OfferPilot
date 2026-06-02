import json
from pathlib import Path

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from offerpilot.cli import app
from offerpilot.db import ensure_demo_user, reset_db, session_scope
from offerpilot.intake import (
    IntakeInputError,
    ResumeLookupError,
    run_job_link_intake,
    run_pasted_jd_intake,
)
from offerpilot.models import AgentRun, Application, EvidenceItem, JobLink, Resume, SearchReport
from offerpilot.providers import MockProviderBundle

JD_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "examples" / "job-descriptions"
JOB_LINK_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "examples" / "job-links"

PASTED_JD = """Company: Example Analytics
Role: Backend Platform Intern
City: Shanghai

Build Python services for candidate analytics with FastAPI, SQL, Redis, and async workflows.
"""


def _shared_link_fixtures() -> list[dict]:
    fixture_path = JOB_LINK_FIXTURE_DIR / "shared-links.jsonl"
    return [
        json.loads(line)
        for line in fixture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _shared_link_fixture(platform: str) -> dict:
    return next(fixture for fixture in _shared_link_fixtures() if fixture["platform"] == platform)


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


def test_run_company_career_link_intake_creates_source_backed_flow(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        result = run_job_link_intake(
            session,
            user,
            "https://careers.example-retail.test/jobs/frontend-growth-intern",
        )

    with session_scope(db_url) as session:
        app_record = session.get(Application, result["application_id"])
        job_source = session.get(JobLink, result["job_link_id"])
        report = session.get(SearchReport, result["search_report_id"])

    assert app_record.company_name == "Example Retail"
    assert app_record.job_title == "Frontend Growth Intern"
    assert app_record.city == "Hangzhou"
    assert app_record.channel == "company_careers"
    assert job_source.parsed_payload["source_type"] == "company_careers_page"
    assert job_source.parsed_payload["public_evidence"] is False
    assert {"React", "TypeScript", "A/B Testing"}.issubset(
        set(job_source.parsed_payload["skills"])
    )
    assert report.source_urls_json
    assert all(url.startswith("https://") for url in report.source_urls_json)


def test_run_shared_job_link_intake_creates_source_backed_flow(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)
    fixture = _shared_link_fixture("mobile_job_share")
    shared_url = fixture["input_url"]

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        result = run_job_link_intake(session, user, shared_url)

    with session_scope(db_url) as session:
        app_record = session.get(Application, result["application_id"])
        job_source = session.get(JobLink, result["job_link_id"])
        report = session.get(SearchReport, result["search_report_id"])

    assert app_record.company_name == fixture["company_name"]
    assert app_record.job_title == fixture["job_title"]
    assert app_record.city == fixture["city"]
    assert app_record.channel == fixture["platform"]
    assert job_source.raw_url == shared_url
    assert job_source.parsed_payload["source_type"] == fixture["source_type"]
    assert job_source.parsed_payload["public_evidence"] is fixture["public_evidence"]
    assert set(fixture["skills"]).issubset(set(job_source.parsed_payload["skills"]))
    assert report.source_urls_json
    assert shared_url not in report.source_urls_json
    assert all(url.startswith("https://") for url in report.source_urls_json)


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


def test_run_pasted_jd_intake_creates_source_backed_flow(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        result = run_pasted_jd_intake(session, user, PASTED_JD)

    with session_scope(db_url) as session:
        app_record = session.get(Application, result["application_id"])
        job_source = session.get(JobLink, result["job_link_id"])
        report = session.get(SearchReport, result["search_report_id"])
        evidence = session.scalars(select(EvidenceItem)).all()
        run = session.scalars(select(AgentRun)).one()

    assert result["input_type"] == "pasted_jd"
    assert app_record.company_name == "Example Analytics"
    assert app_record.job_title == "Backend Platform Intern"
    assert app_record.channel == "pasted_jd"
    assert job_source.raw_url.startswith("pasted-jd://")
    assert job_source.parsed_payload["public_evidence"] is False
    assert "FastAPI" in job_source.jd_text
    assert report.source_urls_json
    assert evidence
    assert run.input_json["source_type"] == "pasted_jd"
    assert "jd_text_chars" in run.input_json
    assert "jd_text" not in run.input_json


def test_run_pasted_jd_intake_rejects_short_text(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        with pytest.raises(IntakeInputError, match="too short"):
            run_pasted_jd_intake(session, user, "too short")


def test_pasted_jd_parser_fixtures_cover_multiple_role_families() -> None:
    parser = MockProviderBundle().job_link_parser
    cases = [
        (
            "backend-platform-jd.txt",
            "Example Analytics",
            "Backend Platform Intern",
            "Shanghai",
            {"Python", "FastAPI", "SQL", "Redis"},
        ),
        (
            "frontend-growth-jd.txt",
            "Example Retail",
            "Frontend Growth Intern",
            "Hangzhou",
            {"React", "TypeScript", "JavaScript", "Vue", "Node.js"},
        ),
        (
            "data-analytics-jd.txt",
            "Example Finance",
            "数据分析实习生",
            "深圳",
            {"Python", "SQL", "Pandas", "Airflow", "Tableau"},
        ),
        (
            "product-operations-jd.txt",
            "Example Health",
            "Product Manager Intern",
            "Beijing",
            {"Product Analytics", "A/B Testing", "Roadmap", "SQL"},
        ),
    ]

    for fixture_name, company, role, city, expected_skills in cases:
        parsed = parser.parse_text((JD_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
        assert parsed["company_name"] == company
        assert parsed["job_title"] == role
        assert parsed["city"] == city
        assert expected_skills.issubset(set(parsed["skills"]))
        assert parsed["public_evidence"] is False


def test_job_link_parser_fixtures_cover_company_careers_and_mirrors() -> None:
    parser = MockProviderBundle().job_link_parser
    fixture_text = (JOB_LINK_FIXTURE_DIR / "company-careers.txt").read_text(encoding="utf-8")
    assert "careers.example-retail.test" in fixture_text
    assert "jobs.example-mirror.test" in fixture_text

    cases = [
        (
            "https://careers.example-retail.test/jobs/frontend-growth-intern",
            "company_careers",
            "company_careers_page",
            "Example Retail",
            "Frontend Growth Intern",
            "Hangzhou",
            {"React", "TypeScript", "JavaScript", "Vue", "Node.js", "A/B Testing"},
        ),
        (
            "https://jobs.example-mirror.test/mirrors/example-finance-data-intern",
            "mirrored_job_board",
            "mirrored_job_board",
            "Example Finance",
            "Data Analytics Intern",
            "Shenzhen",
            {"Python", "SQL", "Pandas", "Airflow", "Tableau"},
        ),
    ]

    for url, platform, source_type, company, role, city, expected_skills in cases:
        parsed = parser.parse(url)
        assert parsed["platform"] == platform
        assert parsed["source_type"] == source_type
        assert parsed["company_name"] == company
        assert parsed["job_title"] == role
        assert parsed["city"] == city
        assert expected_skills.issubset(set(parsed["skills"]))
        assert parsed["public_evidence"] is False


def test_job_link_parser_fixtures_cover_shared_links() -> None:
    parser = MockProviderBundle().job_link_parser
    fixture_text = (JOB_LINK_FIXTURE_DIR / "shared-links.txt").read_text(encoding="utf-8")
    fixtures = _shared_link_fixtures()
    assert "linkedin.example.test" in fixture_text
    assert "m.example-jobs.test" in fixture_text
    assert fixtures
    assert all(fixture["public_evidence"] is False for fixture in fixtures)
    assert all("sourceUrls" in fixture["completed_report_requirement"] for fixture in fixtures)

    for fixture in fixtures:
        parsed = parser.parse(fixture["input_url"])
        assert fixture["input_url"] in fixture_text
        assert parsed["platform"] == fixture["platform"]
        assert parsed["source_type"] == fixture["source_type"]
        assert parsed["company_name"] == fixture["company_name"]
        assert parsed["job_title"] == fixture["job_title"]
        assert parsed["city"] == fixture["city"]
        assert parsed["jd_text"] == fixture["jd_text"]
        assert set(fixture["skills"]).issubset(set(parsed["skills"]))
        assert parsed["public_evidence"] is fixture["public_evidence"]


def test_pasted_jd_intake_fixtures_still_require_source_urls(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    fixture_names = [
        "frontend-growth-jd.txt",
        "data-analytics-jd.txt",
        "product-operations-jd.txt",
    ]
    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        results = [
            run_pasted_jd_intake(
                session,
                user,
                (JD_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"),
            )
            for fixture_name in fixture_names
        ]

    with session_scope(db_url) as session:
        reports = [session.get(SearchReport, result["search_report_id"]) for result in results]
        apps = [session.get(Application, result["application_id"]) for result in results]

    assert [app.job_title for app in apps] == [
        "Frontend Growth Intern",
        "数据分析实习生",
        "Product Manager Intern",
    ]
    assert all(report.source_urls_json for report in reports)


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
