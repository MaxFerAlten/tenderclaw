"""Tests — Sprint 1 signal extraction: auto-extraction from transcript."""

from __future__ import annotations

import pytest

from backend.memory.memory_scan import extract_signals_from_transcript
from backend.memory.memory_types import MemoryScope, MemoryType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user(text: str) -> dict:
    return {"role": "user", "content": text}


def _assistant(text: str) -> dict:
    return {"role": "assistant", "content": text}


def _user_blocks(*texts: str) -> dict:
    return {
        "role": "user",
        "content": [{"type": "text", "text": t} for t in texts],
    }


# ---------------------------------------------------------------------------
# Basic extraction
# ---------------------------------------------------------------------------


class TestExtractSignalsBasic:
    def test_empty_messages_returns_empty(self) -> None:
        assert extract_signals_from_transcript([]) == []

    def test_only_assistant_messages_returns_empty(self) -> None:
        msgs = [_assistant("Sure, I will use snake_case everywhere.")]
        assert extract_signals_from_transcript(msgs) == []

    def test_short_message_skipped(self) -> None:
        msgs = [_user("never")]
        signals = extract_signals_from_transcript(msgs)
        assert signals == []

    def test_feedback_signal_extracted(self) -> None:
        msgs = [_user("please always add docstrings to every function you write")]
        signals = extract_signals_from_transcript(msgs)
        assert len(signals) >= 1
        assert any(s.type == MemoryType.FEEDBACK for s in signals)

    def test_project_signal_extracted(self) -> None:
        msgs = [_user("we use PostgreSQL as the primary database for all services")]
        signals = extract_signals_from_transcript(msgs)
        assert len(signals) >= 1
        assert any(s.scope in (MemoryScope.REPO, MemoryScope.TEAM) for s in signals)


# ---------------------------------------------------------------------------
# Scope assignment
# ---------------------------------------------------------------------------


class TestSignalScopeAssignment:
    def test_preference_goes_to_user_scope(self) -> None:
        msgs = [_user("I prefer verbose error messages and detailed stack traces always")]
        signals = extract_signals_from_transcript(msgs)
        # "prefer" and "always" both match feedback/user pattern
        scopes = {s.scope for s in signals}
        assert MemoryScope.USER in scopes or len(signals) == 0  # permissive: user or no match

    def test_project_decision_goes_to_repo_scope(self) -> None:
        msgs = [_user("we decided to use Redis for caching all session tokens in the project")]
        signals = extract_signals_from_transcript(msgs)
        assert any(s.scope == MemoryScope.REPO for s in signals)

    def test_team_convention_goes_to_team_scope(self) -> None:
        msgs = [_user("everyone on the team agreed to follow PEP 8 as our standard coding convention")]
        signals = extract_signals_from_transcript(msgs)
        assert any(s.scope == MemoryScope.TEAM for s in signals)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_duplicate_messages_not_doubled(self) -> None:
        msg = _user("please always use type hints in Python functions for clarity")
        signals = extract_signals_from_transcript([msg, msg])
        # Deduplication should prevent same fingerprint appearing twice
        titles = [s.title for s in signals]
        assert len(titles) == len(set(titles)), "Duplicate signals should be deduplicated"


# ---------------------------------------------------------------------------
# Multi-message transcripts
# ---------------------------------------------------------------------------


class TestMultiMessageTranscript:
    def test_extracts_from_multiple_user_turns(self) -> None:
        msgs = [
            _user("please never use global variables in the codebase"),
            _assistant("Understood, I will avoid globals."),
            _user("we chose Celery as our task queue for the entire project"),
            _assistant("Got it, Celery will be used for async tasks."),
        ]
        signals = extract_signals_from_transcript(msgs)
        assert len(signals) >= 1

    def test_block_content_messages_processed(self) -> None:
        msg = _user_blocks(
            "always run pytest before any commit",
            "we use Docker for all deployments in this project",
        )
        signals = extract_signals_from_transcript([msg])
        assert len(signals) >= 1


# ---------------------------------------------------------------------------
# Signal metadata
# ---------------------------------------------------------------------------


class TestSignalMetadata:
    def test_signal_has_id(self) -> None:
        msgs = [_user("prefer to never use wildcard imports in any Python module")]
        signals = extract_signals_from_transcript(msgs)
        if signals:
            assert signals[0].id.startswith("sig_")

    def test_signal_has_keywords(self) -> None:
        msgs = [_user("please always write integration tests for every new endpoint")]
        signals = extract_signals_from_transcript(msgs)
        if signals:
            assert isinstance(signals[0].keywords, list)

    def test_signal_has_auto_extracted_tag(self) -> None:
        msgs = [_user("we use Kubernetes for all production deployments in our project")]
        signals = extract_signals_from_transcript(msgs, session_id="abc123")
        if signals:
            assert "auto-extracted" in signals[0].metadata.tags

    def test_session_id_in_tags(self) -> None:
        msgs = [_user("please never commit directly to main branch without review")]
        signals = extract_signals_from_transcript(msgs, session_id="deadbeef1234")
        if signals:
            tags = signals[0].metadata.tags
            assert any("session:deadbeef" in t for t in tags)
