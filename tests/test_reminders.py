import json
from datetime import datetime, timedelta
from pathlib import Path

from offerpilot.db import ensure_demo_user, reset_db, session_scope
from offerpilot.models import Application, Interview
from offerpilot.reminders import build_daily_reminders

REPO_ROOT = Path(__file__).resolve().parents[1]
REMINDER_FIXTURE_PATH = REPO_ROOT / "examples" / "reminders" / "daily-reminders.jsonl"
REMINDER_TYPES = {
    "missing_info",
    "follow_up",
    "daily_checkin",
    "interview_prep",
    "review_after_interview",
}


def _daily_reminder_fixtures() -> list[dict]:
    return [
        json.loads(line)
        for line in REMINDER_FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_daily_reminders_cover_stale_followup_and_interview(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)
    now = datetime(2026, 6, 1, 9, 0, 0)

    with session_scope(db_url) as session:
        user = ensure_demo_user(session)
        app = Application(
            user_id=user.id,
            company_name="Example Robotics",
            job_title="Backend Engineer Intern",
            status="applied",
            next_action_at=now - timedelta(hours=1),
        )
        session.add(app)
        session.flush()
        interview = Interview(
            user_id=user.id,
            application_id=app.id,
            status="scheduled",
            scheduled_at=now + timedelta(hours=20),
        )
        session.add(interview)
        session.flush()

        reminders = build_daily_reminders(session, user.id, now)
        titles = {item.title for item in reminders}

    assert any("跟进" in title for title in titles)
    assert any("面试前" in title for title in titles)
    assert any("岗位链接" in title for title in titles)
    assert any("简历版本" in title for title in titles)


def test_daily_reminder_metadata_is_safe_workflow_state() -> None:
    fixtures = _daily_reminder_fixtures()
    assert fixtures
    assert len({fixture["id"] for fixture in fixtures}) == len(fixtures)

    for fixture in fixtures:
        assert fixture["fixture_type"] == "daily_reminder_case"
        assert fixture["missing_fields"]
        assert fixture["expected_reminder_type"] in REMINDER_TYPES
        assert fixture["safe_without_private_sourceUrls"] is True
        assert fixture["privacy"] == "workflow_metadata"
        assert fixture["public_evidence"] is False
        assert fixture["sourceUrls"] == []
        assert "sourceUrls" in fixture["completed_report_requirement"]


def test_daily_reminder_metadata_drives_rule_expectations(tmp_path) -> None:
    now = datetime(2026, 6, 1, 9, 0, 0)

    for fixture in _daily_reminder_fixtures():
        db_url = f"sqlite:///{tmp_path}/{fixture['id'].replace('/', '-')}.db"
        reset_db(db_url)

        with session_scope(db_url) as session:
            user = ensure_demo_user(session)
            app_state = fixture["application_state"]
            app = Application(
                user_id=user.id,
                company_name=app_state["company_name"],
                job_title=app_state["job_title"],
                status=app_state["status"],
                job_link_id="fixture-job-link" if app_state["has_job_link"] else None,
                resume_id="fixture-resume" if app_state["has_resume"] else None,
                next_action_at=now - timedelta(hours=1) if app_state["next_action_due"] else None,
                updated_at=now - timedelta(days=app_state["updated_days_ago"]),
            )
            session.add(app)
            session.flush()

            interview_state = fixture["interview_state"]
            if interview_state:
                interview = Interview(
                    user_id=user.id,
                    application_id=app.id,
                    status=interview_state["status"],
                    scheduled_at=now + timedelta(hours=interview_state["scheduled_in_hours"]),
                    summary_json={"summary": "done"} if interview_state["has_summary"] else None,
                )
                session.add(interview)
                session.flush()

            reminders = build_daily_reminders(session, user.id, now)

        matching = [
            reminder
            for reminder in reminders
            if reminder.type == fixture["expected_reminder_type"]
            and fixture["expected_title_contains"] in reminder.title
        ]
        assert matching, fixture["id"]
        reminder = matching[0]
        assert reminder.priority == fixture["expected_priority"]
        assert fixture["expected_body_contains"] in reminder.body
