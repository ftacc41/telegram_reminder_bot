import json
import logging
from datetime import datetime
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _get_service():
    """Build an authenticated Google Calendar service from the stored token JSON."""
    token_data = json.loads(config.GOOGLE_TOKEN_JSON)
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    return build("calendar", "v3", credentials=creds)


def create_event(title: str, scheduled_at: datetime) -> "Optional[str]":
    """Create a 30-minute Google Calendar event. Returns the event ID or None on failure."""
    try:
        service = _get_service()
        start = scheduled_at.isoformat()
        # Default 30-minute duration
        from datetime import timedelta
        end = (scheduled_at + timedelta(minutes=30)).isoformat()

        event = {
            "summary": title,
            "start": {"dateTime": start, "timeZone": config.TIMEZONE},
            "end": {"dateTime": end, "timeZone": config.TIMEZONE},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        event_id = created.get("id")
        logger.info("Created calendar event id=%s", event_id)
        return event_id
    except Exception:
        logger.exception("Failed to create calendar event for '%s'", title)
        return None


def delete_event(event_id: str) -> bool:
    """Delete a Google Calendar event by ID. Returns True on success."""
    try:
        service = _get_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        logger.info("Deleted calendar event id=%s", event_id)
        return True
    except Exception:
        logger.exception("Failed to delete calendar event id=%s", event_id)
        return False
