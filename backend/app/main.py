"""FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import SessionLocal, init_db
from .routes import api_router
from .service import ensure_default_config, sync_all
from .timeutil import IST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worklog")

settings = get_settings()
scheduler = BackgroundScheduler(timezone=IST)


def _scheduled_sync() -> None:
    """Background job: pull worklogs from all enabled instances."""
    logger.info("Running scheduled sync...")
    db = SessionLocal()
    try:
        result = sync_all(db)
        logger.info("Scheduled sync complete: %s", result)
    except Exception:  # noqa: BLE001
        logger.exception("Scheduled sync failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Seed default daily hours if not present
    db = SessionLocal()
    try:
        ensure_default_config(db)
    finally:
        db.close()

    if settings.sync_interval_minutes > 0:
        scheduler.add_job(
            _scheduled_sync,
            "interval",
            minutes=settings.sync_interval_minutes,
            id="worklog_sync",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started (every %s min)", settings.sync_interval_minutes)
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}
