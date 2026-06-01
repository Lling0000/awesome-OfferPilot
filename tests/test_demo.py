from sqlalchemy import select

from offerpilot.db import session_scope
from offerpilot.models import Application, EvidenceItem, IntelligenceItem, Reminder, SearchReport
from offerpilot.seed import seed_demo


def test_demo_creates_complete_flow(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    result = seed_demo(reset=True, database_url=db_url)

    with session_scope(db_url) as session:
        apps = session.scalars(select(Application)).all()
        reports = session.scalars(select(SearchReport)).all()
        evidence = session.scalars(select(EvidenceItem)).all()
        intelligence = session.scalars(select(IntelligenceItem)).all()
        reminders = session.scalars(select(Reminder)).all()

    assert result["application_id"]
    assert result["resume_id"]
    assert len(apps) == 1
    assert len(reports) == 1
    assert reports[0].source_urls_json
    assert len(evidence) >= 1
    assert len(intelligence) == 4
    assert result["intelligence_items"] == 4
    assert len(reminders) >= 1
