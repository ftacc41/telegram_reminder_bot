import logging
from datetime import datetime, timedelta

import pytz
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler

import config
from bot.parser import (
    is_reminder_intent,
    has_calendar_intent,
    is_postpone_intent,
    parse_reminder,
    parse_event_time,
    parse_postpone_time,
)
from bot.scheduler import schedule_reminder, cancel_reminder, list_reminders, reschedule_reminder, cancel_followup
from bot.calendar_client import create_event
from bot.reminder_job import get_last_active
from db.models import get_session, Reminder, get_reminder_by_job_id

# ConversationHandler state for custom postpone flow
WAITING_CUSTOM_TIME = 1

logger = logging.getLogger(__name__)


def _authorised(update: Update) -> bool:
    """Reject messages from anyone other than the configured user."""
    return update.effective_user.id == config.USER_CHAT_ID


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route plain text messages — handles reminders, calendar events, postpone, and done."""
    if not _authorised(update):
        return

    text = update.message.text.strip()

    # --- Done: dismiss the last active reminder ---
    if text.lower() in ("done", "dismiss", "completed", "finished"):
        await _handle_done(update)
        return

    # --- Postpone: reschedule the last active reminder ---
    if is_postpone_intent(text):
        await _handle_postpone(update, text)
        return

    want_calendar = has_calendar_intent(text)
    want_reminder = is_reminder_intent(text)

    # --- Calendar + reminder (e.g. "dentist March 20 at 4pm, add to calendar, remind me an hour earlier") ---
    if want_calendar and want_reminder:
        await _handle_calendar_and_reminder(update, text)
        return

    # --- Reminder only ---
    if want_reminder:
        await _handle_reminder(update, text)
        return

    # --- Calendar only (e.g. "add my dentist appointment to calendar on March 20 at 4pm") ---
    if want_calendar:
        await _handle_calendar_only(update, text)
        return

    await update.message.reply_text(
        "I can set reminders or add events to your calendar.\n"
        "Try: _Remind me to call mom tomorrow at 3pm_\n"
        "Or: _Dentist appointment March 20 at 4pm, add to my calendar and remind me an hour earlier_",
        parse_mode="Markdown",
    )


async def _handle_reminder(update: Update, text: str) -> None:
    """Schedule a reminder with no calendar event."""
    title, dt = parse_reminder(text)
    if dt is None:
        await update.message.reply_text(
            "I couldn't figure out the time. Try: 'remind me to call mom tomorrow at 3pm'."
        )
        return

    job_id = schedule_reminder(title=title, scheduled_at=dt, original_text=text)
    time_str = dt.strftime("%A, %b %d at %I:%M %p %Z")
    await update.message.reply_text(
        f"Got it! I'll remind you to *{title}* on {time_str}.",
        parse_mode="Markdown",
    )


async def _handle_calendar_only(update: Update, text: str) -> None:
    """Create a Google Calendar event with no Telegram reminder."""
    title, dt = parse_event_time(text)
    if dt is None:
        await update.message.reply_text(
            "I couldn't figure out the date/time for the calendar event."
        )
        return

    event_id = create_event(title, dt)
    time_str = dt.strftime("%A, %b %d at %I:%M %p %Z")
    if event_id:
        await update.message.reply_text(
            f"Added *{title}* to your Google Calendar on {time_str}.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("Failed to create the calendar event. Check the logs.")


async def _handle_calendar_and_reminder(update: Update, text: str) -> None:
    """Create a calendar event at the event time and a reminder (with optional offset)."""
    from bot.parser import parse_time_offset, parse_event_time
    from datetime import timedelta

    # Parse event time (without applying offset)
    title, event_dt = parse_event_time(text)
    if event_dt is None:
        await update.message.reply_text("I couldn't figure out the date/time.")
        return

    # Create calendar event at the full event time
    event_id = create_event(title, event_dt)

    # Reminder time = event_dt minus any offset ("an hour earlier")
    offset = parse_time_offset(text)
    reminder_dt = event_dt - offset if offset else event_dt

    job_id = schedule_reminder(title=title, scheduled_at=reminder_dt, original_text=text)

    # Link calendar event to reminder row
    if event_id:
        with get_session() as session:
            row = session.query(Reminder).filter_by(job_id=job_id).first()
            if row:
                row.calendar_event_id = event_id
                session.commit()

    event_str = event_dt.strftime("%A, %b %d at %I:%M %p %Z")
    remind_str = reminder_dt.strftime("%A, %b %d at %I:%M %p %Z")
    cal_note = " Added to Google Calendar." if event_id else " (Calendar event failed.)"
    offset_note = f" I'll remind you at {remind_str}." if offset else ""

    await update.message.reply_text(
        f"*{title}* scheduled for {event_str}.{cal_note}{offset_note}",
        parse_mode="Markdown",
    )


async def _handle_done(update: Update) -> None:
    """Dismiss the last active reminder."""
    last = get_last_active()
    if not last["job_id"]:
        await update.message.reply_text("No active reminder to dismiss.")
        return

    cancel_followup(last["job_id"])
    await update.message.reply_text(f"Got it — *{last['title']}* dismissed.", parse_mode="Markdown")


async def _handle_postpone(update: Update, text: str) -> None:
    """Reschedule the last active reminder to a new time."""
    last = get_last_active()
    if not last["job_id"]:
        await update.message.reply_text("No active reminder to postpone.")
        return

    new_dt = parse_postpone_time(text)
    if new_dt is None:
        await update.message.reply_text(
            "I couldn't figure out the new time. Try: 'postpone to tomorrow at 5pm'."
        )
        return

    new_job_id = reschedule_reminder(
        old_job_id=last["job_id"],
        title=last["title"],
        new_dt=new_dt,
    )
    time_str = new_dt.strftime("%A, %b %d at %I:%M %p %Z")
    await update.message.reply_text(
        f"Rescheduled *{last['title']}* to {time_str}.",
        parse_mode="Markdown",
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list — show all pending reminders."""
    if not _authorised(update):
        return

    reminders = list_reminders()
    if not reminders:
        await update.message.reply_text("No reminders set.")
        return

    lines = []
    for r in reminders:
        time_str = r.scheduled_at.strftime("%b %d, %Y %I:%M %p %Z")
        lines.append(f"• *{r.title}* — {time_str}\n  ID: `{r.job_id}`")

    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel <job_id> — remove a scheduled reminder."""
    if not _authorised(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /cancel <job_id>")
        return

    job_id = context.args[0]

    with get_session() as session:
        row = session.query(Reminder).filter_by(job_id=job_id).first()
        if row and row.calendar_event_id:
            from bot.calendar_client import delete_event
            delete_event(row.calendar_event_id)

    found = cancel_reminder(job_id)
    if found:
        await update.message.reply_text(f"Reminder `{job_id}` cancelled.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"No reminder found with ID `{job_id}`.", parse_mode="Markdown")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — greet the user."""
    if not _authorised(update):
        return
    await update.message.reply_text(
        "Hi! Here's what I can do:\n\n"
        "*Set a reminder:*\n_Remind me to call mom tomorrow at 3pm_\n\n"
        "*Add to calendar:*\n_Dentist March 20 at 4pm, add to my calendar_\n\n"
        "*Reminder + calendar:*\n_Dentist March 20 at 4pm, add to my calendar and remind me an hour earlier_\n\n"
        "When a reminder fires, use the buttons to dismiss, snooze, or reschedule.\n"
        "You can also reply *done* or *postpone to [time]* as text.\n\n"
        "Commands:\n"
        "/list — view all reminders\n"
        "/cancel <id> — cancel a reminder",
        parse_mode="Markdown",
    )


