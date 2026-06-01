import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String, nullable=True)
    auth_provider: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    version_label: Mapped[str] = mapped_column(String, nullable=True)
    source_type: Mapped[str] = mapped_column(String, default="text")
    content_text: Mapped[str] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=True)
    parsed_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class JobLink(Base):
    __tablename__ = "job_links"
    __table_args__ = (UniqueConstraint("user_id", "canonical_url", name="uq_job_link_user_url"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    raw_url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(String, nullable=True)
    company_name: Mapped[str] = mapped_column(String, nullable=True)
    job_title: Mapped[str] = mapped_column(String, nullable=True)
    jd_text: Mapped[str] = mapped_column(Text, nullable=True)
    parsed_payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    resume_id: Mapped[str] = mapped_column(String, ForeignKey("resumes.id"), nullable=True)
    job_link_id: Mapped[str] = mapped_column(String, ForeignKey("job_links.id"), nullable=True)
    company_name: Mapped[str] = mapped_column(String)
    job_title: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String, nullable=True)
    channel: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="saved")
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    next_action_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    job_link = relationship("JobLink")
    resume = relationship("Resume")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    application_id: Mapped[str] = mapped_column(String, ForeignKey("applications.id"), index=True)
    stage: Mapped[str] = mapped_column(String, default="technical")
    status: Mapped[str] = mapped_column(String, default="scheduled")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    timezone: Mapped[str] = mapped_column(String, default="Asia/Shanghai")
    location: Mapped[str] = mapped_column(String, nullable=True)
    interviewer: Mapped[str] = mapped_column(String, nullable=True)
    transcript_text: Mapped[str] = mapped_column(Text, nullable=True)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    application = relationship("Application")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id"), nullable=True
    )
    interview_id: Mapped[str] = mapped_column(String, ForeignKey("interviews.id"), nullable=True)
    agent_run_id: Mapped[str] = mapped_column(String, ForeignKey("agent_runs.id"), nullable=True)
    type: Mapped[str] = mapped_column(String, default="missing_info")
    priority: Mapped[int] = mapped_column(Integer, default=2)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    application = relationship("Application")
    interview = relationship("Interview")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    run_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")
    input_json: Mapped[dict] = mapped_column(JSON)
    output_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    parent_run_id: Mapped[str] = mapped_column(String, ForeignKey("agent_runs.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SearchReport(Base):
    __tablename__ = "search_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id"), nullable=True
    )
    job_link_id: Mapped[str] = mapped_column(String, ForeignKey("job_links.id"), nullable=True)
    agent_run_id: Mapped[str] = mapped_column(String, ForeignKey("agent_runs.id"), nullable=True)
    report_type: Mapped[str] = mapped_column(String, default="interview_prep")
    query: Mapped[str] = mapped_column(Text)
    summary_md: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="completed")
    confidence_score: Mapped[float] = mapped_column(Float, nullable=True)
    source_urls_json: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    evidence_items = relationship(
        "EvidenceItem", back_populates="search_report", cascade="all, delete-orphan"
    )


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint("search_report_id", "canonical_url", name="uq_evidence_report_url"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    search_report_id: Mapped[str] = mapped_column(
        String, ForeignKey("search_reports.id"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String, default="unknown")
    publisher: Mapped[str] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=True)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=True)
    credibility_score: Mapped[float] = mapped_column(Float, nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=True)

    search_report = relationship("SearchReport", back_populates="evidence_items")


class IntelligenceItem(Base):
    __tablename__ = "intelligence_items"
    __table_args__ = (
        UniqueConstraint("user_id", "source_url", name="uq_intelligence_user_source"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    agent_run_id: Mapped[str] = mapped_column(String, ForeignKey("agent_runs.id"), nullable=True)
    company_name: Mapped[str] = mapped_column(String)
    company_scale: Mapped[str] = mapped_column(String, index=True)
    role_family: Mapped[str] = mapped_column(String, default="backend")
    signal_type: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String, default="unknown")
    publisher: Mapped[str] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=True)
    tags_json: Mapped[list] = mapped_column(JSON, nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
