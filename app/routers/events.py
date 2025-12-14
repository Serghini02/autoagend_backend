from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
from dateutil.rrule import rrulestr

from ..database import get_db
from ..deps import get_current_user
from .. import models, schemas
from ..ai_events import parse_text_to_event
from .notes import parse_when_to_datetime, normalize_time_text

router = APIRouter(prefix="/events", tags=["events"])


def _combine_date_time(base_dt: datetime, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(base_dt.year, base_dt.month, base_dt.day, h, m)


def _weekday_rrule_guard(rrule: str) -> str:
    # Normalización ligera: espacios fuera
    return re.sub(r"\s+", "", rrule.strip())


@router.post("/", response_model=schemas.EventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="end_at debe ser posterior a start_at")

    ev = models.Event(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        start_at=payload.start_at,
        end_at=payload.end_at,
        rrule=payload.rrule,
        timezone=payload.timezone or "Europe/Madrid",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


@router.post("/from-text", response_model=schemas.EventRead, status_code=status.HTTP_201_CREATED)
def create_event_from_text(
    text: str = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tzname = "Europe/Madrid"
    now = datetime.now(ZoneInfo(tzname))
    now_iso = now.isoformat()

    parsed = parse_text_to_event(texto=text, now_iso=now_iso, timezone=tzname)

    start_time = normalize_time_text(parsed.get("start_time"))
    end_time = normalize_time_text(parsed.get("end_time"))
    duration_minutes = int(parsed.get("duration_minutes") or 30)

    rrule = parsed.get("rrule")
    if rrule:
        rrule = _weekday_rrule_guard(rrule)

    # Si hay rrule pero la IA no puso date_text, permitimos continuar (anclaje automático)
    date_text = parsed.get("date_text")

    # Requisito mínimo: siempre necesitamos hora de inicio
    if not start_time:
        raise HTTPException(
            status_code=422,
            detail="No pude extraer la hora de inicio. Ej: 'cada lunes a las 19' o 'martes 16:00'.",
        )

    # Caso 1: tenemos date_text -> usamos el parser habitual
    if date_text:
        when_text = f"{date_text} a las {start_time}"
        start_dt = parse_when_to_datetime(
            when_text=when_text,
            now=now,
            tzname=tzname,
            date_text=date_text,
            time_text=start_time,
        )
        if start_dt is None:
            raise HTTPException(status_code=422, detail="No pude resolver la fecha/hora a un datetime válido.")
    else:
        # Caso 2: NO hay date_text, pero SI hay rrule:
        # anclamos la primera ocurrencia al próximo instante válido (now -> futuro) usando rrule + start_time
        if not rrule:
            raise HTTPException(
                status_code=422,
                detail="No pude extraer fecha. Prueba: 'el martes a las 16:00' o añade recurrencia: 'cada lunes a las 19'.",
            )

        ev_tz = tzname
        # dtstart aware: hoy a la hora start_time (si ya pasó, mañana a esa hora)
        now_local = now.astimezone(ZoneInfo(ev_tz)).replace(tzinfo=None)
        h, m = map(int, start_time.split(":"))
        candidate = datetime(now_local.year, now_local.month, now_local.day, h, m)
        if candidate <= now_local:
            candidate = candidate + timedelta(days=1)

        dtstart_aware = candidate.replace(tzinfo=ZoneInfo(ev_tz))
        rule = rrulestr(rrule, dtstart=dtstart_aware)
        occ = rule.after(dtstart_aware - timedelta(seconds=1), inc=True)
        if occ is None:
            raise HTTPException(status_code=422, detail="No pude generar la primera ocurrencia de la recurrencia.")
        start_dt = occ.astimezone(ZoneInfo(ev_tz)).replace(tzinfo=None)

    # end_at
    if end_time:
        end_dt = _combine_date_time(start_dt, end_time)
        if end_dt <= start_dt:
            raise HTTPException(status_code=422, detail="La hora de fin debe ser posterior a la hora de inicio.")
    else:
        end_dt = start_dt + timedelta(minutes=duration_minutes)

    ev = models.Event(
        user_id=current_user.id,
        title=parsed["title"],
        description=parsed["description"],
        start_at=start_dt,
        end_at=end_dt,
        rrule=rrule,
        timezone=tzname,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev



@router.get("/", response_model=List[schemas.EventRead])
def list_events(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Event)
        .filter(models.Event.user_id == current_user.id)
        .order_by(models.Event.start_at.desc())
        .all()
    )


@router.get("/{event_id}", response_model=schemas.EventRead)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ev = (
        db.query(models.Event)
        .filter(models.Event.user_id == current_user.id, models.Event.id == event_id)
        .first()
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return ev


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ev = (
        db.query(models.Event)
        .filter(models.Event.user_id == current_user.id, models.Event.id == event_id)
        .first()
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    db.delete(ev)
    db.commit()
    return None
