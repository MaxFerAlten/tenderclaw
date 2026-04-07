"""Remote bridge API endpoints."""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Any
import json

router = APIRouter(tags=["bridge"])


class BridgeConnectRequest(BaseModel):
    client_id: str


class BridgeConnectResponse(BaseModel):
    session_id: str
    token: str
    expires_in: int


class BridgeStatusResponse(BaseModel):
    active: bool
    session_count: int
    max_sessions: int


@router.post("/connect", response_model=BridgeConnectResponse)
async def connect(request: BridgeConnectRequest) -> BridgeConnectResponse:
    """Connect to the remote bridge and get a session token."""
    from backend.bridge.remote_bridge import remote_bridge

    session_id, token = await remote_bridge.connect(request.client_id)
    expires_in = remote_bridge.config.jwt_expiry_hours * 3600
    return BridgeConnectResponse(
        session_id=session_id,
        token=token,
        expires_in=expires_in,
    )


@router.get("/status", response_model=BridgeStatusResponse)
async def status() -> BridgeStatusResponse:
    """Get bridge status."""
    from backend.bridge.remote_bridge import remote_bridge

    return BridgeStatusResponse(
        active=remote_bridge._active,
        session_count=len(remote_bridge.sessions),
        max_sessions=remote_bridge.config.max_sessions,
    )


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    """List all active remote sessions."""
    from backend.bridge.remote_bridge import remote_bridge

    sessions = remote_bridge.list_sessions()
    return [
        {
            "id": s.id,
            "client_id": s.client_id,
            "state": s.state.value,
            "created_at": s.created_at.isoformat(),
            "last_activity": s.last_activity.isoformat(),
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def disconnect_session(session_id: str) -> dict[str, str]:
    """Force disconnect a session."""
    from backend.bridge.remote_bridge import remote_bridge

    if remote_bridge.disconnect(session_id):
        return {"status": "disconnected"}
    raise HTTPException(status_code=404, detail="Session not found")


@router.websocket("/ws/{session_id}")
async def bridge_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for remote bridge communication."""
    from backend.bridge.remote_bridge import remote_bridge

    await websocket.accept()

    try:
        data = await websocket.receive_text()
        auth_data = json.loads(data)
        token = auth_data.get("token")

        if not token or not await remote_bridge.authenticate(session_id, token):
            await websocket.send_json({"error": "Authentication failed"})
            await websocket.close()
            return

        await websocket.send_json({"status": "authenticated"})

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            response = {"type": "pong", "original": message}
            await websocket.send_json(response)

    except WebSocketDisconnect:
        remote_bridge.disconnect(session_id)
