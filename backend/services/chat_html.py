"""Static HTML entrypoints for persisted chat conversations."""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path
from typing import Any

from backend.services.chat_viewer_assets import VIEWER_CSS, VIEWER_JS
from backend.services.workspace import CONVERSATION_FILE_NAME, ensure_workspace_dirs, get_session_dir, iter_conversation_paths

logger = logging.getLogger("tenderclaw.services.chat_html")

SESSION_HTML_FILE_NAME = CHAT_INDEX_FILE_NAME = "index.html"
SESSIONS_JSON_FILE_NAME = "sessions.json"
VIEWER_CSS_FILE_NAME = "viewer.css"
VIEWER_JS_FILE_NAME = "viewer.js"


def refresh_chat_entrypoints(session_id: str | None = None) -> None:
    if session_id:
        write_session_html(session_id)
    else:
        for conv_path in iter_conversation_paths(include_legacy=False):
            if conv_path.name != CONVERSATION_FILE_NAME:
                continue
            try:
                data = json.loads(conv_path.read_text(encoding="utf-8"))
                write_session_html(str(data.get("session_id") or conv_path.parent.name))
            except Exception as exc:
                logger.warning("Failed to refresh chat HTML for %s: %s", conv_path, exc)
    write_chat_index()


def write_session_html(session_id: str) -> Path:
    session_dir = get_session_dir(session_id, create=True)
    _write_viewer_assets(session_dir.parent)
    html_path = session_dir / SESSION_HTML_FILE_NAME
    html_path.write_text(_session_html(session_id), encoding="utf-8")
    return html_path


def write_chat_index() -> Path:
    chat_dir = ensure_workspace_dirs()
    _write_viewer_assets(chat_dir)
    sessions = _load_sessions(chat_dir)
    (chat_dir / SESSIONS_JSON_FILE_NAME).write_text(
        json.dumps({"sessions": sessions}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    html_path = chat_dir / CHAT_INDEX_FILE_NAME
    html_path.write_text(_chat_index_html(sessions), encoding="utf-8")
    return html_path


def _load_sessions(chat_dir: Path) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for conv_path in iter_conversation_paths(include_legacy=False):
        if conv_path.name != CONVERSATION_FILE_NAME:
            continue
        try:
            session_dir = conv_path.parent
            relative_html = session_dir.relative_to(chat_dir) / SESSION_HTML_FILE_NAME
            data = json.loads(conv_path.read_text(encoding="utf-8"))
            messages = data.get("messages", [])
            sessions.append({
                "session_id": data.get("session_id") or session_dir.name,
                "title": data.get("title") or _extract_title(messages),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", data.get("created_at", "")),
                "message_count": len(messages) if isinstance(messages, list) else 0,
                "model": data.get("model", ""),
                "total_cost_usd": data.get("total_cost_usd", 0.0),
                "href": relative_html.as_posix(),
            })
        except Exception as exc:
            logger.warning("Failed to index chat HTML entry for %s: %s", conv_path, exc)
    sessions.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
    return sessions


def _extract_title(messages: Any) -> str:
    if not isinstance(messages, list):
        return "Untitled Session"
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str) and content.strip():
            return _trim(content.strip(), 80)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = str(block.get("text", "")).strip()
                    if text:
                        return _trim(text, 80)
    return "Untitled Session"


def _trim(value: str, length: int) -> str:
    return value[:length] + ("..." if len(value) > length else "")


def _write_viewer_assets(chat_dir: Path) -> None:
    _write_if_changed(chat_dir / VIEWER_CSS_FILE_NAME, VIEWER_CSS.strip() + "\n")
    _write_if_changed(chat_dir / VIEWER_JS_FILE_NAME, VIEWER_JS.strip() + "\n")


def _write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def _session_html(session_id: str) -> str:
    escaped_session = html.escape(session_id, quote=True)
    template = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TenderClaw Session __SESSION__</title>
  <link rel="stylesheet" href="../viewer.css">
</head>
<body class="shell">
  <header class="topbar">
    <div class="topbar-inner">
      <div>
        <a class="crumb" href="../index.html">TenderClaw chats</a>
        <h1 id="title">Session __SESSION__</h1>
        <div id="meta" class="meta"></div>
      </div>
      <div class="actions">
        <a class="button" href="conversation.json">JSON</a>
        <button id="reload" class="button" type="button">Refresh</button>
      </div>
    </div>
  </header>
  <main id="messages" class="messages"></main>
  <script src="../viewer.js"></script>
  <script>
    TenderClawChatViewer.bootSession({ jsonUrl: "conversation.json" });
  </script>
</body>
</html>
"""
    return template.replace("__SESSION__", escaped_session)


def _chat_index_html(sessions: list[dict[str, Any]]) -> str:
    return """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TenderClaw Chats</title>
  <link rel="stylesheet" href="viewer.css">
</head>
<body class="shell">
  <main class="index-main">
    <h1>TenderClaw Chats</h1>
    <div class="meta"><span class="pill">Generated from sessions.json</span></div>
    <input id="search" class="search" type="search" placeholder="Search sessions">
    <section id="sessions"></section>
  </main>
  <script src="viewer.js"></script>
  <script>
    TenderClawChatViewer.bootIndex({ jsonUrl: "sessions.json" });
  </script>
</body>
</html>
"""
