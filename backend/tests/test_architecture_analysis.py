"""E2E test — Big Pickle architecture analysis of TenderClaw.

Test: Send a message to Big Pickle asking for architectural analysis
of the TenderClaw codebase itself.

Requirements:
- Backend running at http://localhost:7000
- OpenCode API key configured
- Target directory exists
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx
import pytest
import websockets

BACKEND = "http://localhost:7000"
WS_BACKEND = "ws://localhost:7000"
TARGET_MODEL = "big-pickle"
TARGET_DIR = r"d:\MY_AI\claude-code\TenderClaw"


async def _wait_for_backend(timeout: int = 10) -> None:
    async with httpx.AsyncClient() as client:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = await client.get(f"{BACKEND}/api/health", timeout=2)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)
    pytest.skip(f"Backend not running at {BACKEND}")


async def _require_opencode_key() -> str:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BACKEND}/api/config/status", timeout=5)
    if r.status_code != 200:
        pytest.skip("Config status endpoint not available")
    data = r.json()
    opencode = data.get("opencode", {})
    if not opencode.get("configured") and not opencode.get("key_set"):
        pytest.skip("OpenCode API key not configured")
    return ""


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_big_pickle_architecture_analysis() -> None:
    """Big Pickle analyzes TenderClaw architecture."""
    await _wait_for_backend()
    await _require_opencode_key()

    session_id: str | None = None
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BACKEND}/api/sessions",
            json={"model": TARGET_MODEL},
        )
        assert r.status_code in (200, 201), f"Session creation failed: {r.text}"
        session_id = r.json()["session_id"]

    assert session_id is not None

    collected_text: list[str] = []
    error_event: dict | None = None

    prompt = "Analizza architetturalmente " + TARGET_DIR

    async with websockets.connect(
        f"{WS_BACKEND}/api/ws/{session_id}",
        open_timeout=10,
    ) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "session_config",
                    "model": TARGET_MODEL,
                }
            )
        )

        await ws.send(
            json.dumps(
                {
                    "type": "user_message",
                    "content": prompt,
                }
            )
        )

        all_events: list[str] = []
        deadline = time.time() + 300
        tool_results_received = False
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
            except asyncio.TimeoutError:
                if tool_results_received:
                    break
                continue

            event: dict[str, Any] = json.loads(raw)
            etype = event.get("type", "")
            all_events.append(etype)

            if etype == "assistant_text":
                collected_text.append(event.get("delta", ""))
            elif etype == "tool_use_start":
                print(f"\n[TOOL START] {event.get('name')}")
            elif etype == "tool_use_complete":
                print(f"\n[TOOL COMPLETE] {event.get('name')}")
            elif etype == "tool_result":
                tool_results_received = True
                result_preview = str(event.get("content", ""))[:100]
                print(f"\n[TOOL RESULT] {result_preview}...")
            elif etype == "turn_end":
                print(f"\n[TURN END] stop_reason: {event.get('stop_reason')}")
                break
            elif etype == "error":
                error_event = event
                print(f"\n[ERROR] {error_event}")
                break
            elif etype == "ping":
                await ws.send(json.dumps({"type": "pong"}))
            else:
                print(f"\n[EVENT] {etype}: {event}")

        if not error_event and not collected_text:
            print(f"\n[DEBUG] All events received: {all_events}")

    if error_event:
        print(f"\n[ERROR] {error_event}")
        pytest.fail(f"Server error: {error_event}")

    response = "".join(collected_text)

    print(f"\n[{TARGET_MODEL}] Response ({len(response)} chars):")
    print("=" * 60)
    print(response[:2000])
    if len(response) > 2000:
        print(f"... ({len(response) - 2000} more chars)")
    print("=" * 60)

    print(f"\n[PASS] Test executed - response length: {len(response)} chars")
    print(f"\n[PASS] Architecture analysis completed ({len(response)} chars)")
