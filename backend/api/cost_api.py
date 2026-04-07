"""API endpoints for cost tracking."""

from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.cost_tracker import CostTracker
from backend.api.sessions import get_current_session_id

router = APIRouter(prefix="/costs", tags=["costs"])


class CostSummary(BaseModel):
    session_id: str
    total_cost_usd: float
    total_api_duration_ms: float
    total_input_tokens: int
    total_output_tokens: int
    model_usage: dict[str, dict]


@router.get("/current", response_model=CostSummary)
async def get_current_session_cost() -> CostSummary:
    """Get cost for current session."""
    session_id = get_current_session_id()
    if not session_id:
        return CostSummary(
            session_id="",
            total_cost_usd=0.0,
            total_api_duration_ms=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            model_usage={},
        )
    data = CostTracker.get_session_cost(session_id)
    return CostSummary(**data)


@router.get("/session/{session_id}", response_model=CostSummary)
async def get_session_cost(session_id: str) -> CostSummary:
    """Get cost for specific session."""
    data = CostTracker.get_session_cost(session_id)
    return CostSummary(**data)


@router.get("/history", response_model=list[CostSummary])
async def get_cost_history() -> list[CostSummary]:
    """Get cost history for all sessions."""
    costs = CostTracker.get_all_costs()
    return [CostSummary(**c) for c in costs]
