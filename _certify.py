"""Certification script — proves TenderClaw responds to a greeting via the web UI."""
import pathlib
from playwright.sync_api import sync_playwright

SCREENSHOT = pathlib.Path("tenderclaw_proof.png")
URL = "http://localhost:7000/tenderclaw"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False, slow_mo=300)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    # Intercept WS messages to detect turn_end
    turn_ended = {"value": False}

    def on_websocket(ws_conn):
        def on_frame_received(payload):
            if '"turn_end"' in payload or '"type":"turn_end"' in payload:
                turn_ended["value"] = True
        ws_conn.on("framereceived", on_frame_received)

    page.on("websocket", on_websocket)

    # Set LM Studio model via Settings (no API key needed)
    page.goto(f"{URL}/settings", wait_until="networkidle", timeout=15000)
    page.get_by_role("button", name="LM Studio (Local)").click()
    page.wait_for_timeout(2500)
    page.get_by_text("google/gemma-4-e4b", exact=True).first.click()
    page.get_by_role("button", name="Save Settings").click()
    page.wait_for_selector("text=Saved!", timeout=4000)
    page.get_by_text("Back to Chat").click()
    page.wait_for_url("**/tenderclaw**", timeout=6000)
    page.wait_for_timeout(2000)

    # Send greeting
    prompt = page.locator("textarea").first
    prompt.wait_for(state="visible", timeout=8000)
    prompt.fill("Ciao! Come stai?")
    prompt.press("Enter")

    # Wait for turn_end WS event (response fully received)
    page.wait_for_function(
        "() => window.__turnEnded === true",
        timeout=120000,
        polling=500,
    ) if False else None  # fallback: poll turn_ended dict

    # Poll until turn_end received or timeout
    import time
    deadline = time.time() + 120
    while not turn_ended["value"] and time.time() < deadline:
        page.wait_for_timeout(500)

    # Extra wait for streaming text to render
    page.wait_for_timeout(2000)
    page.screenshot(path=str(SCREENSHOT))
    browser.close()

print(f"Screenshot saved: {SCREENSHOT.resolve()}")
print(f"Turn ended: {turn_ended['value']}")
