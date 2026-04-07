"""Wave 1 Disk Reload Test (explicit)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.session_store import STATE_DIR, SessionData


def main():
    # If there are persisted sessions, attempt to load the first one via disk + from_dict
    if not STATE_DIR.exists() or not any(STATE_DIR.iterdir()):
        print("No persisted sessions found on disk.")
        return

    # Pick first snapshot file
    snapshot_files = sorted([p for p in STATE_DIR.glob('*.json') if p.is_file()])
    if not snapshot_files:
        print("No snapshot files found in state dir.")
        return

    first = snapshot_files[0]
    data = json.loads(first.read_text(encoding='utf-8'))
    loaded = SessionData.from_dict(data)  # type: ignore[attr-defined]

    print(f"Loaded session from disk: {loaded.session_id}")
    print(f"Model: {loaded.model}, Created: {loaded.created_at}, Messages: {len(loaded.messages)}")

if __name__ == '__main__':
    main()
