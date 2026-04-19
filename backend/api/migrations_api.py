"""API endpoints for migrations."""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.migrations.runner import get_migration_status, run_all_pending

router = APIRouter(prefix="/migrations", tags=["migrations"])


class MigrationStatus(BaseModel):
    total: int
    applied: int
    pending: int
    migrations: list[dict]


@router.get("/status")
async def get_status() -> MigrationStatus:
    """Get migration status."""
    status = get_migration_status()
    return MigrationStatus(**status)


@router.post("/run")
async def run_migrations():
    """Run pending migrations."""
    run_ids = run_all_pending()
    return {"applied": run_ids}
