# reminder_bot — Project Context

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
- `bot/reminder_job.py` function `send_reminder` must never be renamed/moved — APScheduler serializes it by import path

## Environment Variables
```
TELEGRAM_BOT_TOKEN=
USER_CHAT_ID=
GOOGLE_TOKEN_JSON=    # JSON string from setup_oauth.py
TIMEZONE=             # e.g. America/Chicago
DATABASE_URL=         # injected by Railway; use sqlite:///./reminders.db locally
```

## Local Development
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in values
python main.py
```

## Deploy
- Hosted on Railway as a worker process (see Procfile)
- Attach Railway Postgres plugin — DATABASE_URL is injected automatically
- Run setup_oauth.py locally once to generate GOOGLE_TOKEN_JSON

## Module Overview
| File | Responsibility |
|------|---------------|
| `main.py` | Entry point: init DB → start scheduler → run bot |
| `config.py` | Load and expose all env vars |
| `bot/handlers.py` | Telegram message/command handlers |
| `bot/parser.py` | Intent detection + datetime extraction |
| `bot/scheduler.py` | APScheduler init + schedule/cancel helpers |
| `bot/reminder_job.py` | Function APScheduler calls to send reminders |
| `bot/calendar_client.py` | Google Calendar API wrapper |
| `db/models.py` | SQLAlchemy Reminder table |
| `setup_oauth.py` | One-time local script to generate Google OAuth token |
