import json
from pathlib import Path

from sqlalchemy import select
from typer.testing import CliRunner

from offerpilot.cli import app
from offerpilot.db import ensure_demo_user, reset_db, session_scope
from offerpilot.intelligence import (
    COMPANY_SCALES,
    build_intelligence_query_plan,
    run_daily_intelligence,
)
from offerpilot.models import AgentRun, IntelligenceItem

REPO_ROOT = Path(__file__).resolve().parents[1]
INTELLIGENCE_FIXTURE_PATH = REPO_ROOT / "examples" / "intelligence" / "daily-intelligence.jsonl"
SOURCE_TYPES = {"forum", "official", "social"}


def _daily_intelligence_fixtures() -> list[dict]:
    return [
        json.loads(line)
        for line in INTELLIGENCE_FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_query_plan_covers_user_requested_company_scales() -> None:
    plan = build_intelligence_query_plan(role_family="backend", city="Shanghai")

    assert [item["company_scale"] for item in plan] == COMPANY_SCALES
    assert all(item["agent"].endswith("-scout") for item in plan)
    assert any("GD" in item["query"] or "经理面" in item["query"] for item in plan)


def test_query_plan_matches_structured_intelligence_metadata() -> None:
    plan = build_intelligence_query_plan(role_family="backend", city="Shanghai")
    fixtures_by_query = {fixture["query_id"]: fixture for fixture in _daily_intelligence_fixtures()}

    assert {item["id"] for item in plan} == set(fixtures_by_query)
    for item in plan:
        fixture = fixtures_by_query[item["id"]]
        assert item["agent"] == fixture["agent"]
        assert item["company_scale"] == fixture["company_scale"]
        assert fixture["role_family"] in item["query"]
        assert fixture["city"] in item["query"]
        assert set(item["focus"]).intersection(fixture["expected_tags"])


def test_daily_intelligence_metadata_is_source_backed_public_context() -> None:
    fixtures = _daily_intelligence_fixtures()
    assert fixtures
    assert len({fixture["id"] for fixture in fixtures}) == len(fixtures)
    assert {fixture["company_scale"] for fixture in fixtures} == set(COMPANY_SCALES)

    for fixture in fixtures:
        assert fixture["fixture_type"] == "daily_intelligence_case"
        assert fixture["signal_type"]
        assert fixture["source_type"] in SOURCE_TYPES
        assert fixture["expected_tags"]
        assert fixture["sourceUrls"]
        assert all(url.startswith("https://") for url in fixture["sourceUrls"])
        assert fixture["expected_relevance_score"] > 0
        assert fixture["expected_relevance_min"] <= fixture["expected_relevance_score"]
        assert fixture["privacy"] == "public_source_signal"
        assert fixture["public_evidence"] is True
        assert fixture["private_user_context"] is False
        assert fixture["sourceUrls_refresh_required"] is True
        assert "sourceUrls" in fixture["completed_report_requirement"]
        if fixture["source_type"] in {"forum", "social"}:
            assert fixture["needs_corroboration"] is True
            assert fixture["needs_verification"] is True
            assert "verification" in fixture["weak_signal_policy"]


def test_daily_intelligence_creates_source_backed_items_and_child_runs(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        result = run_daily_intelligence(session, user, role_family="backend", city="Shanghai")

    with session_scope(db_url) as session:
        parent = session.get(AgentRun, result["agent_run_id"])
        child_runs = session.scalars(
            select(AgentRun).where(AgentRun.parent_run_id == result["agent_run_id"])
        ).all()
        items = session.scalars(select(IntelligenceItem)).all()

    assert parent.run_type == "daily_intelligence"
    assert len(child_runs) == 4
    assert len(items) == 4
    assert result["created"] == 4
    assert len(result["sourceUrls"]) == 4
    assert {item.company_scale for item in items} == set(COMPANY_SCALES)
    assert all(item.source_url.startswith("https://") for item in items)
    assert result["digest"]["manager_or_gd_matches"]


def test_daily_intelligence_output_matches_structured_metadata(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        result = run_daily_intelligence(session, user, role_family="backend", city="Shanghai")

    with session_scope(db_url) as session:
        child_runs = session.scalars(
            select(AgentRun).where(AgentRun.parent_run_id == result["agent_run_id"])
        ).all()
        persisted_items = session.scalars(select(IntelligenceItem)).all()

    fixtures_by_url = {
        fixture["sourceUrls"][0]: fixture for fixture in _daily_intelligence_fixtures()
    }
    assert set(result["sourceUrls"]) == set(fixtures_by_url)

    for item in result["items"]:
        fixture = fixtures_by_url[item["source_url"]]
        assert item["company_name"] == fixture["company_name"]
        assert item["company_scale"] == fixture["company_scale"]
        assert item["role_family"] == fixture["role_family"]
        assert item["signal_type"] == fixture["signal_type"]
        assert item["title"] == fixture["title"]
        assert item["source_type"] == fixture["source_type"]
        assert item["publisher"] == fixture["publisher"]
        assert item["relevance_score"] == fixture["expected_relevance_score"]
        assert item["relevance_score"] >= fixture["expected_relevance_min"]
        assert set(fixture["expected_tags"]).issubset(item["tags"])

    child_runs_by_agent = {run.input_json["agent"]: run for run in child_runs}
    for item in persisted_items:
        fixture = fixtures_by_url[item.source_url]
        child_run = child_runs_by_agent[fixture["agent"]]
        assert child_run.input_json["id"] == fixture["query_id"]
        assert item.raw_json["query_id"] == fixture["query_id"]
        assert item.raw_json["retrieved_by"] == fixture["agent"]


def test_daily_intelligence_is_idempotent_by_source_url(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        first = run_daily_intelligence(session, user)
        second = run_daily_intelligence(session, user)

    with session_scope(db_url) as session:
        items = session.scalars(select(IntelligenceItem)).all()

    assert first["created"] == 4
    assert second["created"] == 0
    assert len(items) == 4


def test_daily_intelligence_keeps_private_context_out_of_queries(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)
    private_email = "candidate-private@example.com"

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        result = run_daily_intelligence(
            session,
            user,
            role_family="backend",
            city="Shanghai",
        )

    with session_scope(db_url) as session:
        parent = session.get(AgentRun, result["agent_run_id"])

    assert private_email not in str(parent.input_json)


def test_cli_intelligence_creates_brief(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    runner = CliRunner()

    result = runner.invoke(app, ["intelligence", "--role-family", "backend", "--city", "Shanghai"])

    assert result.exit_code == 0
    assert "Daily intelligence ready" in result.output
    assert "sourceUrls: 4" in result.output
    assert "国央企" in result.output
