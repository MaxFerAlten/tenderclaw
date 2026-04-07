"""E2E test — verify LM Studio model selection and call via TenderClaw.

Tests:
1. Backend diagnostics: LM Studio reachable, google/gemma-4-e4b listed
2. Backend WS: create session with google/gemma-4-e4b, send message, get response
3. UI (Playwright): select LM Studio in Settings, pick model, save, send message

All three tests are automatically skipped when the required services are not
running, so they never produce a FAIL in a bare development checkout.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest
import websockets
from playwright.async_api import async_playwright, expect

BACKEND = "http://localhost:7000"
WS_BACKEND = "ws://localhost:7000"
FRONTEND = "http://localhost:5173/tenderclaw"
TARGET_MODEL = "google/gemma-4-e4b"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _check_reachable(url: str, timeout: int = 3) -> bool:
    """Return True if the URL responds with any HTTP status within timeout."""
    try:
        async with httpx.AsyncClient() as client:
            await client.get(url, timeout=timeout)
        return True
    except Exception:
        return False


async def _wait_for_backend(timeout: int = 10) -> None:
    """Wait up to *timeout* seconds for the backend health endpoint.

    Raises pytest.skip (not RuntimeError) so the test is marked SKIPPED
    rather than FAILED when the backend is not running.
    """
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
    pytest.skip(f"Backend not running at {BACKEND} — start with `tenderclaw` to run e2e tests")


async def _require_frontend() -> None:
    """Skip the test if the Vite dev server (or built frontend) is not reachable."""
    reachable = await _check_reachable(FRONTEND, timeout=3)
    if not reachable:
        pytest.skip(
            f"Frontend not running at {FRONTEND} — "
            "start with `npm run dev` (or serve the dist build) to run UI e2e tests"
        )


async def _require_lmstudio() -> None:
    """Skip the test if LM Studio is not reachable or the target model is not loaded."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BACKEND}/api/diagnostics/lmstudio", timeout=5)
        if r.status_code != 200:
            pytest.skip("LM Studio diagnostics endpoint not available")
        data = r.json()
        if data.get("status") != "ok":
            pytest.skip(f"LM Studio not reachable: {data}")
        if TARGET_MODEL not in str(data.get("models", "")):
            pytest.skip(
                f"LM Studio is up but {TARGET_MODEL!r} is not loaded — "
                f"loaded models: {data.get('models', '')}"
            )
    except Exception as exc:
        pytest.skip(f"LM Studio check failed: {exc}")


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
async def test_lmstudio_diagnostics() -> None:
    """LM Studio is reachable and google/gemma-4-e4b is loaded."""
    await _wait_for_backend()
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BACKEND}/api/diagnostics/lmstudio", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok", f"LM Studio not reachable: {data}"
    models_str = data.get("models", "")
    assert TARGET_MODEL in models_str, (
        f"{TARGET_MODEL} not found in LM Studio. Loaded: {models_str}"
    )
    print(f"\n[diagnostics] OK — models: {models_str}")


# ---------------------------------------------------------------------------
# Test 2 — WebSocket round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_lmstudio_ws_roundtrip() -> None:
    """Create session with google/gemma-4-e4b, send message via WS, get non-empty response."""
    await _wait_for_backend()
    await _require_lmstudio()
    session_id = await _create_session(TARGET_MODEL)

    collected_text: list[str] = []
    error_event: dict | None = None

    async with websockets.connect(
        f"{WS_BACKEND}/api/ws/{session_id}",
        open_timeout=5,
    ) as ws:
        # Confirm model via session_config
        await ws.send(json.dumps({
            "type": "session_config",
            "model": TARGET_MODEL,
        }))

        # Send user message
        await ws.send(json.dumps({
            "type": "user_message",
            "content": "Reply with exactly the word: LMSTUDIO_OK",
        }))

        # Collect events until turn_end or error (max 60s)
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
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
    assert len(response) > 0, "Empty response from LM Studio via WebSocket"
    print(f"\n[ws_roundtrip] Response ({len(response)} chars): {response[:200]}")


# ---------------------------------------------------------------------------
# Test 3 — Playwright UI
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_settings_ui_lmstudio(tmp_path: Path) -> None:
    """UI: select LM Studio, load models dynamically, pick google/gemma-4-e4b, save, chat."""
    await _wait_for_backend()
    await _require_lmstudio()
    await _require_frontend()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=250)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        js_errors: list[str] = []
        page.on("console", lambda m: js_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: js_errors.append(str(e)))

        try:
            # --- Settings page ---
            await page.goto(f"{FRONTEND}/settings", wait_until="networkidle", timeout=15_000)

            # Select LM Studio provider
            await page.get_by_role("button", name="LM Studio (Local)").click()

            # Wait for dynamic model fetch (fetchLmstudioModels fires on click)
            await page.wait_for_timeout(2_500)

            # google/gemma-4-e4b should appear
            model_btn = page.get_by_text(TARGET_MODEL, exact=True).first
            await expect(model_btn).to_be_visible(timeout=6_000)
            await model_btn.click()

            # Confirm selected label
            selected = page.get_by_text(TARGET_MODEL, exact=False).last
            await expect(selected).to_be_visible()

            # Save
            await page.get_by_role("button", name="Save Settings").click()
            await expect(page.get_by_text("Saved!")).to_be_visible(timeout=4_000)

            # Screenshot: settings saved
            await page.screenshot(path=str(tmp_path / "01_settings_saved.png"))

            # Back to chat
            await page.get_by_text("Back to Chat").click()
            await page.wait_for_url("**/tenderclaw**", timeout=6_000)

            # Send a message
            prompt = page.locator("textarea, input[placeholder*='essage']").first
            await expect(prompt).to_be_visible(timeout=5_000)
            await prompt.fill("Say exactly: GEMMA_UI_OK")
            await prompt.press("Enter")

            # Wait for assistant response — streaming text appears first, then settles into a bubble
            # StreamingText or the assistant bubble (bg-zinc-900 + "TenderClaw" label)
            response_el = page.locator("text=TenderClaw").last
            await expect(response_el).to_be_visible(timeout=45_000)

            # Screenshot: response received
            await page.screenshot(path=str(tmp_path / "02_response_received.png"))
            print(f"\n[ui] Screenshots saved to {tmp_path}")

        finally:
            await page.screenshot(path=str(tmp_path / "final_state.png"))
            await browser.close()

    critical_errors = [e for e in js_errors if "TypeError" in e or "SyntaxError" in e]
    assert not critical_errors, f"JS errors during UI test: {critical_errors}"
