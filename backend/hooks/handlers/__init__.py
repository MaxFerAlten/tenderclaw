"""TenderClaw hook handlers package."""

from backend.hooks.handlers.keyword_detector import (
    CommentCheckerHook,
    ContextInjectorHook,
    KeywordDetectorHook,
    RalphLoopHook,
    SessionRecoveryHook,
)
from backend.hooks.handlers.secret_scanner import (
    scan_and_redact,
    secret_scanner_assistant_after,
    secret_scanner_tool_after,
)

__all__ = [
    "KeywordDetectorHook",
    "RalphLoopHook",
    "ContextInjectorHook",
    "SessionRecoveryHook",
    "CommentCheckerHook",
    "scan_and_redact",
    "secret_scanner_tool_after",
    "secret_scanner_assistant_after",
]
