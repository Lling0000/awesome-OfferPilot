from datetime import datetime, timedelta

from offerpilot.db import ensure_demo_user, reset_db, session_scope
from offerpilot.models import Application, Interview
from offerpilot.reminders import build_daily_reminders


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
