from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import dateparser
import re

from ..database import get_db
from .. import models
from ..ai import parse_note_to_tasks
from ..deps import get_current_user

router = APIRouter(prefix="/notes", tags=["notes"])

_WEEKDAYS_ES = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}


def normalize_time_text(time_text: str | None) -> str | None:
    if not time_text:
        return None
    s = time_text.strip().lower().replace(".", ":")
    s = re.sub(r"h$", "", s).strip()

    if re.fullmatch(r"\d{1,2}", s):
        h = int(s)
        if 0 <= h <= 23:
            return f"{h:02d}:00"
        return None

    m = re.fullmatch(r"(\d{1,2}):(\d{1,2})", s)
    if m:
        h = int(m.group(1)); mi = int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return f"{h:02d}:{mi:02d}"
        return None

    if re.fullmatch(r"\d{2}:\d{2}", s):
        return s
    return None


def build_when_text(date_text: str | None, time_text: str | None, day_part: str | None) -> str | None:
    if not date_text and not time_text and not day_part:
        return None

    default_by_part = {"morning": "10:00", "noon": "13:00", "afternoon": "16:00", "night": "20:00"}

    hhmm = normalize_time_text(time_text)
    if not hhmm and day_part in default_by_part:
        hhmm = default_by_part[day_part]

    if date_text and hhmm:
        return f"{date_text} a las {hhmm}"
    if date_text and not hhmm:
        return date_text
    if not date_text and hhmm:
        return f"hoy a las {hhmm}"
    return None


def _resolve_weekday_es(date_text: str | None, time_hhmm: str | None, now_local: datetime) -> datetime | None:
    if not date_text or not time_hhmm:
        return None

    dt = date_text.strip().lower()
    found = None
    for name, idx in _WEEKDAYS_ES.items():
        if re.search(rf"\b{name}\b", dt):
            found = idx
            break
    if found is None:
        return None

    h, m = map(int, time_hhmm.split(":"))
    today_idx = now_local.weekday()
    days_ahead = (found - today_idx) % 7
    candidate_date = now_local.date() + timedelta(days=days_ahead)
    candidate_dt = datetime(candidate_date.year, candidate_date.month, candidate_date.day, h, m)

    if days_ahead == 0 and candidate_dt <= now_local:
        candidate_dt += timedelta(days=7)
    if candidate_dt <= now_local:
        candidate_dt += timedelta(days=7)
    return candidate_dt


def parse_when_to_datetime(
    when_text: str | None,
    now: datetime,
    tzname: str,
    date_text: str | None = None,
    time_text: str | None = None,
) -> datetime | None:
    now_local = now.astimezone(ZoneInfo(tzname)).replace(tzinfo=None)
    time_hhmm = normalize_time_text(time_text)

    resolved = _resolve_weekday_es(date_text, time_hhmm, now_local)
    if resolved is not None:
        return resolved

    if not when_text:
        return None

    settings = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": now,
        "TIMEZONE": tzname,
        "RETURN_AS_TIMEZONE_AWARE": True,
    }

    dt = dateparser.parse(when_text, languages=["es"], settings=settings)
    if dt is None:
        return None

    dt_local = dt.astimezone(ZoneInfo(tzname)).replace(tzinfo=None)
    if dt_local < now_local:
        return None
    return dt_local


@router.post("/text")
def parse_note_text(
    text: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tzname = "Europe/Madrid"
    now = datetime.now(ZoneInfo(tzname))
    now_iso = now.isoformat()

    tasks_data = parse_note_to_tasks(texto=text, now_iso=now_iso, timezone=tzname)

    created_tasks = []
    for t in tasks_data:
        when_text = build_when_text(t.get("date_text"), t.get("time_text"), t.get("day_part"))
        dt = parse_when_to_datetime(
            when_text=when_text,
            now=now,
            tzname=tzname,
            date_text=t.get("date_text"),
            time_text=t.get("time_text"),
        )

        nueva = models.Task(
            user_id=current_user.id,
            title=t["title"],
            description=t["description"],
            date=dt,
            channel=t.get("channel"),
        )
        db.add(nueva)
        db.commit()
        db.refresh(nueva)
        created_tasks.append(nueva)

    return {"message": "Tareas creadas desde nota", "count": len(created_tasks), "tasks": created_tasks}
