from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Session
import config


class Base(DeclarativeBase):
    pass


class Reminder(Base):
    """Stores human-readable reminder metadata alongside APScheduler's internal job state."""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, unique=True, nullable=False)        # APScheduler job ID
    title = Column(String, nullable=False)                       # Extracted reminder text
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    calendar_event_id = Column(String, nullable=True)           # Google Calendar event ID if created
    original_text = Column(String, nullable=False)              # Raw user message


engine = create_engine(config.DATABASE_URL)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Return a new SQLAlchemy session."""
    return Session(engine)


def get_reminder_by_job_id(job_id: str) -> "Reminder | None":
    """Fetch a Reminder row by job_id, expunged for safe use outside the session."""
    with get_session() as session:
        row = session.query(Reminder).filter_by(job_id=job_id).first()
        if row:
            session.expunge(row)
        return row
