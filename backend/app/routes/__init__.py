"""API router assembly."""
from fastapi import APIRouter

from . import calendar, config, instances, sync, users

api_router = APIRouter()
api_router.include_router(instances.router, prefix="/instances", tags=["instances"])
api_router.include_router(users.router, prefix="/instances/{instance_id}/users", tags=["users"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
