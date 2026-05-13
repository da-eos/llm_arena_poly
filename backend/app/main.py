import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.events import router as events_router
from app.api.predictions import router as predictions_router
from app.db import engine
from app.scheduler import start_scheduler, stop_scheduler
from app.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("db connection ok")
    start_scheduler()
    yield
    stop_scheduler()
    await engine.dispose()


app = FastAPI(title="LLM Arena", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(events_router)
app.include_router(predictions_router)
app.include_router(admin_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
