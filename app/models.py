from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Guardamos naive local
    date = Column(DateTime, nullable=True)

    channel = Column(String, nullable=True)

    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Guardamos naive local
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)

    # RRULE iCal opcional (ej: "FREQ=WEEKLY;BYDAY=MO")
    rrule = Column(String, nullable=True)

    timezone = Column(String, nullable=False, default="Europe/Madrid")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Fecha límite de la tarea original (si existe)
    deadline = Column(DateTime, nullable=True)
    
    # Cuándo debe sonar el recordatorio
    remind_at = Column(DateTime, nullable=False)
    
    frequency = Column(String, default="once") # once, daily, weekly, monthly
    rrule = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    task = relationship("Task")
