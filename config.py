import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
USER_CHAT_ID: int = int(os.environ["USER_CHAT_ID"])

# Google Calendar
GOOGLE_TOKEN_JSON: str = os.environ["GOOGLE_TOKEN_JSON"]

# Scheduling
TIMEZONE: str = os.getenv("TIMEZONE", "America/Argentina/Buenos_Aires")

# Database — Railway injects DATABASE_URL for Postgres; use sqlite locally
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./reminders.db")
