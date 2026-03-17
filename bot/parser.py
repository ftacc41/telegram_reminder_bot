import re
import logging
from datetime import datetime, timedelta

import dateparser
import dateparser.search
import pytz

import config

logger = logging.getLogger(__name__)

# Keywords that signal a "set reminder" intent
_REMIND_PATTERNS = re.compile(
    r"\b(remind(er)?(\s+me)?|alert(\s+me)?|notify(\s+me)?|don't let me forget|set (a\s+)?reminder)\b",
    re.IGNORECASE,
)

# Keywords that signal a "add to calendar" intent
_CALENDAR_PATTERNS = re.compile(
    r"\b(add (it\s+)?to (my\s+)?(google\s+)?calendar|put (it\s+)?on (my\s+)?calendar|calendar event|schedule (it\s+)?on (my\s+)?calendar)\b",
    re.IGNORECASE,
)

# Offset phrasing like "an hour earlier", "30 minutes before"
_OFFSET_PATTERNS = re.compile(
    r"(an?\s+hour|(\d+)\s*hour[s]?|(\d+)\s*min(ute)?[s]?|half\s+an?\s+hour)\s+(earlier|before|prior)",
    re.IGNORECASE,
)

# Keywords that signal a postpone/reschedule intent
_POSTPONE_PATTERNS = re.compile(
    r"\b(postpone|move|reschedule|snooze|delay|push\s+back|push\s+it)\b",
    re.IGNORECASE,
)


def is_reminder_intent(text: str) -> bool:
    """Return True if the message looks like a request to set a reminder."""
    return bool(_REMIND_PATTERNS.search(text))


def has_calendar_intent(text: str) -> bool:
    """Return True if the message explicitly asks to add something to Google Calendar."""
    return bool(_CALENDAR_PATTERNS.search(text))


def is_postpone_intent(text: str) -> bool:
    """Return True if the message is asking to postpone/reschedule an active reminder."""
    return bool(_POSTPONE_PATTERNS.search(text))


def parse_time_offset(text: str) -> "timedelta | None":
    """
    Extract a time offset from phrases like 'an hour earlier' or '30 minutes before'.
    Returns a timedelta to subtract from the event time, or None if not found.
    """
    match = _OFFSET_PATTERNS.search(text)
    if not match:
        return None

    phrase = match.group(0).lower()

    if "half" in phrase:
        return timedelta(minutes=30)

    hours_match = re.search(r"(\d+)\s*hour", phrase)
    if hours_match:
        return timedelta(hours=int(hours_match.group(1)))

    if "an hour" in phrase or "a hour" in phrase:
        return timedelta(hours=1)

    mins_match = re.search(r"(\d+)\s*min", phrase)
    if mins_match:
        return timedelta(minutes=int(mins_match.group(1)))

    return None


def parse_reminder(text: str) -> "tuple":
    """
    Extract (title, datetime) from natural language input.
    Returns (None, None) if a datetime cannot be parsed.
    """
    settings = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": config.TIMEZONE,
    }

    # Find the intent phrase anywhere in the text and take everything after it
    intent_match = re.search(
        r"\b(remind(er)?(\s+me)?\s+(to\s+)?|alert(\s+me)?\s+(to\s+)?|"
        r"notify(\s+me)?\s+(to\s+)?|don't let me forget\s+(to\s+)?|set (a\s+)?reminder\s+(to\s+)?)",
        text, re.IGNORECASE,
    )
    body = text[intent_match.end():].strip() if intent_match else text

    # Strip calendar phrase from body before parsing time
    body_clean = _CALENDAR_PATTERNS.sub("", body).strip().rstrip(".,!? ")

    results = dateparser.search.search_dates(body_clean, settings=settings)
    if not results:
        results = dateparser.search.search_dates(text, settings=settings)
    if not results:
        logger.debug("Could not parse datetime from: %r", text)
        return None, None

    time_phrase, dt = results[-1]
    title = body_clean.replace(time_phrase, "").strip().rstrip(".,!? ")

    # Apply reminder offset if present (e.g. "an hour earlier")
    offset = parse_time_offset(text)
    if offset:
        dt = dt - offset

    logger.debug("Parsed reminder: title=%r dt=%s", title, dt)
    return title, dt


def parse_event_time(text: str) -> "tuple":
    """
    For calendar-only messages, extract (title, event_datetime).
    Returns (None, None) if datetime cannot be parsed.
    """
    settings = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": config.TIMEZONE,
    }

    # Strip calendar and reminder phrases to isolate the event description + time
    body = _CALENDAR_PATTERNS.sub("", text)
    body = _REMIND_PATTERNS.sub("", body).strip().rstrip(".,!? ")

    results = dateparser.search.search_dates(body, settings=settings)
    if not results:
        return None, None

    time_phrase, dt = results[-1]
    title = body.replace(time_phrase, "").strip().rstrip(".,!? ")
    return title, dt


def parse_postpone_time(text: str) -> "datetime | None":
    """Extract the new datetime from a postpone message like 'postpone to tomorrow at 3pm'."""
    settings = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": config.TIMEZONE,
    }

    # Strip the postpone keyword before parsing
    body = _POSTPONE_PATTERNS.sub("", text).strip()
    # Strip leading prepositions like "to", "until", "for"
    body = re.sub(r"^(to|until|for)\s+", "", body, flags=re.IGNORECASE).strip()

    results = dateparser.search.search_dates(body, settings=settings)
    if not results:
        return None

    _, dt = results[-1]
    return dt
