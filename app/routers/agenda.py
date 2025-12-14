from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo
from dateutil.rrule import rrulestr

from ..database import get_db
from ..deps import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/agenda", tags=["agenda"])


def _ensure_aware(dt: datetime, tzname: str) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo(tzname))
    return dt


def _to_local_naive(dt: datetime, tzname: str) -> datetime:
    return _ensure_aware(dt, tzname).astimezone(ZoneInfo(tzname)).replace(tzinfo=None)


@router.get("/", response_model=list[schemas.AgendaItem])
def get_agenda(
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tzname = "Europe/Madrid"
    from_local = _to_local_naive(from_dt, tzname)
    to_local = _to_local_naive(to_dt, tzname)

    items: list[schemas.AgendaItem] = []

    # TAREAS
    tasks = (
        db.query(models.Task)
        .filter(
            models.Task.user_id == current_user.id,
            models.Task.date.isnot(None),
            models.Task.date >= from_local,
            models.Task.date <= to_local,
        )
        .order_by(models.Task.date.asc())
        .all()
    )
    for t in tasks:
        items.append(
            schemas.AgendaItem(
                type="task",
                id=t.id,
                title=t.title,
                description=t.description,
                date=t.date,
                channel=t.channel,
                status=t.status,
            )
        )

    # EVENTOS (puntuales + recurrentes)
    events = (
        db.query(models.Event)
        .filter(models.Event.user_id == current_user.id)
        .order_by(models.Event.start_at.asc())
        .all()
    )

    for ev in events:
        duration = ev.end_at - ev.start_at

        if not ev.rrule:
            # Puntual: incluir si solapa rango
            if ev.end_at >= from_local and ev.start_at <= to_local:
                items.append(
                    schemas.AgendaItem(
                        type="event",
                        id=ev.id,
                        title=ev.title,
                        description=ev.description,
                        start_at=ev.start_at,
                        end_at=ev.end_at,
                        rrule=None,
                        timezone=ev.timezone,
                        is_occurrence=False,
                    )
                )
            continue

        # Recurrente: expandir ocurrencias
        ev_tz = ev.timezone or tzname
        dtstart_aware = ev.start_at.replace(tzinfo=ZoneInfo(ev_tz))
        rule = rrulestr(ev.rrule, dtstart=dtstart_aware)

        range_start_aware = from_local.replace(tzinfo=ZoneInfo(ev_tz))
        range_end_aware = to_local.replace(tzinfo=ZoneInfo(ev_tz))

        occs = rule.between(range_start_aware, range_end_aware, inc=True)

        for occ in occs:
            occ_local = occ.astimezone(ZoneInfo(ev_tz)).replace(tzinfo=None)
            occ_end = occ_local + duration

            if occ_end >= from_local and occ_local <= to_local:
                items.append(
                    schemas.AgendaItem(
                        type="event",
                        id=ev.id,
                        title=ev.title,
                        description=ev.description,
                        start_at=occ_local,
                        end_at=occ_end,
                        rrule=ev.rrule,
                        timezone=ev.timezone,
                        is_occurrence=True,  # <- clave
                    )
                )

    # Orden
    def sort_key(x: schemas.AgendaItem):
        if x.type == "event" and x.start_at:
            return x.start_at
        if x.type == "task" and x.date:
            return x.date
        return datetime.max

    items.sort(key=sort_key)
    return items
