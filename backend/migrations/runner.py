"""Runner for settings migrations."""

import json
import logging
from pathlib import Path

from backend.migrations.registry import MigrationRegistry, Migration

MIGRATIONS_STATE_FILE = Path(".tenderclaw") / "migrations.json"

logger = logging.getLogger("tenderclaw")


def load_migrations_state() -> dict[str, str]:
    """Load migration state from disk."""
    if MIGRATIONS_STATE_FILE.exists():
        try:
            with open(MIGRATIONS_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load migrations state: %s", e)
    return {}


def save_migrations_state(state: dict[str, str]):
    """Save migration state to disk."""
    MIGRATIONS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MIGRATIONS_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def run_all_pending() -> list[str]:
    """Run all pending migrations."""
    state = load_migrations_state()
    MigrationRegistry.set_applied_ids(state)
    
    run_ids = MigrationRegistry.run_pending()
    
    if run_ids:
        for mid in run_ids:
            state[mid] = MigrationRegistry._applied[mid].isoformat()
        save_migrations_state(state)
        logger.info("Applied migrations: %s", run_ids)
    
    return run_ids


def get_migration_status() -> dict:
    """Get status of all migrations."""
    all_migrations = MigrationRegistry.get_all()
    pending = MigrationRegistry.get_pending()
    applied = MigrationRegistry.get_applied()
    
    return {
        "total": len(all_migrations),
        "applied": len(applied),
        "pending": len(pending),
        "migrations": [
            {
                "id": m.id,
                "description": m.description,
                "status": "applied" if m.id in MigrationRegistry.get_applied_ids() else "pending",
                "applied_at": m.applied_at.isoformat() if m.applied_at else None,
            }
            for m in sorted(all_migrations, key=lambda x: x.id)
        ],
    }
