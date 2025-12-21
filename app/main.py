from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models  # asegura que se registran modelos

from .routers.auth import router as auth_router
from .routers.users import router as users_router
from .routers.tasks import router as tasks_router
from .routers.notes import router as notes_router
from .routers.events import router as events_router
from .routers.events import router as events_router
from .routers.agenda import router as agenda_router
from .routers.reminders import router as reminders_router

app = FastAPI(title="AutoAgenda AI", version="1.4.0")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.get("/ping")
def ping():
    return {"message": "pong"}

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tasks_router)
app.include_router(notes_router)
app.include_router(events_router)
app.include_router(events_router)
app.include_router(agenda_router)
app.include_router(reminders_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)