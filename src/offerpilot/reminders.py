from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from offerpilot.models import Application, Interview, Reminder


def build_daily_reminders(session: Session, user_id: str, now: datetime) -> List[Reminder]:
    created = []
    apps = session.scalars(select(Application).where(Application.user_id == user_id)).all()
    interviews = session.scalars(select(Interview).where(Interview.user_id == user_id)).all()

    for app in apps:
        if not app.job_link_id:
            created.append(
                _reminder(
                    user_id,
                    "missing_info",
                    1,
                    f"补充 {app.company_name} 的岗位链接",
                    "岗位链接会影响 JD 回看、强制搜索和面试准备报告。",
                    now,
                    application_id=app.id,
                )
            )
        if not app.resume_id and app.status in {"applied", "interviewing", "offer"}:
            created.append(
                _reminder(
                    user_id,
                    "missing_info",
                    1,
                    f"记录 {app.company_name} 使用的简历版本",
                    "后续复盘命中率时需要知道本次投递用了哪版简历。",
                    now,
                    application_id=app.id,
                )
            )
        if app.next_action_at and app.next_action_at <= now:
            created.append(
                _reminder(
                    user_id,
                    "follow_up",
                    0,
                    f"跟进 {app.company_name} 的下一步动作",
                    "下一步动作已经到期，确认投递、笔试、面试或结果状态。",
                    app.next_action_at,
                    application_id=app.id,
                )
            )
        if app.updated_at and app.updated_at < now - timedelta(days=7):
            created.append(
                _reminder(
                    user_id,
                    "daily_checkin",
                    2,
                    f"更新 {app.company_name} 的投递状态",
                    "这条机会超过 7 天未更新，建议确认是否沉默、推进或关闭。",
                    now,
                    application_id=app.id,
                )
            )

    for interview in interviews:
        if interview.status == "scheduled" and interview.scheduled_at:
            if now <= interview.scheduled_at <= now + timedelta(hours=24):
                created.append(
                    _reminder(
                        user_id,
                        "interview_prep",
                        0,
                        "面试前补齐链接、地点和准备重点",
                        "未来 24 小时内有面试，确认会议链接、地点和本轮准备材料。",
                        interview.scheduled_at,
                        application_id=interview.application_id,
                        interview_id=interview.id,
                    )
                )
        if interview.status == "completed" and not interview.summary_json:
            created.append(
                _reminder(
                    user_id,
                    "review_after_interview",
                    1,
                    "补充面试复盘",
                    "面试后 24 小时内记录题目、卡点和下一轮准备最有价值。",
                    now,
                    application_id=interview.application_id,
                    interview_id=interview.id,
                )
            )

    persisted = []
    for reminder in created:
        exists = session.scalar(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.application_id == reminder.application_id,
                Reminder.interview_id == reminder.interview_id,
                Reminder.title == reminder.title,
                Reminder.status == "pending",
            )
        )
        if exists:
            continue
        session.add(reminder)
        persisted.append(reminder)
    session.flush()
    return persisted


def _reminder(
    user_id: str,
    type_: str,
    priority: int,
    title: str,
    body: str,
    due_at: datetime,
    application_id: str = None,
    interview_id: str = None,
) -> Reminder:
    return Reminder(
        user_id=user_id,
        application_id=application_id,
        interview_id=interview_id,
        type=type_,
        priority=priority,
        title=title,
        body=body,
        due_at=due_at,
        status="pending",
        payload_json={"generated_by": "daily_rules"},
    )
