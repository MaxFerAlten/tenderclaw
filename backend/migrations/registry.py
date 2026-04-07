"""Registry for settings migrations."""

from dataclasses import dataclass, field
from typing import Callable, Any
from datetime import UTC, datetime


@dataclass
class Migration:
    id: str
    description: str
    migrate: Callable[[], None]
    rollback: Callable[[], None] | None = None
    applied_at: datetime | None = None


class MigrationRegistry:
    _migrations: dict[str, Migration] = {}
    _applied: dict[str, datetime] = {}
    
    @classmethod
    def register(cls, migration_id: str, description: str, 
                 migrate: Callable, rollback: Callable | None = None):
        """Register a new migration."""
        cls._migrations[migration_id] = Migration(
            id=migration_id,
            description=description,
            migrate=migrate,
            rollback=rollback,
        )
    
    @classmethod
    def get_pending(cls) -> list[Migration]:
        """Get migrations not yet applied."""
        return [
            m for m in cls._migrations.values()
            if m.id not in cls._applied
        ]
    
    @classmethod
    def get_applied(cls) -> list[Migration]:
        """Get applied migrations."""
        applied = []
        for m in cls._migrations.values():
            if m.id in cls._applied:
                m.applied_at = cls._applied[m.id]
                applied.append(m)
        return applied
    
    @classmethod
    def mark_applied(cls, migration_id: str):
        """Mark migration as applied."""
        cls._applied[migration_id] = datetime.now(UTC)
    
    @classmethod
    def get_applied_ids(cls) -> set[str]:
        """Get set of applied migration IDs."""
        return set(cls._applied.keys())
    
    @classmethod
    def set_applied_ids(cls, applied_ids: dict[str, str]):
        """Set applied migration IDs from external state."""
        cls._applied = {
            k: datetime.fromisoformat(v) if v else datetime.now(UTC)
            for k, v in applied_ids.items()
        }
    
    @classmethod
    def run_pending(cls) -> list[str]:
        """Run all pending migrations. Returns list of run migration IDs."""
        run_ids = []
        for migration in cls.get_pending():
            try:
                migration.migrate()
                cls.mark_applied(migration.id)
                run_ids.append(migration.id)
            except Exception as e:
                raise RuntimeError(f"Migration {migration.id} failed: {e}")
        return run_ids
    
    @classmethod
    def get_all(cls) -> list[Migration]:
        """Get all registered migrations."""
        return list(cls._migrations.values())
