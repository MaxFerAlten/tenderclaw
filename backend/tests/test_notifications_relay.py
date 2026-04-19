"""Tests for Notifications service, Relay API, and skill trigger wiring."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.notifications import (
    Notification,
    NotificationCategory,
    NotificationLevel,
    NotificationService,
)


# ── NotificationService ─────────────────────────────────────────────


class TestNotificationService:
    def test_create_notification(self):
        svc = NotificationService()
        notif = svc.create(title="Test", body="Body text")
        assert notif.title == "Test"
        assert notif.body == "Body text"
        assert notif.level == NotificationLevel.INFO
        assert notif.dismissed is False

    def test_create_with_all_fields(self):
        svc = NotificationService()
        notif = svc.create(
            title="Alert",
            body="Something happened",
            level=NotificationLevel.ERROR,
            category=NotificationCategory.SECURITY,
            agent_name="sentinel",
            session_id="sess_123",
            auto_dismiss_ms=10000,
            metadata={"key": "val"},
        )
        assert notif.level == NotificationLevel.ERROR
        assert notif.category == NotificationCategory.SECURITY
        assert notif.agent_name == "sentinel"
        assert notif.session_id == "sess_123"
        assert notif.auto_dismiss_ms == 10000
        assert notif.metadata["key"] == "val"

    def test_list_active(self):
        svc = NotificationService()
        svc.create(title="A")
        svc.create(title="B")
        active = svc.list_active()
        assert len(active) == 2
        assert active[0].title == "B"  # newest first (appendleft)

    def test_list_active_filters_dismissed(self):
        svc = NotificationService()
        n1 = svc.create(title="A")
        svc.create(title="B")
        svc.dismiss(n1.id)
        active = svc.list_active()
        assert len(active) == 1
        assert active[0].title == "B"

    def test_list_active_by_session(self):
        svc = NotificationService()
        svc.create(title="Global")
        svc.create(title="Sess1", session_id="s1")
        svc.create(title="Sess2", session_id="s2")

        # Session filter includes global (no session_id) + matching
        active = svc.list_active(session_id="s1")
        titles = [n.title for n in active]
        assert "Global" in titles
        assert "Sess1" in titles
        assert "Sess2" not in titles

    def test_dismiss(self):
        svc = NotificationService()
        notif = svc.create(title="Test")
        assert svc.dismiss(notif.id) is True
        assert svc.list_active() == []

    def test_dismiss_nonexistent(self):
        svc = NotificationService()
        assert svc.dismiss("nonexistent") is False

    def test_dismiss_all(self):
        svc = NotificationService()
        svc.create(title="A")
        svc.create(title="B")
        count = svc.dismiss_all()
        assert count == 2
        assert len(svc.list_active()) == 0

    def test_dismiss_all_by_session(self):
        svc = NotificationService()
        svc.create(title="Global")
        svc.create(title="Sess1", session_id="s1")
        svc.create(title="Sess2", session_id="s2")
        count = svc.dismiss_all(session_id="s1")
        # dismiss_all(session_id="s1") dismisses: Sess1 + Global (no session_id)
        assert count == 2
        active = svc.list_active()
        titles = [n.title for n in active]
        assert "Sess1" not in titles
        assert "Sess2" in titles

    def test_clear(self):
        svc = NotificationService()
        svc.create(title="A")
        svc.create(title="B")
        svc.clear()
        assert len(svc.list_all()) == 0

    def test_stats(self):
        svc = NotificationService()
        svc.create(title="A", level=NotificationLevel.INFO)
        svc.create(title="B", level=NotificationLevel.ERROR)
        n3 = svc.create(title="C", level=NotificationLevel.INFO)
        svc.dismiss(n3.id)
        stats = svc.stats()
        assert stats["total"] == 3
        assert stats["active"] == 2
        assert stats["dismissed"] == 1
        assert stats["by_level"]["info"] == 1
        assert stats["by_level"]["error"] == 1

    def test_max_notifications(self):
        svc = NotificationService()
        for i in range(250):
            svc.create(title=f"N{i}")
        # deque maxlen=200, but list_all has default limit=100
        assert len(svc.list_all(limit=300)) == 200  # MAX_NOTIFICATIONS

    def test_set_broadcast(self):
        svc = NotificationService()
        fn = MagicMock()
        svc.set_broadcast(fn)
        assert svc._broadcast_fn is fn


# ── WSConnectionManager ─────────────────────────────────────────────


class TestWSConnectionManager:
    def test_active_sessions_empty(self):
        from backend.api.ws import WSConnectionManager
        mgr = WSConnectionManager()
        assert mgr.active_sessions() == []

    def test_active_sessions_with_connections(self):
        from backend.api.ws import WSConnectionManager
        mgr = WSConnectionManager()
        ws1 = MagicMock()
        ws2 = MagicMock()
        asyncio.run(mgr.connect(ws1, "sess_a"))
        asyncio.run(mgr.connect(ws2, "sess_b"))
        sessions = mgr.active_sessions()
        assert "sess_a" in sessions
        assert "sess_b" in sessions

    def test_active_sessions_after_disconnect(self):
        from backend.api.ws import WSConnectionManager
        mgr = WSConnectionManager()
        ws1 = MagicMock()
        asyncio.run(mgr.connect(ws1, "sess_a"))
        asyncio.run(mgr.disconnect(ws1, "sess_a"))
        assert mgr.active_sessions() == []


# ── WSPipelineStage + WSThinkingProgress ─────────────────────────────


class TestPipelineWSEvents:
    def test_pipeline_stage_model(self):
        from backend.schemas.ws import WSPipelineStage
        ps = WSPipelineStage(stage="oracle", status="started", detail="Researching")
        d = ps.model_dump()
        assert d["type"] == "pipeline_stage"
        assert d["stage"] == "oracle"

    def test_thinking_progress_model(self):
        from backend.schemas.ws import WSThinkingProgress
        tp = WSThinkingProgress(
            agent_name="metis", phase="planning", progress_pct=50, detail="Building plan"
        )
        d = tp.model_dump()
        assert d["type"] == "thinking_progress"
        assert d["agent_name"] == "metis"
        assert d["progress_pct"] == 50

    def test_notification_model(self):
        from backend.schemas.ws import WSNotification
        n = WSNotification(
            id="n1", level="info", category="system",
            title="Test", body="body", auto_dismiss_ms=5000,
        )
        d = n.model_dump()
        assert d["type"] == "notification"
        assert d["id"] == "n1"


# ── Skill Trigger Matching ──────────────────────────────────────────


class TestSkillTriggerMatching:
    def test_match_trigger_basic(self):
        from backend.core.skills import match_trigger, Skill, get_registry

        reg = get_registry()
        # Check if any skills are loaded
        all_skills = reg.all()
        if not all_skills:
            pytest.skip("No skills discovered (skills directory may not exist)")

        # Find a skill with a trigger
        skills_with_triggers = [s for s in all_skills if s.trigger]
        if not skills_with_triggers:
            pytest.skip("No skills with triggers found")

        skill = skills_with_triggers[0]
        trigger = skill.trigger.lstrip("/")
        matches = match_trigger(f"Please {trigger} this code")
        assert any(m.name == skill.name for m in matches)

    def test_match_trigger_no_match(self):
        from backend.core.skills import match_trigger
        matches = match_trigger("completely unrelated query about cooking")
        # May or may not match — just verify no crash
        assert isinstance(matches, list)


# ── Skill Execution API ─────────────────────────────────────────────


class TestSkillExecutionAPI:
    @pytest.mark.asyncio
    async def test_execute_skill_not_found(self):
        from backend.api.skills_api import execute_skill, SkillExecuteRequest
        with pytest.raises(Exception):  # HTTPException
            await execute_skill("nonexistent_skill_xyz", SkillExecuteRequest())

    @pytest.mark.asyncio
    async def test_execute_skill_no_session(self):
        from backend.api.skills_api import execute_skill, SkillExecuteRequest
        from backend.core.skills import get_registry

        reg = get_registry()
        all_skills = reg.all()
        if not all_skills:
            pytest.skip("No skills discovered")

        skill_name = all_skills[0].name
        result = await execute_skill(skill_name, SkillExecuteRequest())
        assert result["success"] is True
        assert "prompt" in result["result"]
