# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is
A personal Telegram bot that:
- Accepts natural language input ("remind me to call mom tomorrow at 3pm")
- Creates events in Google Calendar
- Sends Telegram reminder messages at scheduled times
- Persists reminders across restarts via Postgres + APScheduler

## Stack
- **python-telegram-bot v21** — async Telegram framework (polling)
- **dateparser** — natural language datetime parsing (no LLM)
- **APScheduler v3** + **SQLAlchemyJobStore** — persistent scheduling
- **google-api-python-client** + **google-auth-oauthlib** — Google Calendar
- **SQLAlchemy** — ORM + APScheduler backend
- **Railway Postgres** — production database
- **python-dotenv** — env var loading

## Key Constraints
- Single-user bot — all handlers reject unknown user IDs
- No LLM for parsing — dateparser + keyword matching only
- Never write persistent state to local files — Railway filesystem is ephemeral
- `bot/reminder_job.py::send_reminder` must never be renamed or moved — APScheduler serializes job references by import path; renaming breaks deserialization of persisted jobs

## Commands

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in values
python main.py         # run locally

python setup_oauth.py  # one-time: generate GOOGLE_TOKEN_JSON env var value
```

## Environment Variables
```
TELEGRAM_BOT_TOKEN=
USER_CHAT_ID=
GOOGLE_TOKEN_JSON=    # JSON string from setup_oauth.py
TIMEZONE=             # e.g. America/Chicago
DATABASE_URL=         # injected by Railway; use sqlite:///./reminders.db locally
```

## Architecture

### Startup sequence (`main.py`)
`init_db()` → `init_scheduler()` → register handlers → `run_polling()`

### Message routing (`bot/handlers.py`)
Plain text messages are routed by `handle_message` in priority order:
1. "done"/"dismiss"/"completed"/"finished" → cancel the follow-up job for the last active reminder
2. Postpone intent → reschedule last active reminder to a new time
3. Calendar + reminder intent → create Calendar event at event time, schedule Telegram reminder with optional offset
4. Reminder only → schedule Telegram reminder
5. Calendar only → create Calendar event, no reminder

### Dual persistence model
Each reminder is stored in two places that must stay in sync:
- **APScheduler job store** (in the `apscheduler_jobs` table via SQLAlchemyJobStore) — drives the actual job execution
- **`reminders` table** (via `db/models.py`) — stores human-readable metadata (title, original text, scheduled time, calendar event ID)

`cancel_reminder` and `reschedule_reminder` in `bot/scheduler.py` always clean up both.

### Inline button flow
`send_reminder` and `send_followup_check` attach a three-button keyboard to every reminder message (callback patterns: `done:<job_id>`, `snooze:<job_id>`, `custom:<job_id>`). The `custom:` button starts a `ConversationHandler` flow (`WAITING_CUSTOM_TIME` state) that prompts for a typed time, parses it, and calls `reschedule_reminder`. This `ConversationHandler` must be registered **before** the catch-all `MessageHandler` in `main.py`.

### Follow-up job pattern
When `send_reminder` fires, it immediately schedules a `followup_{job_id}` interval job (every 30 min) via `schedule_followup`; each tick calls `send_followup_check` (not `send_reminder`). Replying "done" or "postpone" calls `cancel_followup` to stop it. This avoids a circular import: `reminder_job.py` imports `schedule_followup` lazily inside the function body.

### `_last_active` state
`bot/reminder_job.py` holds an in-memory dict `_last_active` tracking the most recently fired reminder. This is what allows the user to say "done" or "postpone" without a job ID. It is process-local — not persisted.

### Natural language parsing (`bot/parser.py`)
- Intent detection: regex patterns (`_REMIND_PATTERNS`, `_CALENDAR_PATTERNS`, `_POSTPONE_PATTERNS`)
- Datetime extraction: `dateparser.search.search_dates` with `PREFER_DATES_FROM: future` and the configured `TIMEZONE`
- Time offset: `_OFFSET_PATTERNS` extracts phrases like "an hour earlier" → `timedelta` subtracted from event time

### Google Calendar (`bot/calendar_client.py`)
Reads credentials from `GOOGLE_TOKEN_JSON` (a JSON string). `setup_oauth.py` performs the OAuth flow locally and prints the token JSON to copy into the env var.

## Bot Commands
| Command | Behaviour |
|---------|-----------|
| `/start` | Help message with examples |
| `/list` | Show all pending reminders with job IDs |
| `/cancel <job_id>` | Remove reminder + its Calendar event if linked |
| `done` / `dismiss` / `completed` / `finished` | Dismiss last active reminder (stops follow-ups) |
| `postpone to <time>` | Reschedule last active reminder |

## Deploy
- Hosted on Railway as a worker process (see `Procfile`)
- Attach Railway Postgres plugin — `DATABASE_URL` is injected automatically
- Run `setup_oauth.py` locally once to generate `GOOGLE_TOKEN_JSON`
