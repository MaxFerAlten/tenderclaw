"""Tests for notification service — Phase 9."""

from __future__ import annotations

import pytest

from backend.services.notifications import (
    Notification,
    NotificationCategory,
    NotificationLevel,
    NotificationService,
)


@pytest.fixture
def svc() -> NotificationService:
    return NotificationService()


def test_create_notification(svc: NotificationService) -> None:
    notif = svc.create(title="Test", body="hello")
    assert notif.title == "Test"
    assert notif.body == "hello"
    assert notif.level == NotificationLevel.INFO
    assert notif.dismissed is False
    assert notif.id.startswith("notif_")


def test_list_active(svc: NotificationService) -> None:
    svc.create(title="A")
    svc.create(title="B")
    assert len(svc.list_active()) == 2


def test_list_active_excludes_dismissed(svc: NotificationService) -> None:
    n1 = svc.create(title="A")
    svc.create(title="B")
    svc.dismiss(n1.id)
    active = svc.list_active()
    assert len(active) == 1
    assert active[0].title == "B"


def test_dismiss(svc: NotificationService) -> None:
    n = svc.create(title="Dismissable")
    assert svc.dismiss(n.id) is True
    assert svc.list_active() == []


def test_dismiss_nonexistent(svc: NotificationService) -> None:
    assert svc.dismiss("nonexistent") is False


def test_dismiss_all(svc: NotificationService) -> None:
    svc.create(title="A")
    svc.create(title="B")
    svc.create(title="C")
    count = svc.dismiss_all()
    assert count == 3
    assert svc.list_active() == []


def test_dismiss_all_with_session_filter(svc: NotificationService) -> None:
    svc.create(title="A", session_id="s1")
    svc.create(title="B", session_id="s2")
    svc.create(title="C", session_id="s1")
    count = svc.dismiss_all(session_id="s1")
    assert count == 2
    active = svc.list_active()
    assert len(active) == 1
    assert active[0].title == "B"


def test_list_active_session_filter(svc: NotificationService) -> None:
    svc.create(title="Global")
    svc.create(title="S1", session_id="s1")
    svc.create(title="S2", session_id="s2")
    active = svc.list_active(session_id="s1")
    assert len(active) == 2  # Global (no session) + S1
    titles = {n.title for n in active}
    assert "Global" in titles
    assert "S1" in titles


def test_list_active_limit(svc: NotificationService) -> None:
    for i in range(10):
        svc.create(title=f"N{i}")
    assert len(svc.list_active(limit=3)) == 3


def test_list_all_includes_dismissed(svc: NotificationService) -> None:
    n = svc.create(title="X")
    svc.dismiss(n.id)
    svc.create(title="Y")
    assert len(svc.list_all()) == 2


def test_clear(svc: NotificationService) -> None:
    svc.create(title="A")
    svc.create(title="B")
    svc.clear()
    assert svc.list_all() == []


def test_stats(svc: NotificationService) -> None:
    svc.create(title="A", level=NotificationLevel.INFO)
    svc.create(title="B", level=NotificationLevel.ERROR)
    n = svc.create(title="C", level=NotificationLevel.WARNING)
    svc.dismiss(n.id)
    stats = svc.stats()
    assert stats["total"] == 3
    assert stats["active"] == 2
    assert stats["dismissed"] == 1
    assert stats["by_level"]["info"] == 1
    assert stats["by_level"]["error"] == 1


def test_notification_levels() -> None:
    for level in NotificationLevel:
        n = Notification(title="test", level=level)
        assert n.level == level


def test_notification_categories() -> None:
    for cat in NotificationCategory:
        n = Notification(title="test", category=cat)
        assert n.category == cat


def test_max_notifications() -> None:
    svc = NotificationService()
    for i in range(250):
        svc.create(title=f"N{i}")
    assert len(svc.list_all(limit=300)) == 200  # MAX_NOTIFICATIONS


def test_agent_notification(svc: NotificationService) -> None:
    notif = svc.create(
        title="Oracle started",
        body="Researching codebase",
        level=NotificationLevel.INFO,
        category=NotificationCategory.AGENT,
        agent_name="oracle",
        session_id="sess_123",
        auto_dismiss_ms=4000,
    )
    assert notif.agent_name == "oracle"
    assert notif.category == NotificationCategory.AGENT
    assert notif.auto_dismiss_ms == 4000
    assert notif.session_id == "sess_123"


def test_pipeline_notification(svc: NotificationService) -> None:
    notif = svc.create(
        title="Pipeline failed",
        body="Max fix attempts reached",
        level=NotificationLevel.ERROR,
        category=NotificationCategory.PIPELINE,
    )
    assert notif.level == NotificationLevel.ERROR
    assert notif.category == NotificationCategory.PIPELINE
    assert notif.auto_dismiss_ms == 5000


def test_metadata(svc: NotificationService) -> None:
    notif = svc.create(
        title="With metadata",
        metadata={"turn": 3, "model": "claude-sonnet"},
    )
    assert notif.metadata["turn"] == 3
    assert notif.metadata["model"] == "claude-sonnet"
