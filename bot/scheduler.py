import uuid
import logging
from datetime import datetime
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

import config
from db.models import get_session, Reminder
from bot.reminder_job import send_reminder, send_followup_check

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Return the global scheduler instance (must call init_scheduler first)."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialised")
    return _scheduler


def init_scheduler() -> AsyncIOScheduler:
    """Create and start the APScheduler with SQLAlchemy job store."""
    global _scheduler
    jobstores = {"default": SQLAlchemyJobStore(url=config.DATABASE_URL)}
    _scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone=config.TIMEZONE,
        job_defaults={"misfire_grace_time": 3600},
    )
    _scheduler.start()
    logger.info("Scheduler started (tz=%s)", config.TIMEZONE)
    return _scheduler


def schedule_reminder(title: str, scheduled_at: datetime, original_text: str) -> str:
    """Add a job to the scheduler and persist a Reminder row. Returns job_id."""
    tz = pytz.timezone(config.TIMEZONE)
    if scheduled_at.tzinfo is None:
        scheduled_at = tz.localize(scheduled_at)

    job_id = str(uuid.uuid4())
    get_scheduler().add_job(
        send_reminder,
        trigger="date",
        run_date=scheduled_at,
        kwargs={"job_id": job_id, "title": title, "chat_id": config.USER_CHAT_ID},
        id=job_id,
        replace_existing=True,
    )

    with get_session() as session:
        session.add(
            Reminder(
                job_id=job_id,
                title=title,
                scheduled_at=scheduled_at,
                original_text=original_text,
            )
        )
        session.commit()

    logger.info("Scheduled reminder job_id=%s at %s", job_id, scheduled_at)
    return job_id


def schedule_followup(job_id: str, title: str, chat_id: int) -> None:
    """Schedule a repeating 30-minute follow-up check after a reminder fires."""
    followup_id = f"followup_{job_id}"
    get_scheduler().add_job(
        send_followup_check,
        trigger="interval",
        minutes=30,
        kwargs={"job_id": job_id, "title": title, "chat_id": chat_id},
        id=followup_id,
        replace_existing=True,
    )
    logger.info("Scheduled follow-up checks for job_id=%s", job_id)


def cancel_followup(job_id: str) -> None:
    """Cancel the 30-minute follow-up job for a reminder."""
    followup_id = f"followup_{job_id}"
    if get_scheduler().get_job(followup_id):
        get_scheduler().remove_job(followup_id)
        logger.info("Cancelled follow-up for job_id=%s", job_id)


def cancel_reminder(job_id: str) -> bool:
    """Remove a reminder job + its follow-up, and delete the DB row. Returns True if found."""
    scheduler = get_scheduler()

    # Cancel follow-up if running
    cancel_followup(job_id)

    job = scheduler.get_job(job_id)
    if job:
        scheduler.remove_job(job_id)

    with get_session() as session:
        row = session.query(Reminder).filter_by(job_id=job_id).first()
        if row:
            session.delete(row)
            session.commit()
            return True

    return bool(job)


def reschedule_reminder(old_job_id: str, title: str, new_dt: datetime) -> str:
    """
    Cancel an existing reminder's follow-up, create a new reminder at new_dt.
    Returns the new job_id.
    """
    cancel_followup(old_job_id)

    # Remove old DB row (the APScheduler job already fired or may not exist)
    with get_session() as session:
        row = session.query(Reminder).filter_by(job_id=old_job_id).first()
        original_text = row.original_text if row else title
        if row:
            session.delete(row)
            session.commit()

    new_job_id = schedule_reminder(
        title=title,
        scheduled_at=new_dt,
        original_text=original_text,
    )
    logger.info("Rescheduled reminder old=%s new=%s at %s", old_job_id, new_job_id, new_dt)
    return new_job_id


def list_reminders() -> "list[Reminder]":
    """Return all persisted reminders ordered by scheduled time."""
    with get_session() as session:
        rows = (
            session.query(Reminder)
            .order_by(Reminder.scheduled_at)
            .all()
        )
        for row in rows:
            session.expunge(row)
        return rows
