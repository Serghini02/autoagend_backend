from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..ai_reminders import analyze_reminder_intent, generate_reminder_question

router = APIRouter(prefix="/reminders", tags=["reminders"])

# Simu-DB in memory for conversation state (in production use Redis)
CONVERSATIONS: Dict[str, Dict[str, Any]] = {}

@router.post("/analyze", response_model=Dict[str, Any])
def analyze_intent(
    req: schemas.ReminderAnalyzeRequest,
    current_user: models.User = Depends(get_current_user),
):
    tzname = "Europe/Madrid" # TODO: get from user prefs
    now_iso = datetime.now(ZoneInfo(tzname)).isoformat()
    return analyze_reminder_intent(req.text, now_iso, tzname)

@router.post("/conversation/start", response_model=schemas.ConversationResponse)
def start_conversation(
    req: schemas.ConversationStartRequest,
    current_user: models.User = Depends(get_current_user),
):
    conv_id = str(uuid.uuid4())
    tzname = "Europe/Madrid"
    now_iso = datetime.now(ZoneInfo(tzname)).isoformat()

    # Initial context based on analysis or passed context
    context = req.context or {}
    context["original_text"] = req.text
    
    # Add initial system message mock to history
    history = [
        {"role": "user", "content": req.text}
    ]

    ai_resp = generate_reminder_question(history, context, now_iso, tzname)
    
    # Save state
    CONVERSATIONS[conv_id] = {
        "user_id": current_user.id,
        "history": history,
        "context": context,
        "step": ai_resp.get("next_step", "initial")
    }
    
    # Update context with any extracted data if AI did it
    if "extracted_data_update" in ai_resp:
        context.update(ai_resp["extracted_data_update"])

    replies = []
    for qr in ai_resp.get("quick_replies", []):
        replies.append(schemas.QuickReply(**qr))

    return schemas.ConversationResponse(
        conversation_id=conv_id,
        message=ai_resp.get("message", ""),
        quick_replies=replies,
        next_step=ai_resp.get("next_step", "initial"),
        context=context
    )

@router.post("/conversation/{conv_id}/respond", response_model=schemas.ConversationResponse)
def respond(
    conv_id: str,
    req: schemas.ConversationReplyRequest,
    current_user: models.User = Depends(get_current_user),
):
    if conv_id not in CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    
    state = CONVERSATIONS[conv_id]
    if state["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    # Update history
    user_msg = req.text or (req.selected_option.get("label") if req.selected_option else "Opción seleccionada")
    state["history"].append({"role": "user", "content": user_msg})
    
    # Update context
    context = state["context"]
    if req.context:
        context.update(req.context)
    if req.selected_option:
         # Merge selected option value into context
         # Assuming value is a dict like {"time": "09:00"}
         if "value" in req.selected_option:
             context.update(req.selected_option["value"])

    tzname = "Europe/Madrid"
    now_iso = datetime.now(ZoneInfo(tzname)).isoformat()

    ai_resp = generate_reminder_question(state["history"], context, now_iso, tzname)
    
    # Add AI response to history
    state["history"].append({"role": "assistant", "content": ai_resp.get("message", "")})
    state["step"] = ai_resp.get("next_step", "ongoing")
    
    if "extracted_data_update" in ai_resp:
        context.update(ai_resp["extracted_data_update"])

    replies = []
    for qr in ai_resp.get("quick_replies", []):
        replies.append(schemas.QuickReply(**qr))

    return schemas.ConversationResponse(
        conversation_id=conv_id,
        message=ai_resp.get("message", ""),
        quick_replies=replies,
        next_step=ai_resp.get("next_step", "ongoing"),
        context=context
    )

@router.post("/", response_model=schemas.ReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: schemas.ReminderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rem = models.Reminder(
        user_id=current_user.id,
        task_id=payload.task_id,
        title=payload.title,
        description=payload.description,
        deadline=payload.deadline,
        remind_at=payload.remind_at,
        frequency=payload.frequency or "once",
        rrule=payload.rrule,
    )
    db.add(rem)
    db.commit()
    db.refresh(rem)
    return rem

@router.get("/", response_model=List[schemas.ReminderRead])
def list_reminders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Reminder)
        .filter(models.Reminder.user_id == current_user.id)
        .order_by(models.Reminder.remind_at.asc())
        .all()
    )
