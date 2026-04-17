"""Secret Scanner Hook — blocks API keys and secrets from appearing in tool output.

This hook runs at TOOL_AFTER and MESSAGE_ASSISTANT_AFTER with the highest
priority (negative value) and BLOCK tier. If a secret pattern is detected
in tool output or assistant messages, the hook redacts the content in-place
and logs a security warning.

Patterns covered:
- AWS Access Key IDs and Secret Keys
- Anthropic API keys (sk-ant-...)
- OpenAI API keys (sk-...)
- GitHub personal access tokens (ghp_... / github_pat_...)
- Generic bearer tokens
- Private key PEM headers
- Generic high-entropy base64 secrets (≥ 32 chars of [A-Za-z0-9+/=])
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.schemas.hooks import HookAction, HookEvent, HookResult

logger = logging.getLogger("tenderclaw.hooks.secret_scanner")

# ---------------------------------------------------------------------------
# Secret patterns — ordered from most specific to most generic
# ---------------------------------------------------------------------------

_REDACTED = "[REDACTED]"

_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aws_access_key_id",     re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_access_key", re.compile(r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key[\s:=]+[A-Za-z0-9/+]{40}")),
    ("anthropic_api_key",     re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b")),
    ("openai_api_key",        re.compile(r"\bsk-(?:proj-|[A-Za-z0-9]{4}-)[A-Za-z0-9\-_]{16,}\b")),
    ("github_token_ghp",      re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("github_pat",            re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b")),
    ("generic_bearer",        re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{20,}")),
    ("pem_private_key",       re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----")),
    ("high_entropy_secret",   re.compile(r"(?<![A-Za-z0-9/+])[A-Za-z0-9/+]{32,}={0,2}(?![A-Za-z0-9/+])")),
]


def scan_and_redact(text: str) -> tuple[str, list[str]]:
    """Scan text for secrets, return redacted version and list of finding names."""
    findings: list[str] = []
    result = text
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(result):
            result = pattern.sub(_REDACTED, result)
            findings.append(name)
    return result, findings


async def secret_scanner_tool_after(event: HookEvent) -> HookResult:
    """Scan tool result content for secrets after execution."""
    data: dict[str, Any] = event.data or {}
    raw_result = data.get("result", "")

    if not isinstance(raw_result, str) or not raw_result:
        return HookResult(action=HookAction.CONTINUE)

    redacted, findings = scan_and_redact(raw_result)
    if findings:
        tool_name = data.get("tool_name", "?")
        logger.warning(
            "SECRET SCANNER: blocked %d secret pattern(s) in tool output "
            "(tool=%s, session=%s, patterns=%s)",
            len(findings),
            tool_name,
            event.session_id,
            findings,
        )
        # Mutate data in-place so downstream hooks see redacted content
        data["result"] = redacted
        return HookResult(action=HookAction.CONTINUE, data={"result": redacted})

    return HookResult(action=HookAction.CONTINUE)


async def secret_scanner_assistant_after(event: HookEvent) -> HookResult:
    """Scan assistant message content for secrets before it reaches the client."""
    data: dict[str, Any] = event.data or {}
    raw_content = data.get("content", "")

    if not isinstance(raw_content, str) or not raw_content:
        return HookResult(action=HookAction.CONTINUE)

    redacted, findings = scan_and_redact(raw_content)
    if findings:
        logger.warning(
            "SECRET SCANNER: blocked %d secret pattern(s) in assistant message "
            "(session=%s, patterns=%s)",
            len(findings),
            event.session_id,
            findings,
        )
        data["content"] = redacted
        return HookResult(action=HookAction.CONTINUE, data={"content": redacted})

    return HookResult(action=HookAction.CONTINUE)
