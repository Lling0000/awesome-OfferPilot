from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from offerpilot.config import get_settings
from offerpilot.models import Base, User


def _ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    path = Path(database_url.replace("sqlite:///", "", 1))
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)


def make_engine(database_url: Optional[str] = None) -> Engine:
    url = database_url or get_settings().database_url
    _ensure_sqlite_parent(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def make_session_factory(database_url: Optional[str] = None) -> sessionmaker:
    return sessionmaker(bind=make_engine(database_url), autoflush=False, expire_on_commit=False)


def init_db(database_url: Optional[str] = None) -> None:
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)


def reset_db(database_url: Optional[str] = None) -> None:
    engine = make_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(database_url: Optional[str] = None) -> Iterator[Session]:
    factory = make_session_factory(database_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_demo_user(session: Session) -> User:
    settings = get_settings()
    user = session.scalar(select(User).where(User.email == settings.demo_user_email))
    if user:
        return user
    user = User(
        email=settings.demo_user_email,
        display_name="Demo Applicant",
        auth_provider="demo",
    )
    session.add(user)
    session.flush()
    return user
