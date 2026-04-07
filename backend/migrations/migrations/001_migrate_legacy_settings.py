"""Initial migration: migrate legacy settings format if any."""

import json
import logging
from pathlib import Path

from backend.migrations.registry import MigrationRegistry

logger = logging.getLogger("tenderclaw")


def migrate():
    """Migrate legacy settings."""
    settings_dir = Path(".tenderclaw")
    legacy_file = settings_dir / "config.json"
    
    if legacy_file.exists():
        try:
            with open(legacy_file, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)
            logger.info("Found legacy settings format: %s", legacy_data)
        except Exception as e:
            logger.warning("Failed to read legacy settings: %s", e)


MigrationRegistry.register(
    "001_legacy_settings",
    "Migrate legacy settings format",
    migrate=migrate,
    rollback=None,
)
