"""TenderClaw workspace paths.

Chat conversations and their attachments live under:
    ~/workspace_tenderclaw/chat/{session_id}/
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterable
from pathlib import Path

WORKSPACE_DIR_NAME = "workspace_tenderclaw"
CHAT_DIR_NAME = "chat"
CONVERSATION_FILE_NAME = "conversation.json"
METADATA_FILE_NAME = "metadata.json"

LEGACY_STATE_DIR = Path(".tenderclaw") / "state"
LEGACY_WORKSPACE_DIR = Path.home() / "workspace_tendermachine"

_SAFE_SESSION_ID = re.compile(r"[^A-Za-z0-9_.-]")


def get_default_workspace_dir() -> Path:
    """Return the default workspace in the user's home directory."""
    return Path.home() / WORKSPACE_DIR_NAME


def get_default_chat_dir() -> Path:
    """Return the default chat storage directory."""
    return get_default_workspace_dir() / CHAT_DIR_NAME


def get_chat_dir() -> Path:
    """Return the active chat storage directory.

    A configured ``chat_storage_path`` is treated as the chat root itself.
    When unset, TenderClaw uses ``~/workspace_tenderclaw/chat``.
    """
    try:
        from backend.api.config import _global_config

        custom = str(_global_config.get("chat_storage_path") or "").strip()
    except Exception:
        custom = ""

    if custom:
        return Path(custom).expanduser()
    return get_default_chat_dir()


def ensure_workspace_dirs() -> Path:
    """Create the home workspace and active chat directory."""
    get_default_workspace_dir().mkdir(parents=True, exist_ok=True)
    chat_dir = get_chat_dir()
    chat_dir.mkdir(parents=True, exist_ok=True)
    return chat_dir


def sanitize_session_id(session_id: str) -> str:
    """Return a filesystem-safe session directory name."""
    safe = _SAFE_SESSION_ID.sub("_", session_id.strip())
    return safe or "unknown_session"


def get_session_dir(session_id: str, *, create: bool = False) -> Path:
    """Return the per-session chat artifact directory."""
    chat_dir = ensure_workspace_dirs() if create else get_chat_dir()
    session_dir = chat_dir / sanitize_session_id(session_id)
    if create:
        session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_conversation_path(session_id: str, *, create_parent: bool = False) -> Path:
    """Return the canonical JSON conversation path for a session."""
    return get_session_dir(session_id, create=create_parent) / CONVERSATION_FILE_NAME


def get_metadata_path(session_id: str, *, create_parent: bool = False) -> Path:
    """Return the canonical metadata JSON path for a session."""
    return get_session_dir(session_id, create=create_parent) / METADATA_FILE_NAME


def iter_conversation_paths(*, include_legacy: bool = True) -> Iterable[Path]:
    """Yield known conversation JSON paths, newest layout first."""
    seen: set[Path] = set()

    candidates: list[Path] = []
    chat_dir = get_chat_dir()
    if chat_dir.exists():
        candidates.extend(sorted(chat_dir.glob(f"*/{CONVERSATION_FILE_NAME}")))
        candidates.extend(sorted(chat_dir.glob("*.json")))

    if include_legacy:
        if LEGACY_STATE_DIR.exists():
            candidates.extend(sorted(LEGACY_STATE_DIR.glob("*.json")))
        if LEGACY_WORKSPACE_DIR.exists():
            candidates.extend(sorted(LEGACY_WORKSPACE_DIR.glob(f"*/{CONVERSATION_FILE_NAME}")))

    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        yield path


def find_conversation_path(session_id: str) -> Path | None:
    """Find a persisted conversation for a session across current and legacy layouts."""
    safe_id = sanitize_session_id(session_id)
    chat_dir = get_chat_dir()
    candidates = [
        get_conversation_path(session_id),
        chat_dir / f"{safe_id}.json",
        chat_dir / "sessions" / f"{safe_id}.json",
        LEGACY_STATE_DIR / f"{safe_id}.json",
        LEGACY_WORKSPACE_DIR / safe_id / CONVERSATION_FILE_NAME,
    ]
    return next((path for path in candidates if path.exists()), None)


def delete_session_artifacts(session_id: str) -> None:
    """Delete canonical and known legacy artifacts for a session."""
    safe_id = sanitize_session_id(session_id)
    for directory in (get_session_dir(session_id), LEGACY_WORKSPACE_DIR / safe_id):
        if directory.exists() and directory.is_dir():
            shutil.rmtree(directory)

    for path in (
        get_chat_dir() / f"{safe_id}.json",
        get_chat_dir() / "sessions" / f"{safe_id}.json",
        LEGACY_STATE_DIR / f"{safe_id}.json",
    ):
        path.unlink(missing_ok=True)
