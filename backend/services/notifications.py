"""Notification service — in-memory store for real-time HUD notifications.

Manages notifications lifecycle: create, read, dismiss, broadcast.
Integrates with WebSocket to push notifications to connected clients.
"""

from __future__ import annotations

import logging
import uuid
from collections import deque
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("tenderclaw.services.notifications")

MAX_NOTIFICATIONS = 200


class NotificationLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class NotificationCategory(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    PIPELINE = "pipeline"
    SYSTEM = "system"
    SECURITY = "security"


class Notification(BaseModel):
    id: str = Field(default_factory=lambda: f"notif_{uuid.uuid4().hex[:8]}")
    level: NotificationLevel = NotificationLevel.INFO
    category: NotificationCategory = NotificationCategory.SYSTEM
    title: str
    body: str = ""
    agent_name: str | None = None
    session_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dismissed: bool = False
    auto_dismiss_ms: int = 5000
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationService:
    """In-memory notification store with broadcast capability."""

    def __init__(self) -> None:
        self._notifications: deque[Notification] = deque(maxlen=MAX_NOTIFICATIONS)
        self._broadcast_fn: Any | None = None

    def set_broadcast(self, fn: Any) -> None:
        self._broadcast_fn = fn

    def create(
        self,
        title: str,
        body: str = "",
        level: NotificationLevel = NotificationLevel.INFO,
        category: NotificationCategory = NotificationCategory.SYSTEM,
        agent_name: str | None = None,
        session_id: str | None = None,
        auto_dismiss_ms: int = 5000,
        metadata: dict[str, Any] | None = None,
    ) -> Notification:
        notif = Notification(
            title=title,
            body=body,
            level=level,
            category=category,
            agent_name=agent_name,
            session_id=session_id,
            auto_dismiss_ms=auto_dismiss_ms,
            metadata=metadata or {},
        )
        self._notifications.appendleft(notif)
        logger.debug("Notification created: [%s] %s", notif.level.value, notif.title)
        return notif

    def list_active(self, session_id: str | None = None, limit: int = 50) -> list[Notification]:
        items = [n for n in self._notifications if not n.dismissed]
        if session_id:
            items = [n for n in items if n.session_id is None or n.session_id == session_id]
        return items[:limit]

    def list_all(self, limit: int = 100) -> list[Notification]:
        return list(self._notifications)[:limit]

    def dismiss(self, notification_id: str) -> bool:
        for n in self._notifications:
            if n.id == notification_id:
                n.dismissed = True
                return True
        return False

    def dismiss_all(self, session_id: str | None = None) -> int:
        count = 0
        for n in self._notifications:
            if n.dismissed:
                continue
            if session_id and n.session_id and n.session_id != session_id:
                continue
            n.dismissed = True
            count += 1
        return count

    def clear(self) -> None:
        self._notifications.clear()

    def stats(self) -> dict[str, Any]:
        active = [n for n in self._notifications if not n.dismissed]
        by_level = {}
        for n in active:
            by_level[n.level.value] = by_level.get(n.level.value, 0) + 1
        return {
            "total": len(self._notifications),
            "active": len(active),
            "dismissed": len(self._notifications) - len(active),
            "by_level": by_level,
        }


notification_service = NotificationService()
