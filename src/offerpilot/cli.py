import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import uvicorn

from offerpilot.config import get_settings
from offerpilot.db import ensure_demo_user, init_db, reset_db, session_scope
from offerpilot.doctor import checks_ok, format_checks, run_doctor
from offerpilot.intake import ResumeLookupError, run_job_link_intake
from offerpilot.intelligence import run_daily_intelligence
from offerpilot.reminders import build_daily_reminders
from offerpilot.seed import seed_demo

app = typer.Typer(help="OfferPilot job search command center.")
db_app = typer.Typer(help="Database commands.")
app.add_typer(db_app, name="db")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the local web app."""
    init_db()
    uvicorn.run("offerpilot.app:create_app", factory=True, host=host, port=port, reload=False)


@db_app.command("init")
def db_init() -> None:
    init_db()
    typer.echo("Database initialized.")


@db_app.command("reset")
def db_reset() -> None:
    reset_db()
    typer.echo("Database reset.")


@app.command()
def demo(reset: bool = False) -> None:
    """Seed a complete demo application, reminders, and evidence-backed report."""
    result = seed_demo(reset=reset)
    typer.echo("Demo ready:")
    for key, value in result.items():
        typer.echo(f"  {key}: {value}")


@app.command("analyze-link")
def analyze_link(
    url: str,
    resume_id: Optional[str] = typer.Option(
        None,
        "--resume-id",
        help="Attach a specific resume id to the created application.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Create an application and source-backed report from a job URL."""
    init_db()
    with session_scope() as session:
        user = ensure_demo_user(session)
        try:
            result = run_job_link_intake(session, user, url, resume_id=resume_id)
        except ResumeLookupError as exc:
            raise typer.BadParameter(str(exc), param_hint="--resume-id") from exc
        if json_output:
            typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
            return
        typer.echo("Job link analyzed:")
        typer.echo(f"  company: {result['company_name']}")
        typer.echo(f"  job_title: {result['job_title']}")
        typer.echo(f"  application_id: {result['application_id']}")
        typer.echo(f"  search_report_id: {result['search_report_id']}")
        typer.echo(f"  reminders_created: {result['reminders_created']}")
        typer.echo("  sourceUrls:")
        for source_url in result["sourceUrls"]:
            typer.echo(f"    - {source_url}")


@app.command()
def doctor(strict_publish: bool = False) -> None:
    """Check local readiness."""
    init_db()
    checks = run_doctor(strict_publish=strict_publish, root=Path("."))
    typer.echo(format_checks(checks))
    raise typer.Exit(0 if checks_ok(checks) else 1)


@app.command()
def remind(daily: bool = True, dry_run: bool = False) -> None:
    """Generate or preview daily reminders."""
    init_db()
    with session_scope() as session:
        user = ensure_demo_user(session)
        reminders = build_daily_reminders(session, user.id, datetime.utcnow())
        if dry_run:
            session.rollback()
        if not daily:
            typer.echo("Only daily reminders are supported in v1.")
        typer.echo(f"{'Would create' if dry_run else 'Created'} {len(reminders)} reminders.")
        for reminder in reminders:
            typer.echo(f"P{reminder.priority} {reminder.title}")


@app.command("intelligence")
def intelligence(role_family: str = "backend", city: str = "Shanghai") -> None:
    """Run the daily multi-agent interview intelligence brief."""
    init_db()
    with session_scope() as session:
        user = ensure_demo_user(session)
        result = run_daily_intelligence(session, user, role_family=role_family, city=city)
        typer.echo("Daily intelligence ready:")
        typer.echo(f"  agent_run_id: {result['agent_run_id']}")
        typer.echo(f"  items: {len(result['items'])}")
        typer.echo(f"  sourceUrls: {len(result['sourceUrls'])}")
        for item in result["items"]:
            typer.echo(
                "  "
                f"{item['company_scale']} · {item['signal_type']} · "
                f"{item['company_name']} · {item['source_url']}"
            )


def main() -> None:
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    app()
