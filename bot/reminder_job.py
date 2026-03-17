import logging
from telegram import Bot
import config

logger = logging.getLogger(__name__)

# Tracks the most recently triggered reminder for the single-user bot.
# Used so the user can say "postpone" or "done" without specifying a job ID.
_last_active: dict = {"job_id": None, "title": None}


def get_last_active() -> dict:
    """Return the last triggered reminder info."""
    return _last_active


async def send_reminder(job_id: str, title: str, chat_id: int):
    """Send a reminder message via Telegram. Called by APScheduler — do not rename or move."""
    global _last_active
    _last_active = {"job_id": job_id, "title": title}

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"Reminder: *{title}*\n\n"
                "Reply *done* to dismiss, or *postpone to [time]* to reschedule."
            ),
            parse_mode="Markdown",
        )
        logger.info("Sent reminder job_id=%s", job_id)

        # Schedule 30-minute follow-up checks (lazy import to avoid circular dependency)
        from bot.scheduler import schedule_followup
        schedule_followup(job_id=job_id, title=title, chat_id=chat_id)

    except Exception:
        logger.exception("Failed to send reminder job_id=%s", job_id)
    finally:
        await bot.shutdown()


async def send_followup_check(job_id: str, title: str, chat_id: int):
    """Send a follow-up check 30 minutes after a reminder fires."""
    global _last_active
    _last_active = {"job_id": job_id, "title": title}

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"Still pending: *{title}*\n\n"
                "Reply *done* to dismiss, or *postpone to [time]* to reschedule."
            ),
            parse_mode="Markdown",
        )
        logger.info("Sent follow-up check job_id=%s", job_id)
    except Exception:
        logger.exception("Failed to send follow-up check job_id=%s", job_id)
    finally:
        await bot.shutdown()