# --- Inline keyboard callback handlers ---

async def handle_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ✅ Done button: cancel follow-up, remove DB row, collapse message."""
    query = update.callback_query
    await query.answer()
    job_id = query.data.split(":", 1)[1]
    cancel_reminder(job_id)
    await query.edit_message_text("✅ Dismissed.")


async def handle_snooze_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ⏰ Snooze 30min button: reschedule to now+30min in user's timezone."""
    query = update.callback_query
    await query.answer()
    job_id = query.data.split(":", 1)[1]

    row = get_reminder_by_job_id(job_id)
    if not row:
        await query.edit_message_text("Reminder not found — already dismissed?")
        return

    tz = pytz.timezone(config.TIMEZONE)
    new_dt = datetime.now(tz) + timedelta(minutes=30)
    reschedule_reminder(old_job_id=job_id, title=row.title, new_dt=new_dt)
    time_str = new_dt.strftime("%I:%M %p %Z")
    await query.edit_message_text(
        f"⏰ Snoozed — I'll remind you about *{row.title}* at {time_str}.",
        parse_mode="Markdown",
    )


async def handle_custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for custom reschedule: store job context and prompt for new time."""
    query = update.callback_query
    await query.answer()
    job_id = query.data.split(":", 1)[1]

    row = get_reminder_by_job_id(job_id)
    if not row:
        await query.edit_message_text("Reminder not found.")
        return ConversationHandler.END

    context.user_data["postpone_job_id"] = job_id
    context.user_data["postpone_title"] = row.title
    await query.edit_message_reply_markup(reply_markup=None)  # clear buttons
    await query.message.reply_text("When should I reschedule? (e.g. 'tomorrow at 5pm')")
    return WAITING_CUSTOM_TIME


async def handle_custom_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive the user's typed time and reschedule the reminder."""
    job_id = context.user_data.get("postpone_job_id")
    title = context.user_data.get("postpone_title")

    if not job_id or not title:
        await update.message.reply_text("Something went wrong. Tap the button again.")
        return ConversationHandler.END

    new_dt = parse_postpone_time(update.message.text)
    if new_dt is None:
        await update.message.reply_text(
            "Couldn't parse that time. Try again (e.g. 'tomorrow at 5pm') or /cancel."
        )
        return WAITING_CUSTOM_TIME  # keep conversation alive for retry

    reschedule_reminder(old_job_id=job_id, title=title, new_dt=new_dt)
    time_str = new_dt.strftime("%A, %b %d at %I:%M %p %Z")
    await update.message.reply_text(
        f"Rescheduled *{title}* to {time_str}.", parse_mode="Markdown"
    )
    context.user_data.pop("postpone_job_id", None)
    context.user_data.pop("postpone_title", None)
    return ConversationHandler.END
