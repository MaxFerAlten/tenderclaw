"""E2E test — verify OpenCode model selection and call via TenderClaw.

Tests:
1. Backend diagnostics: OpenCode key configured, big-pickle listed in available models
2. Backend WS: create session with big-pickle, send message, get response
3. UI (Playwright): select OpenCode in Settings, pick big-pickle, save, send message, get response

All tests are automatically skipped when the required services are not running
or the OpenCode API key is not configured.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest
import websockets

playwright_async_api = pytest.importorskip(
    "playwright.async_api",
    reason="Playwright is required for UI e2e tests",
)
async_playwright = playwright_async_api.async_playwright
expect = playwright_async_api.expect

BACKEND = "http://localhost:7000"
WS_BACKEND = "ws://localhost:7000"
FRONTEND = "http://localhost:7000/tenderclaw"
TARGET_MODEL = "big-pickle"
OPENCODE_API_KEY_ENV = "OPENCODE_API_KEY"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Return the OpenCode API key or skip the test."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BACKEND}/api/config/status", timeout=5)
    if r.status_code != 200:
        pytest.skip("Config status endpoint not available")
    data = r.json()
    opencode = data.get("opencode", {})
    if not opencode.get("configured") and not opencode.get("key_set"):
        pytest.skip("OpenCode API key not configured — add it in Settings first")
    return ""


async def _require_big_pickle_available() -> None:
    """Skip if big-pickle is not in the OpenCode models list."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BACKEND}/api/diagnostics/opencode/models", timeout=10)
    if r.status_code != 200:
        pytest.skip("OpenCode diagnostics endpoint not available")
    models: list[str] = r.json()
    if not models:
        pytest.skip("OpenCode returned empty model list — check API key validity")
    if TARGET_MODEL not in models:
        pytest.skip(
            f"{TARGET_MODEL!r} not in OpenCode model list. Available: {models[:10]}"
        )


async def _create_session(model: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BACKEND}/api/sessions", json={"model": model})
        assert r.status_code in (200, 201), f"Session creation failed: {r.text}"
        return r.json()["session_id"]


# ---------------------------------------------------------------------------
# Test 1 — diagnostics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_opencode_diagnostics() -> None:
    """OpenCode key is configured and big-pickle is in the available models."""
    await _wait_for_backend()
    await _require_opencode_key()

    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BACKEND}/api/diagnostics/opencode/models", timeout=10)

    assert r.status_code == 200, f"Diagnostics endpoint failed: {r.text}"
    models: list[str] = r.json()
    assert len(models) > 0, "OpenCode returned empty model list"
    assert TARGET_MODEL in models, (
        f"{TARGET_MODEL!r} not found. Available models: {models}"
    )
    print(f"\n[diagnostics] OK — {len(models)} models, big-pickle present")


# ---------------------------------------------------------------------------
# Test 2 — WebSocket round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_opencode_ws_roundtrip() -> None:
    """Create session with big-pickle, send message via WS, get non-empty response."""
    await _wait_for_backend()
    await _require_opencode_key()
    await _require_big_pickle_available()

    session_id = await _create_session(TARGET_MODEL)
    collected_text: list[str] = []
    error_event: dict | None = None

    async with websockets.connect(
        f"{WS_BACKEND}/api/ws/{session_id}",
        open_timeout=5,
    ) as ws:
        await ws.send(json.dumps({
            "type": "session_config",
            "model": TARGET_MODEL,
        }))

        await ws.send(json.dumps({
            "type": "user_message",
            "content": "Reply with exactly the word: OPENCODE_OK",
        }))

        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
            except asyncio.TimeoutError:
                continue
            event = json.loads(raw)
            etype = event.get("type", "")

            if etype == "assistant_text":
                collected_text.append(event.get("delta", ""))
            elif etype == "turn_end":
                break
            elif etype == "error":
                error_event = event
                break

    assert error_event is None, f"Server returned error: {error_event}"
    response = "".join(collected_text)
    assert len(response) > 0, "Empty response from OpenCode via WebSocket"
    print(f"\n[ws_roundtrip] Response ({len(response)} chars): {response[:200]}")


# ---------------------------------------------------------------------------
# Test 3 — Playwright UI
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_settings_ui_opencode(tmp_path: Path) -> None:
    """UI: select OpenCode, load models, pick big-pickle, save, chat, get response."""
    await _wait_for_backend()
    await _require_opencode_key()
    await _require_big_pickle_available()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=300)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        js_errors: list[str] = []
        page.on("console", lambda m: js_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: js_errors.append(str(e)))

        try:
            # --- Settings page ---
            await page.goto(f"{FRONTEND}/settings", wait_until="networkidle", timeout=15_000)
            await page.screenshot(path=str(tmp_path / "00_settings_loaded.png"))

            # Select OpenCode provider
            await page.get_by_role("button", name="OpenCode").click()

            # Wait for dynamic model fetch
            await page.wait_for_timeout(3_000)
            await page.screenshot(path=str(tmp_path / "01_opencode_selected.png"))

            # big-pickle should appear in the model list
            model_btn = page.get_by_text(TARGET_MODEL, exact=True).first
            await expect(model_btn).to_be_visible(timeout=8_000)
            await model_btn.click()

            # Confirm selected label shows big-pickle
            selected_label = page.get_by_text(TARGET_MODEL, exact=False).last
            await expect(selected_label).to_be_visible()

            # Save settings
            await page.get_by_role("button", name="Save Settings").click()
            await expect(page.get_by_text("Saved!")).to_be_visible(timeout=4_000)
            await page.screenshot(path=str(tmp_path / "02_settings_saved.png"))

            # Back to chat
            await page.get_by_text("Back to Chat").click()
            await page.wait_for_url("**/tenderclaw**", timeout=6_000)

            # Send a message
            prompt = page.locator("textarea, input[placeholder*='essage']").first
            await expect(prompt).to_be_visible(timeout=5_000)
            await prompt.fill("Say exactly: BIGPICKLE_UI_OK")
            await prompt.press("Enter")

            # Wait for assistant response bubble
            response_el = page.locator("text=TenderClaw").last
            await expect(response_el).to_be_visible(timeout=90_000)
            await page.screenshot(path=str(tmp_path / "03_response_received.png"))

            print(f"\n[ui] Screenshots saved to {tmp_path}")

        finally:
            await page.screenshot(path=str(tmp_path / "final_state.png"))
            await browser.close()

    critical_errors = [e for e in js_errors if "TypeError" in e or "SyntaxError" in e]
    assert not critical_errors, f"JS errors during UI test: {critical_errors}"
