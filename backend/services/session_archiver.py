"""Session Archiver — persist complete session data (conversation + files) to workspace.

Structure:
    ~/workspace_tenderclaw/chat/{session_id}/
        conversation.json   ← full serialized session with messages
        image/file uploads   ← saved next to the conversation JSON
        metadata.json       ← lightweight session info for quick listing
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from backend.services.chat_html import refresh_chat_entrypoints
from backend.services.workspace import (
    CONVERSATION_FILE_NAME,
    LEGACY_WORKSPACE_DIR,
    delete_session_artifacts,
    ensure_workspace_dirs,
    find_conversation_path,
    get_conversation_path,
    get_metadata_path,
    get_session_dir,
    iter_conversation_paths,
    sanitize_session_id,
)

logger = logging.getLogger("tenderclaw.services.archiver")


def _ensure_workspace() -> None:
    ensure_workspace_dirs()


def archive_session(session_id: str, session_data: dict[str, Any]) -> str | None:
    """Archive a complete session to workspace.

    Args:
        session_id: The session identifier (e.g. "tc_526003bcdd22").
        session_data: Full serialized session data including messages.

    Returns:
        Path to the archived conversation.json, or None on failure.
    """
    try:
        _ensure_workspace()

        # Create session directory
        get_session_dir(session_id, create=True)

        # Save conversation JSON
        conv_path = get_conversation_path(session_id, create_parent=True)
        existing: dict[str, Any] = {}
        if conv_path.exists():
            try:
                with open(conv_path, encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception as exc:
                logger.warning("Failed to merge existing archive for %s: %s", session_id, exc)

        payload = {**existing, **session_data, "updated_at": datetime.now(UTC).isoformat()}
        with open(conv_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("Archived conversation for %s → %s (%d messages)",
                     session_id, conv_path, len(payload.get("messages", [])))

        # Save metadata for quick listing
        meta = {
            "session_id": session_id,
            "title": _extract_title(payload),
            "created_at": payload.get("created_at", ""),
            "updated_at": payload.get("updated_at", ""),
            "model": payload.get("model", ""),
            "message_count": len(payload.get("messages", [])),
            "total_cost_usd": payload.get("total_cost_usd", 0.0),
            "status": payload.get("status", ""),
        }
        meta_path = get_metadata_path(session_id, create_parent=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        refresh_chat_entrypoints(session_id)

        return str(conv_path)
    except Exception as exc:
        logger.error("Failed to archive session %s: %s", session_id, exc)
        return None


def _extract_title(session_data: dict[str, Any]) -> str:
    """Extract a title from the first user message."""
    messages = session_data.get("messages", [])
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content[:80] + ("..." if len(content) > 80 else "")
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text", "")[:80]
                        return text + ("..." if len(text) == 80 else "")
    return "Untitled Session"


def list_archived_sessions() -> list[dict]:
    """List all archived sessions with metadata."""
    _ensure_workspace()
    results = []
    seen_session_ids: set[str] = set()

    for conv_path in iter_conversation_paths():
        meta_path = conv_path.parent / "metadata.json"
        session_id = conv_path.parent.name if conv_path.name == CONVERSATION_FILE_NAME else conv_path.stem
        if meta_path.exists():
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                sid = meta.get("session_id") or session_id
                if sid in seen_session_ids:
                    continue
                seen_session_ids.add(sid)
                results.append(meta)
            except Exception as exc:
                logger.warning("Failed to read metadata for %s: %s", session_id, exc)
        else:
            try:
                with open(conv_path, encoding="utf-8") as f:
                    data = json.load(f)
                sid = data.get("session_id") or session_id
                if sid in seen_session_ids:
                    continue
                seen_session_ids.add(sid)
                results.append({
                    "session_id": sid,
                    "title": _extract_title(data),
                    "created_at": data.get("created_at", ""),
                    "message_count": len(data.get("messages", [])),
                    "model": data.get("model", ""),
                    "total_cost_usd": data.get("total_cost_usd", 0.0),
                })
            except Exception as exc:
                logger.warning("Failed to read conversation for %s: %s", session_id, exc)

    results.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return results


def get_archived_session(session_id: str) -> dict[str, Any] | None:
    """Get a single archived session."""
    conv_path = find_conversation_path(session_id)
    if not conv_path:
        return None

    try:
        with open(conv_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to read archived session %s: %s", session_id, exc)
        return None


def delete_archived_session(session_id: str) -> bool:
    """Delete an archived session and all its files."""
    if not find_conversation_path(session_id):
        return False

    try:
        delete_session_artifacts(session_id)
        refresh_chat_entrypoints()
        logger.info("Deleted archived session %s", session_id)
        return True
    except Exception as exc:
        logger.error("Failed to delete archived session %s: %s", session_id, exc)
        return False


def get_session_images(session_id: str) -> list[dict]:
    """List images for an archived session."""
    safe_id = sanitize_session_id(session_id)
    dirs = [
        get_session_dir(session_id),
        LEGACY_WORKSPACE_DIR / safe_id,
        LEGACY_WORKSPACE_DIR / safe_id / "images",
    ]

    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tiff"}
    results = []
    seen_paths: set[str] = set()
    for img_dir in dirs:
        if not img_dir.exists():
            continue
        for f in sorted(img_dir.iterdir()):
            if not f.is_file() or f.suffix.lower() not in image_extensions:
                continue
            resolved = str(f.resolve())
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            results.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
            })
    return results
