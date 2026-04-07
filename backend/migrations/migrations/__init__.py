"""Migrations package."""

import importlib
import pkgutil
from pathlib import Path

_migrations_dir = Path(__file__).parent
for module_info in pkgutil.iter_modules([_migrations_dir]):
    if module_info.name != "__init__":
        importlib.import_module(f"backend.migrations.migrations.{module_info.name}")
