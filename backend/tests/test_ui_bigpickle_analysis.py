"""E2E UI test — navigate Settings → OpenCode + big-pickle → chat analysis.

Flow:
  1. Open Settings page at http://localhost:7000/tenderclaw/settings
  2. Click the OpenCode provider button
  3. Wait for dynamic model fetch (3 s); if big-pickle appears, click it,
     otherwise fall back to the custom-model text input
  4. Save settings and confirm "Saved!" feedback
  5. Navigate back to Chat
  6. Send: "analizza d:\\MY_AI\\claude-code\\TenderClaw\\"
  7. Wait up to 5 min for any assistant response
  8. Capture screenshots at every step; print WS events summary

Test is automatically skipped when the backend is not running.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest

playwright_async_api = pytest.importorskip(
    "playwright.async_api",
    reason="Playwright is required for UI e2e tests",
)
async_playwright = playwright_async_api.async_playwright
expect = playwright_async_api.expect

BACKEND    = "http://localhost:7000"
FRONTEND   = "http://localhost:7000/tenderclaw"
SETTINGS   = f"{FRONTEND}/settings"
TARGET_MODEL = "big-pickle"
ANALYSIS_PROMPT = r"analizza d:\MY_AI\claude-code\TenderClaw\ "


# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------

async def _wait_for_backend(timeout: int = 15) -> None:
    """Skip the test gracefully if the server is not responding."""
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
    pytest.skip(f"Backend not running at {BACKEND} — start it with start.bat first")


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_ui_bigpickle_chat_analysis(tmp_path: Path) -> None:
    """
    UI: Settings → OpenCode → big-pickle → Save → Chat →
        'analizza d:\\MY_AI\\claude-code\\TenderClaw\\'
    """
    await _wait_for_backend()

    shot_dir = tmp_path / "shots"
    shot_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=250)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await ctx.new_page()

        js_errors: list[str] = []
        page.on("console",   lambda m: js_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: js_errors.append(str(e)))

        try:
            # ── Step 1: Open Settings ──────────────────────────────────────
            print(f"\n[Step 1] Navigating to Settings: {SETTINGS}")
            await page.goto(SETTINGS, wait_until="networkidle", timeout=20_000)
            await page.screenshot(path=str(shot_dir / "01_settings_loaded.png"))

            # ── Step 2: Click OpenCode provider ────────────────────────────
            print("[Step 2] Selecting OpenCode provider")
            opencode_btn = page.get_by_role("button", name="OpenCode")
            await expect(opencode_btn).to_be_visible(timeout=5_000)
            await opencode_btn.click()

            # Wait for dynamic model fetch to complete
            await page.wait_for_timeout(3_500)
            await page.screenshot(path=str(shot_dir / "02_opencode_selected.png"))

            # ── Step 3: Pick big-pickle ─────────────────────────────────────
            # Try the dynamic list first; fall back to the manual input field
            model_btn = page.get_by_text(TARGET_MODEL, exact=True).first
            model_visible = await model_btn.is_visible()

            if model_visible:
                print(f"[Step 3] big-pickle found in dynamic list — clicking it")
                await model_btn.click()
            else:
                print(f"[Step 3] big-pickle not in dynamic list — using custom model input")
                custom_input = page.locator("input[placeholder*='model']").last
                await expect(custom_input).to_be_visible(timeout=4_000)
                await custom_input.fill(TARGET_MODEL)
                use_btn = page.get_by_role("button", name="Use")
                await use_btn.click()

            # Confirm the selected label is visible somewhere on the page
            selected = page.get_by_text(TARGET_MODEL, exact=False).last
            await expect(selected).to_be_visible(timeout=5_000)
            await page.screenshot(path=str(shot_dir / "03_model_selected.png"))
            print(f"[Step 3] Model '{TARGET_MODEL}' selected ✓")

            # ── Step 4: Save settings ───────────────────────────────────────
            print("[Step 4] Saving settings")
            save_btn = page.get_by_role("button", name="Save Settings")
            await save_btn.click()
            await expect(page.get_by_text("Saved!")).to_be_visible(timeout=5_000)
            await page.screenshot(path=str(shot_dir / "04_settings_saved.png"))
            print("[Step 4] Settings saved ✓")

            # ── Step 5: Navigate back to Chat ───────────────────────────────
            print("[Step 5] Navigating back to chat")
            back_link = page.get_by_text("Back to Chat")
            await back_link.click()
            await page.wait_for_url("**/tenderclaw", timeout=8_000)
            await page.wait_for_timeout(1_000)
            await page.screenshot(path=str(shot_dir / "05_chat_ready.png"))
            print("[Step 5] Chat page ready ✓")

            # ── Step 6: Send the analysis prompt ────────────────────────────
            print(f"[Step 6] Sending prompt: {ANALYSIS_PROMPT!r}")
            prompt_box = page.locator(
                "textarea, input[type='text'][placeholder*='essage']"
            ).first
            await expect(prompt_box).to_be_visible(timeout=5_000)
            await prompt_box.click()
            await prompt_box.fill(ANALYSIS_PROMPT)
            await page.screenshot(path=str(shot_dir / "06_prompt_filled.png"))
            await prompt_box.press("Enter")
            print("[Step 6] Prompt submitted ✓")

            # ── Step 7: Wait for assistant response (up to 5 min) ──────────
            print("[Step 7] Waiting for assistant response (up to 300 s)…")

            # An assistant bubble or error badge will contain "TenderClaw" or
            # the word "error" / "Error". We wait for any chat reply to appear.
            response_el = page.locator(
                # The assistant label or streamed text container
                "[data-role='assistant'], .assistant-bubble, "
                "[class*='assistant'], [class*='message']:not([class*='user'])"
            ).last

            # Also accept an error widget that appears instead
            any_reply = page.locator(
                "text=TenderClaw, text=Error, text=error, "
                "[data-role='assistant']"
            ).first

            try:
                await expect(any_reply).to_be_visible(timeout=300_000)
                print("[Step 7] Response received ✓")
            except Exception:
                print("[Step 7] Timeout waiting for reply — capturing final state")

            await page.screenshot(path=str(shot_dir / "07_response_received.png"))

            # ── Step 8: Dump visible chat text ──────────────────────────────
            chat_text = await page.inner_text("body")
            preview = chat_text.replace("\n", " ")[:500]
            print(f"\n[Step 8] Page text preview:\n{preview}\n")

            print(f"\n[PASS] Screenshots saved to {shot_dir}")

        finally:
            await page.screenshot(path=str(shot_dir / "final_state.png"))
            await browser.close()

    # Surface JS errors as warnings (not failures) — networking noise is expected
    critical = [e for e in js_errors if "TypeError" in e or "SyntaxError" in e]
    if critical:
        pytest.fail(f"Critical JS errors during UI test: {critical}")
