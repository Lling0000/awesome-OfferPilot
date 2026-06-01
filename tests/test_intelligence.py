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


def test_query_plan_covers_user_requested_company_scales() -> None:
    plan = build_intelligence_query_plan(role_family="backend", city="Shanghai")

    assert [item["company_scale"] for item in plan] == COMPANY_SCALES
    assert all(item["agent"].endswith("-scout") for item in plan)
    assert any("GD" in item["query"] or "经理面" in item["query"] for item in plan)


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
