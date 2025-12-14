from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from zoneinfo import ZoneInfo

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..ai import parse_note_to_tasks
from .notes import build_when_text, parse_when_to_datetime

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/", response_model=schemas.TaskRead)
def create_task(
    task_in: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_task = models.Task(
        user_id=current_user.id,
        title=task_in.title,
        description=task_in.description,
        date=task_in.date,
        channel=task_in.channel,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@router.get("/", response_model=List[schemas.TaskRead])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Task)
        .filter(models.Task.user_id == current_user.id)
        .order_by(models.Task.created_at.desc())
        .all()
    )


@router.post("/from-text")
def create_tasks_from_text(
    text: str = Body(...),
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

    return {"message": "Tareas creadas desde texto", "count": len(created_tasks), "tasks": created_tasks}
