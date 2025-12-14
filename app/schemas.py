from datetime import datetime
from typing import Optional, Literal

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

