from datetime import datetime
from typing import Optional, Literal, List, Dict, Any

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    date: Optional[datetime] = None
    channel: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskRead(TaskBase):
    id: int
    user_id: int
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_at: datetime
    end_at: datetime
    rrule: Optional[str] = None
    timezone: Optional[str] = "Europe/Madrid"


class EventRead(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    start_at: datetime
    end_at: datetime
    rrule: Optional[str] = None
    timezone: str
    created_at: datetime

    class Config:
        from_attributes = True


class ReminderCreate(BaseModel):
    title: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    remind_at: datetime
    frequency: Optional[str] = "once"
    rrule: Optional[str] = None
    task_id: Optional[int] = None


class ReminderRead(BaseModel):
    id: int
    user_id: int
    task_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    remind_at: datetime
    frequency: str
    rrule: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ReminderAnalyzeRequest(BaseModel):
    text: str


class ConversationStartRequest(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None


class ConversationReplyRequest(BaseModel):
    text: Optional[str] = None
    selected_option: Optional[Dict[str, Any]] = None # Para quick replies
    context: Optional[Dict[str, Any]] = None


class QuickReply(BaseModel):
    id: str
    label: str
    value: Dict[str, Any]


class ConversationResponse(BaseModel):
    conversation_id: str
    message: str
    quick_replies: List[QuickReply] = []
    next_step: str
    context: Dict[str, Any]


class AgendaItem(BaseModel):
    type: Literal["task", "event"]
    id: int
    title: str
    description: Optional[str] = None

    # Task
    date: Optional[datetime] = None
    channel: Optional[str] = None
    status: Optional[str] = None

    # Event occurrence
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    # Event metadata (para depurar y UI)
    rrule: Optional[str] = None
    timezone: Optional[str] = None
    is_occurrence: bool = False
