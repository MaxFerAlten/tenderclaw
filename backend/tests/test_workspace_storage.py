from __future__ import annotations

import json
from pathlib import Path

from backend.api import config as config_module
from backend.schemas.sessions import SessionCreate
from backend.services.image_store import save_image
from backend.services.session_store import SessionStore
from backend.services.workspace import ensure_workspace_dirs, get_default_workspace_dir


def test_default_workspace_chat_dir_is_created_in_home(tmp_path, monkeypatch) -> None:
    snapshot = dict(config_module._global_config)
    monkeypatch.setenv("HOME", str(tmp_path))
    config_module._global_config["chat_storage_path"] = ""

    try:
        chat_dir = ensure_workspace_dirs()
    finally:
        config_module._global_config.clear()
        config_module._global_config.update(snapshot)

    assert chat_dir == tmp_path / "workspace_tenderclaw" / "chat"
    assert chat_dir.is_dir()


def test_default_workspace_uses_platform_home_path(tmp_path, monkeypatch) -> None:
    snapshot = dict(config_module._global_config)
    fake_windows_home = tmp_path / "Users" / "TenderMachine"
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_windows_home))
    config_module._global_config["chat_storage_path"] = ""

    try:
        workspace_dir = get_default_workspace_dir()
        chat_dir = ensure_workspace_dirs()
    finally:
        config_module._global_config.clear()
        config_module._global_config.update(snapshot)

    assert workspace_dir == fake_windows_home / "workspace_tenderclaw"
    assert chat_dir == fake_windows_home / "workspace_tenderclaw" / "chat"
    assert workspace_dir.is_dir()
    assert chat_dir.is_dir()


def test_session_store_writes_conversation_json_under_chat_dir(tmp_path) -> None:
    snapshot = dict(config_module._global_config)
    chat_dir = tmp_path / "workspace_tenderclaw" / "chat"
    config_module._global_config["chat_storage_path"] = str(chat_dir)

    try:
        store = SessionStore()
        state = store.create(SessionCreate(model=None, system_prompt_append=None, working_directory="."))
    finally:
        config_module._global_config.clear()
        config_module._global_config.update(snapshot)

    conversation_path = chat_dir / state.session_id / "conversation.json"
    assert conversation_path.exists()
    assert (chat_dir / state.session_id / "index.html").exists()
    assert (chat_dir / "index.html").exists()
    assert (chat_dir / "sessions.json").exists()
    assert (chat_dir / "viewer.css").exists()
    assert (chat_dir / "viewer.js").exists()

    payload = json.loads(conversation_path.read_text(encoding="utf-8"))
    assert payload["session_id"] == state.session_id
    assert payload["messages"] == []

    session_html = (chat_dir / state.session_id / "index.html").read_text(encoding="utf-8")
    assert '<script src="../viewer.js"></script>' in session_html
    assert 'jsonUrl: "conversation.json"' in session_html
    assert "TenderClawChatViewer.bootSession" in session_html
    assert "fallback:" not in session_html

    viewer_js = (chat_dir / "viewer.js").read_text(encoding="utf-8")
    assert 'fetch(url,{cache:"no-store"})' in viewer_js
    assert "function renderConversation(data)" in viewer_js
    assert 'Choose " + label + " from this folder' in viewer_js

    sessions_payload = json.loads((chat_dir / "sessions.json").read_text(encoding="utf-8"))
    assert sessions_payload["sessions"][0]["href"] == f"{state.session_id}/index.html"

    chat_html = (chat_dir / "index.html").read_text(encoding="utf-8")
    assert '<script src="viewer.js"></script>' in chat_html
    assert 'jsonUrl: "sessions.json"' in chat_html
    assert "TenderClawChatViewer.bootIndex" in chat_html
    assert "fallback:" not in chat_html


def test_images_are_saved_next_to_conversation_json(tmp_path) -> None:
    snapshot = dict(config_module._global_config)
    chat_dir = tmp_path / "workspace_tenderclaw" / "chat"
    config_module._global_config["chat_storage_path"] = str(chat_dir)

    try:
        saved = save_image("tc_image_test", 0, "screen.png", "image/png", b"png-bytes")
    finally:
        config_module._global_config.clear()
        config_module._global_config.update(snapshot)

    assert saved is not None
    saved_path = Path(saved)
    assert saved_path.parent == chat_dir / "tc_image_test"
    assert saved_path.read_bytes() == b"png-bytes"
