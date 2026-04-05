"""MVP orchestration runner — Wave 2 orchestration pipeline.

This module exposes run_mvp_for_task() which drives a task through the
Oracle -> Metis -> Sisyphus stages using the MVP pipeline.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Dict

from backend.orchestration.mvp_pipeline import run_mvp_pipeline


async def run_mvp_for_task(
    task: str,
    history: list[Dict[str, object]] | None = None,
) -> AsyncIterator[Dict[str, object]]:
    """Yield MVP pipeline steps for a given task."""
    async for part in run_mvp_pipeline(task, history or []):
        yield part
