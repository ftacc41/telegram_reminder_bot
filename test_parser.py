"""
Run with: python test_parser.py
Tests parser logic without needing Telegram or a scheduler.
"""
import os
os.environ.setdefault("TIMEZONE", "America/Chicago")
os.environ.setdefault("DATABASE_URL", "sqlite:///./reminders.db")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
os.environ.setdefault("USER_CHAT_ID", "0")

from bot.parser import (
    is_reminder_intent,
    parse_recurrence,
    parse_recurrence_reminder,
    parse_reminder,
)

CASES = [
    # Recurring
    "Remind me every weekday to do wrist exercises at 10am",
    "remind me every day at 9am to drink water",
    "every Monday at 8am remind me to review emails",
    "daily standup reminder at 9:30am",
    "remind me every Friday at 5pm to submit timesheet",
    # One-off
    "remind me to call mom tomorrow at 3pm",
    "remind me to take meds at 8pm tonight",
    # Edge cases
    "Remind me every weekday to do wrist exercises at 10am",  # original failing case
]

SEP = "-" * 60

for text in CASES:
    print(SEP)
    print(f"INPUT:      {text!r}")
    print(f"is_remind:  {is_reminder_intent(text)}")

    rec = parse_recurrence(text)
    print(f"recurrence: {rec}")

    rec_full = parse_recurrence_reminder(text)
    if rec_full:
        title, cron_kwargs, label, hour, minute = rec_full
        print(f"  → title={title!r}  label={label!r}  time={hour:02d}:{minute:02d}  cron={cron_kwargs}")
    else:
        # Fall through to one-off parser
        title, dt = parse_reminder(text)
        print(f"  → one-off: title={title!r}  dt={dt}")

print(SEP)
