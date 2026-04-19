"""MVP orchestration API (Wave 2).

Exposes a minimal Wave 2 orchestrator endpoint to run a task through the
Oracle -> Metis -> Sisyphus stages.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend.orchestration.mvp_runner import run_mvp_for_task

router = APIRouter()


class MVPRunRequest(BaseModel):
    task: str
    history: list[dict[str, Any]] | None = None


@router.post("/run", response_model=list[dict[str, Any]])
async def run_mvp(request: MVPRunRequest) -> list[dict[str, Any]]:
    """Run a task through the Oracle -> Metis -> Sisyphus pipeline."""
    task = request.task
    history = request.history or []
    results: list[dict[str, Any]] = []
    async for part in run_mvp_for_task(task, history):
        results.append(part)
    return results
