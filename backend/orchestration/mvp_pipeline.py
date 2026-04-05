"""Minimal MVP orchestration pipeline (Wave 2).

This module provides a tiny, dependency-free orchestration path that simulates
the Oracle -> Metis -> Sisyphus stages by yielding small progress blocks.
It is intended as a scaffold for real integration with the existing agent
framework.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Dict


async def run_mvp_pipeline(
    task: str,
    messages: list[Dict[str, object]] | None = None,
) -> AsyncIterator[Dict[str, object]]:
    """Run a task through Oracle -> Metis -> Sisyphus stages."""
    # Stage 1: Oracle (research/planning)
    yield {"stage": "oracle", "status": "start", "task": task}
    await asyncio.sleep(0.01)
    yield {
        "stage": "oracle",
        "status": "done",
        "plan": f"Oracle plan for: {task}",
    }

    # Stage 2: Metis (detailed planning)
    yield {"stage": "metis", "status": "start", "task": task}
    await asyncio.sleep(0.01)
    yield {
        "stage": "metis",
        "status": "done",
        "plan": f"Metis implementation plan for: {task}",
    }

    # Stage 3: Sisyphus (execution)
    yield {"stage": "sisyphus", "status": "start", "task": task}
    await asyncio.sleep(0.01)
    yield {
        "stage": "sisyphus",
        "status": "done",
        "execution": f"Executed plan for: {task}",
    }
