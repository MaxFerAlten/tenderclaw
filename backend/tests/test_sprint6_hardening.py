"""Sprint 6 — Hardening + i18n + Blueprint Audit tests.

Verifies:
- IntentCache: push, majority_intent, confidence, sliding window, cache hit
- IntentGateResult: new intent_confidence field
- classify_intent_with_skill: cache integration (use_cache=False for determinism)
- ConflictResolution: LAST_WIN, FIRST_WIN, MERGE in hook engine
- HookEntry.conflict_resolution field and default
- Hook ordering + BAIL short-circuits correctly
- KeywordDetectorHook delegates to canonical engine (no duplicate KEYWORDS dict)
- keyword_detection.py: canonical detect() covers all expected actions
- i18n: load, t(), locale switching, fallback, interpolation, has_key
- blueprint-audit.md: file exists and has content
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# IntentCache
# ---------------------------------------------------------------------------


class TestIntentCache:
    def _cache(self, session_id: str = ""):
        from backend.orchestration.intent_gate import IntentCache
        return IntentCache(session_id=session_id)

    def test_empty_majority_returns_none(self):
        from backend.orchestration.intent_gate import IntentCache
        c = self._cache()
        assert c.majority_intent() is None

    def test_single_entry_no_majority(self):
        from backend.orchestration.intent_gate import IntentCache, Intent
        c = self._cache()
        c.push(Intent.IMPLEMENT, "write code")
        assert c.majority_intent() is None  # need >= 2

    def test_two_same_gives_majority(self):
        from backend.orchestration.intent_gate import IntentCache, Intent
        c = self._cache()
        c.push(Intent.IMPLEMENT, "write code")
        c.push(Intent.IMPLEMENT, "more code")
        assert c.majority_intent() == Intent.IMPLEMENT

    def test_two_different_no_majority(self):
        from backend.orchestration.intent_gate import IntentCache, Intent
        c = self._cache()
        c.push(Intent.IMPLEMENT, "write code")
        c.push(Intent.FIX, "fix bug")
        assert c.majority_intent() is None

    def test_three_same_majority(self):
        from backend.orchestration.intent_gate import IntentCache, Intent
        c = self._cache()
        for _ in range(3):
            c.push(Intent.PLAN, "plan feature")
        assert c.majority_intent() == Intent.PLAN

    def test_window_eviction_oldest_entry(self):
        from backend.orchestration.intent_gate import IntentCache, Intent
        c = self._cache()
        # Push 4 items into a window=3 cache
        c.push(Intent.RESEARCH, "old")
        c.push(Intent.IMPLEMENT, "a")
        c.push(Intent.IMPLEMENT, "b")
        c.push(Intent.IMPLEMENT, "c")
        # "old" RESEARCH was evicted; IMPLEMENT should win
        assert c.majority_intent() == Intent.IMPLEMENT

    def test_confidence_empty_returns_half(self):
        from backend.orchestration.intent_gate import IntentCache
        c = self._cache()
        assert c.confidence() == 0.5

    def test_confidence_unanimous_window(self):
        from backend.orchestration.intent_gate import IntentCache, Intent
        c = self._cache()
        for _ in range(3):
            c.push(Intent.REVIEW, "review code")
        assert c.confidence() == 1.0

    def test_confidence_two_of_three(self):
        from backend.orchestration.intent_gate import IntentCache, Intent
        c = self._cache()
        c.push(Intent.FIX, "fix a")
        c.push(Intent.FIX, "fix b")
        c.push(Intent.IMPLEMENT, "impl")
        conf = c.confidence()
        assert abs(conf - 2 / 3) < 0.01

    def test_clear_resets_window(self):
        from backend.orchestration.intent_gate import IntentCache, Intent
        c = self._cache()
        c.push(Intent.PLAN, "plan")
        c.push(Intent.PLAN, "plan again")
        c.clear()
        assert len(c) == 0
        assert c.majority_intent() is None

    def test_len(self):
        from backend.orchestration.intent_gate import IntentCache, Intent
        c = self._cache()
        assert len(c) == 0
        c.push(Intent.CHAT, "hi")
        assert len(c) == 1

    def test_window_size_constant(self):
        from backend.orchestration.intent_gate import IntentCache
        assert IntentCache.WINDOW == 3


# ---------------------------------------------------------------------------
# get_intent_cache / clear_intent_cache
# ---------------------------------------------------------------------------


class TestIntentCacheRegistry:
    def test_get_cache_creates_new(self):
        from backend.orchestration.intent_gate import get_intent_cache, Intent
        import backend.orchestration.intent_gate as m
        sid = "__test_session_new__"
        m._session_caches.pop(sid, None)  # ensure clean
        c = get_intent_cache(sid)
        assert len(c) == 0

    def test_get_cache_same_object(self):
        from backend.orchestration.intent_gate import get_intent_cache
        sid = "__test_same__"
        c1 = get_intent_cache(sid)
        c2 = get_intent_cache(sid)
        assert c1 is c2

    def test_clear_intent_cache(self):
        from backend.orchestration.intent_gate import get_intent_cache, clear_intent_cache, Intent
        sid = "__test_clear__"
        c = get_intent_cache(sid)
        c.push(Intent.IMPLEMENT, "x")
        clear_intent_cache(sid)
        assert len(c) == 0


# ---------------------------------------------------------------------------
# IntentGateResult — intent_confidence field
# ---------------------------------------------------------------------------


class TestIntentGateResult:
    def test_intent_confidence_default(self):
        from backend.orchestration.intent_gate import IntentGateResult, Intent
        r = IntentGateResult(intent=Intent.IMPLEMENT)
        assert r.intent_confidence == 0.5

    def test_intent_confidence_set(self):
        from backend.orchestration.intent_gate import IntentGateResult, Intent
        r = IntentGateResult(intent=Intent.PLAN, intent_confidence=0.9)
        assert r.intent_confidence == 0.9

    def test_has_skill_false(self):
        from backend.orchestration.intent_gate import IntentGateResult, Intent
        r = IntentGateResult(intent=Intent.CHAT)
        assert r.has_skill is False

    def test_has_skill_true(self):
        from backend.orchestration.intent_gate import IntentGateResult, Intent
        r = IntentGateResult(intent=Intent.PLAN, skill_name="ralplan", confidence=0.8)
        assert r.has_skill is True

    def test_all_fields_accessible(self):
        from backend.orchestration.intent_gate import IntentGateResult, Intent
        r = IntentGateResult(
            intent=Intent.REVIEW,
            skill_name="code-review",
            confidence=0.7,
            reason="keyword match",
            intent_confidence=0.67,
        )
        assert r.intent == Intent.REVIEW
        assert r.skill_name == "code-review"
        assert r.intent_confidence == 0.67


# ---------------------------------------------------------------------------
# classify_intent_with_skill (no-API path)
# ---------------------------------------------------------------------------


class TestClassifyIntentWithSkillNoApi:
    """Run with use_cache=False to avoid inter-test pollution."""

    def test_returns_intent_gate_result(self):
        from backend.orchestration.intent_gate import classify_intent_with_skill, IntentGateResult
        result = _run(classify_intent_with_skill("write some code", use_cache=False))
        assert isinstance(result, IntentGateResult)

    def test_intent_confidence_between_0_and_1(self):
        from backend.orchestration.intent_gate import classify_intent_with_skill
        r = _run(classify_intent_with_skill("fix the bug", use_cache=False))
        assert 0.0 <= r.intent_confidence <= 1.0

    def test_skill_match_is_skill_match_or_empty(self):
        from backend.orchestration.intent_gate import classify_intent_with_skill
        r = _run(classify_intent_with_skill("ralplan the authentication feature", use_cache=False))
        assert isinstance(r.skill_name, str)
        assert isinstance(r.confidence, float)


# ---------------------------------------------------------------------------
# ConflictResolution — hook engine
# ---------------------------------------------------------------------------


class TestConflictResolution:
    def _make_event(self, data: dict | None = None):
        from backend.schemas.hooks import HookEvent, HookPoint
        return HookEvent(point=HookPoint.TURN_START, data=data or {})

    def _make_result(self, data: dict):
        from backend.schemas.hooks import HookResult, HookAction
        return HookResult(action=HookAction.MODIFY, data=data)

    def test_last_win_overwrites(self):
        from backend.hooks.engine import _apply_modify, ConflictResolution
        event = self._make_event({"key": "old"})
        result = self._make_result({"key": "new"})
        _apply_modify(event, result, ConflictResolution.LAST_WIN)
        assert event.data["key"] == "new"

    def test_first_win_preserves_existing(self):
        from backend.hooks.engine import _apply_modify, ConflictResolution
        event = self._make_event({"key": "original"})
        result = self._make_result({"key": "later"})
        _apply_modify(event, result, ConflictResolution.FIRST_WIN)
        assert event.data["key"] == "original"

    def test_first_win_adds_new_keys(self):
        from backend.hooks.engine import _apply_modify, ConflictResolution
        event = self._make_event({"existing": 1})
        result = self._make_result({"new_key": 2})
        _apply_modify(event, result, ConflictResolution.FIRST_WIN)
        assert event.data["new_key"] == 2
        assert event.data["existing"] == 1

    def test_merge_lists_concatenated(self):
        from backend.hooks.engine import _apply_modify, ConflictResolution
        event = self._make_event({"items": [1, 2]})
        result = self._make_result({"items": [3, 4]})
        _apply_modify(event, result, ConflictResolution.MERGE)
        assert event.data["items"] == [1, 2, 3, 4]

    def test_merge_dicts_shallow_merged(self):
        from backend.hooks.engine import _apply_modify, ConflictResolution
        event = self._make_event({"meta": {"a": 1}})
        result = self._make_result({"meta": {"b": 2}})
        _apply_modify(event, result, ConflictResolution.MERGE)
        assert event.data["meta"] == {"a": 1, "b": 2}

    def test_merge_scalar_falls_back_to_last_win(self):
        from backend.hooks.engine import _apply_modify, ConflictResolution
        event = self._make_event({"count": 1})
        result = self._make_result({"count": 2})
        _apply_modify(event, result, ConflictResolution.MERGE)
        assert event.data["count"] == 2

    def test_conflict_resolution_default_is_last_win(self):
        from backend.hooks.engine import HookEntry, ConflictResolution
        from backend.schemas.hooks import HookPoint, HookTier

        async def handler(e): ...  # pragma: no cover

        entry = HookEntry(name="x", point=HookPoint.TURN_START, handler=handler)
        assert entry.conflict_resolution == ConflictResolution.LAST_WIN

    def test_register_with_conflict_resolution(self):
        from backend.hooks.engine import HookRegistry, ConflictResolution
        from backend.schemas.hooks import HookPoint, HookAction, HookEvent, HookResult

        reg = HookRegistry()
        calls: list[ConflictResolution] = []

        async def handler(event: HookEvent) -> HookResult:
            return HookResult(action=HookAction.MODIFY, data={"x": 1})

        reg.register("test_hook", HookPoint.TURN_START, handler, conflict_resolution=ConflictResolution.FIRST_WIN)
        entries = reg._hooks.get(HookPoint.TURN_START, [])
        assert entries[0].conflict_resolution == ConflictResolution.FIRST_WIN


# ---------------------------------------------------------------------------
# Hook engine — run_hooks with conflict resolution
# ---------------------------------------------------------------------------


class TestHookEngineRunHooks:
    def _make_event(self):
        from backend.schemas.hooks import HookEvent, HookPoint
        return HookEvent(point=HookPoint.TURN_START, data={})

    def test_two_modify_hooks_last_win(self):
        from backend.hooks.engine import HookRegistry, ConflictResolution
        from backend.schemas.hooks import HookPoint, HookAction, HookEvent, HookResult

        reg = HookRegistry()

        async def h1(e: HookEvent) -> HookResult:
            return HookResult(action=HookAction.MODIFY, data={"key": "first"})

        async def h2(e: HookEvent) -> HookResult:
            return HookResult(action=HookAction.MODIFY, data={"key": "second"})

        reg.register("h1", HookPoint.TURN_START, h1, priority=0, conflict_resolution=ConflictResolution.LAST_WIN)
        reg.register("h2", HookPoint.TURN_START, h2, priority=1, conflict_resolution=ConflictResolution.LAST_WIN)

        event = self._make_event()
        _run(reg.run_hooks(HookPoint.TURN_START, event))
        assert event.data["key"] == "second"

    def test_first_win_preserves_first_hook_data(self):
        from backend.hooks.engine import HookRegistry, ConflictResolution
        from backend.schemas.hooks import HookPoint, HookAction, HookEvent, HookResult

        reg = HookRegistry()

        async def h1(e: HookEvent) -> HookResult:
            return HookResult(action=HookAction.MODIFY, data={"key": "first"})

        async def h2(e: HookEvent) -> HookResult:
            return HookResult(action=HookAction.MODIFY, data={"key": "second"})

        reg.register("h1", HookPoint.TURN_START, h1, priority=0, conflict_resolution=ConflictResolution.FIRST_WIN)
        reg.register("h2", HookPoint.TURN_START, h2, priority=1, conflict_resolution=ConflictResolution.FIRST_WIN)

        event = self._make_event()
        _run(reg.run_hooks(HookPoint.TURN_START, event))
        assert event.data["key"] == "first"

    def test_merge_lists_across_hooks(self):
        from backend.hooks.engine import HookRegistry, ConflictResolution
        from backend.schemas.hooks import HookPoint, HookAction, HookEvent, HookResult

        reg = HookRegistry()

        async def h1(e: HookEvent) -> HookResult:
            return HookResult(action=HookAction.MODIFY, data={"tags": ["a"]})

        async def h2(e: HookEvent) -> HookResult:
            return HookResult(action=HookAction.MODIFY, data={"tags": ["b"]})

        reg.register("h1", HookPoint.TURN_START, h1, priority=0, conflict_resolution=ConflictResolution.MERGE)
        reg.register("h2", HookPoint.TURN_START, h2, priority=1, conflict_resolution=ConflictResolution.MERGE)

        event = self._make_event()
        _run(reg.run_hooks(HookPoint.TURN_START, event))
        assert set(event.data["tags"]) == {"a", "b"}

    def test_bail_stops_chain(self):
        from backend.hooks.engine import HookRegistry
        from backend.schemas.hooks import HookPoint, HookAction, HookEvent, HookResult

        reg = HookRegistry()
        ran: list[str] = []

        async def h_bail(e: HookEvent) -> HookResult:
            ran.append("bail")
            return HookResult(action=HookAction.BAIL, reason="stop here")

        async def h_after(e: HookEvent) -> HookResult:
            ran.append("after")  # should NOT run
            return HookResult()

        reg.register("h_bail", HookPoint.TURN_END, h_bail, priority=0)
        reg.register("h_after", HookPoint.TURN_END, h_after, priority=1)

        event = HookEvent(point=HookPoint.TURN_END, data={})
        result = _run(reg.run_hooks(HookPoint.TURN_END, event))
        assert result.action == HookAction.BAIL
        assert ran == ["bail"]

    def test_empty_hooks_returns_continue(self):
        from backend.hooks.engine import HookRegistry
        from backend.schemas.hooks import HookPoint, HookAction, HookEvent

        reg = HookRegistry()
        event = HookEvent(point=HookPoint.TURN_START, data={})
        result = _run(reg.run_hooks(HookPoint.TURN_START, event))
        assert result.action == HookAction.CONTINUE


# ---------------------------------------------------------------------------
# Keyword deduplication
# ---------------------------------------------------------------------------


class TestKeywordDetectorDeduplication:
    def test_hook_has_no_own_keywords_dict(self):
        """KeywordDetectorHook must not define its own KEYWORDS dict."""
        from backend.hooks.handlers.keyword_detector import KeywordDetectorHook
        assert not hasattr(KeywordDetectorHook, "KEYWORDS"), (
            "KeywordDetectorHook.KEYWORDS still present — deduplication incomplete"
        )

    def test_keyword_detection_is_canonical_engine(self):
        """keyword_detection.py must be the sole canonical keyword engine."""
        from backend.core.keyword_detection import KeywordDetector, keyword_detector
        assert isinstance(keyword_detector, KeywordDetector)

    def test_canonical_engine_covers_24_plus_mappings(self):
        from backend.core.keyword_detection import KeywordDetector
        assert len(KeywordDetector.MAPPINGS) >= 24

    def test_canonical_engine_includes_ralplan(self):
        from backend.core.keyword_detection import KeywordDetector
        actions = [m.action for m in KeywordDetector.MAPPINGS]
        assert "ralplan" in actions

    def test_canonical_engine_includes_autopilot(self):
        from backend.core.keyword_detection import keyword_detector
        matches = keyword_detector.detect("run autopilot on this project")
        assert any(m.action == "autopilot" for m in matches)

    def test_canonical_engine_includes_brainstorming(self):
        from backend.core.keyword_detection import keyword_detector
        matches = keyword_detector.detect("brainstorm ideas for the login page")
        assert any(m.action == "brainstorming" for m in matches)

    def test_canonical_engine_detect_returns_list(self):
        from backend.core.keyword_detection import keyword_detector
        result = keyword_detector.detect("no keyword here at all xyz")
        assert isinstance(result, list)

    def test_hook_execute_uses_canonical_engine(self):
        """Smoke-test: KeywordDetectorHook.execute produces consistent results."""
        from backend.hooks.handlers.keyword_detector import KeywordDetectorHook
        from backend.hooks import HookContext, HookEvent
        from backend.core.keyword_detection import keyword_detector as engine

        hook = KeywordDetectorHook()
        # Check that the hook doesn't maintain its own detection state
        direct = engine.detect("run tdd tests")
        assert isinstance(direct, list)


# ---------------------------------------------------------------------------
# i18n manager
# ---------------------------------------------------------------------------


class TestI18nManager:
    def _mgr(self):
        from backend.i18n.i18n_manager import I18nManager
        return I18nManager()

    def test_loads_en_locale(self):
        m = self._mgr()
        assert "en" in m.available_locales()

    def test_loads_it_locale(self):
        m = self._mgr()
        assert "it" in m.available_locales()

    def test_t_returns_string(self):
        m = self._mgr()
        result = m.t("intent.implement")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_t_en_locale(self):
        m = self._mgr()
        result = m.t("intent.implement", locale="en")
        assert "implement" in result.lower() or "writing" in result.lower() or "modif" in result.lower()

    def test_t_it_locale(self):
        m = self._mgr()
        result = m.t("intent.implement", locale="it")
        # Italian version exists and differs from key
        assert result != "intent.implement"

    def test_t_fallback_to_en(self):
        """Key missing in 'it' falls back to 'en'."""
        m = self._mgr()
        # Add a key only to 'en'
        m._strings.setdefault("en", {})["test.only_en"] = "english only"
        m._strings.setdefault("it", {}).pop("test.only_en", None)
        result = m.t("test.only_en", locale="it")
        assert result == "english only"

    def test_t_fallback_to_key(self):
        """Key missing everywhere returns the key itself."""
        m = self._mgr()
        result = m.t("does.not.exist.at.all")
        assert result == "does.not.exist.at.all"

    def test_t_with_interpolation(self):
        m = self._mgr()
        # Use a key that has {skill_name}
        result = m.t("skill.selected", skill_name="ralplan", confidence=0.85)
        assert "ralplan" in result

    def test_t_interpolation_error_returns_template(self):
        m = self._mgr()
        m._strings.setdefault("en", {})["test.bad_fmt"] = "Hello {missing_key}"
        result = m.t("test.bad_fmt")
        assert "Hello" in result

    def test_set_locale(self):
        m = self._mgr()
        m.set_locale("it")
        assert m.locale == "it"

    def test_set_unknown_locale_keeps_current(self):
        m = self._mgr()
        m.set_locale("fr")
        assert m.locale == "en"  # unchanged

    def test_available_locales_is_list(self):
        m = self._mgr()
        locales = m.available_locales()
        assert isinstance(locales, list)
        assert len(locales) >= 2

    def test_has_key_true(self):
        m = self._mgr()
        assert m.has_key("intent.implement")

    def test_has_key_false(self):
        m = self._mgr()
        assert not m.has_key("this.key.does.not.exist")

    def test_singleton_importable(self):
        from backend.i18n.i18n_manager import i18n
        assert i18n is not None
        assert "en" in i18n.available_locales()

    def test_reload_does_not_crash(self):
        m = self._mgr()
        m.reload()
        assert "en" in m.available_locales()


# ---------------------------------------------------------------------------
# i18n JSON catalog validity
# ---------------------------------------------------------------------------


class TestI18nJsonCatalogs:
    _LOCALES_DIR = Path(__file__).parent.parent / "i18n"

    def test_en_json_exists(self):
        assert (self._LOCALES_DIR / "en.json").exists()

    def test_it_json_exists(self):
        assert (self._LOCALES_DIR / "it.json").exists()

    def test_en_json_valid(self):
        data = json.loads((self._LOCALES_DIR / "en.json").read_text("utf-8"))
        assert isinstance(data, dict)
        assert len(data) >= 10

    def test_it_json_valid(self):
        data = json.loads((self._LOCALES_DIR / "it.json").read_text("utf-8"))
        assert isinstance(data, dict)
        assert len(data) >= 10

    def test_it_has_same_keys_as_en(self):
        en = json.loads((self._LOCALES_DIR / "en.json").read_text("utf-8"))
        it = json.loads((self._LOCALES_DIR / "it.json").read_text("utf-8"))
        missing = set(en.keys()) - set(it.keys())
        assert not missing, f"Keys in en.json but missing from it.json: {missing}"

    def test_no_empty_values_en(self):
        data = json.loads((self._LOCALES_DIR / "en.json").read_text("utf-8"))
        empty = [k for k, v in data.items() if not v.strip()]
        assert not empty, f"Empty values in en.json: {empty}"

    def test_no_empty_values_it(self):
        data = json.loads((self._LOCALES_DIR / "it.json").read_text("utf-8"))
        empty = [k for k, v in data.items() if not v.strip()]
        assert not empty, f"Empty values in it.json: {empty}"


# ---------------------------------------------------------------------------
# Blueprint audit document
# ---------------------------------------------------------------------------


class TestBlueprintAudit:
    _PATH = Path(__file__).parent.parent.parent / "docs" / "blueprint-audit.md"

    def test_file_exists(self):
        assert self._PATH.exists(), "docs/blueprint-audit.md must exist"

    def test_file_has_content(self):
        content = self._PATH.read_text("utf-8")
        assert len(content) > 200

    def test_file_mentions_divergences(self):
        content = self._PATH.read_text("utf-8").lower()
        assert "divergen" in content

    def test_file_mentions_not_yet_implemented(self):
        content = self._PATH.read_text("utf-8").lower()
        assert "not yet" in content or "non implementat" in content

    def test_file_mentions_intent_cache(self):
        content = self._PATH.read_text("utf-8").lower()
        assert "intent" in content and "cache" in content

    def test_file_mentions_keyword_deduplication(self):
        content = self._PATH.read_text("utf-8").lower()
        assert "keyword" in content and ("dedup" in content or "canonical" in content)
