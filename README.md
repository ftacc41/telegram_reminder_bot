# Telegram Reminder Bot

A personal Telegram bot that accepts natural language reminders, fires them at the right time, and optionally creates Google Calendar events — all without an LLM. 100% Free (As of March 23, 2026)

**"Remind me to call the dentist tomorrow at 10am"**
**"Dentist March 20 at 4pm, add to my calendar and remind me an hour earlier"**

When a reminder fires you get inline buttons to dismiss it, snooze 30 minutes, pick a custom time, or cancel it.

---

## Features

- Natural language scheduling via [dateparser](https://dateparser.readthedocs.io/)
- Reminders persist across restarts (APScheduler + Postgres)
- Google Calendar event creation with optional reminder offset
- Inline keyboard buttons on every reminder: ✅ Done · ⏰ Snooze 30min · 🕒 Custom time · ❌ Cancel
- Single-user — all messages from unknown Telegram IDs are silently ignored

---

## Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Your Telegram user ID (e.g. from [@userinfobot](https://t.me/userinfobot))
- A Google Cloud project with the Calendar API enabled and an OAuth 2.0 Desktop client credentials file
- (Production) A [Railway](https://railway.app) account with a Postgres plugin

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/your-username/reminder_bot.git
cd reminder_bot
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=   # from BotFather
USER_CHAT_ID=         # your Telegram numeric user ID
GOOGLE_TOKEN_JSON=    # generated in the next step
TIMEZONE=             # e.g. America/Chicago  (see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
DATABASE_URL=         # leave as sqlite:///./reminders.db for local dev
```

### 3. Authenticate Google Calendar (one-time)

1. Download your OAuth 2.0 credentials from [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → your Desktop client → **Download JSON**
2. Save the file to `~/.config/reminderbot/client_secret.json`
3. Run the OAuth flow:
   ```bash
   python setup_oauth.py
   ```
4. A browser window will open — approve access, then copy the printed JSON string into `GOOGLE_TOKEN_JSON` in your `.env`.

### 4. Run locally

```bash
python main.py
```

---

## Deploy to Railway

1. Push the repo to GitHub
2. Create a new Railway project → **Deploy from GitHub repo**
3. Add a **Postgres** plugin — `DATABASE_URL` is injected automatically
4. Set the remaining environment variables under **Variables**:
   - `TELEGRAM_BOT_TOKEN`
   - `USER_CHAT_ID`
   - `GOOGLE_TOKEN_JSON`
   - `TIMEZONE`
5. Railway uses the `Procfile` to start the worker: `python main.py`

---

## Usage

| Input | What happens |
|-------|-------------|
| `Remind me to call mom tomorrow at 3pm` | Sets a one-off Telegram reminder |
| `Remind me every weekday to do wrist exercises at 10am` | Sets a recurring reminder (Mon–Fri) |
| `Remind me every Monday at 9am to review emails` | Sets a weekly recurring reminder |
| `Daily standup reminder at 9:30am` | Recurring every day |
| `Dentist March 20 at 4pm, add to my calendar` | Creates a Google Calendar event |
| `Dentist March 20 at 4pm, add to my calendar and remind me an hour earlier` | Calendar event at 4pm + reminder at 3pm |
| `/list` | Show all pending reminders, each with inline action buttons |
| `/cancel <id>` | Cancel a reminder (and its calendar event if linked) |
| `/clearjobs` | Cancel all scheduled jobs (use to clear stuck reminders) |

Every confirmation reply includes the job ID so you can cancel immediately, e.g. `Cancel: /cancel ab3x9k7m`.

When a reminder fires, tap the inline buttons to dismiss, snooze 30 minutes, or enter a custom reschedule time. Text replies `done` and `postpone to [time]` also work as fallbacks.

---

## Project Structure

```
main.py               Entry point
config.py             Env var loading
bot/
  handlers.py         Telegram message + callback handlers
  parser.py           Intent detection + datetime extraction
  scheduler.py        APScheduler helpers (schedule/cancel/reschedule)
  reminder_job.py     Functions APScheduler calls to send reminders
  calendar_client.py  Google Calendar API wrapper
db/
  models.py           SQLAlchemy Reminder table
setup_oauth.py        One-time Google OAuth token generator
```

---

## Security Notes

- `.env`, `credentials.json`, and `token.json` are in `.gitignore` and should never be committed
- `GOOGLE_TOKEN_JSON` contains a refresh token — treat it as a secret
- The bot rejects all messages from users other than `USER_CHAT_ID`

---

## License

MIT
