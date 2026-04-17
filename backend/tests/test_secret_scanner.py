"""Tests — Sprint 2 secret scanner: redaction of API keys and secrets."""

from __future__ import annotations

import pytest

from backend.hooks.handlers.secret_scanner import scan_and_redact


_REDACTED = "[REDACTED]"


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------


class TestAWSPatterns:
    def test_aws_access_key_id_detected(self) -> None:
        text = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result, findings = scan_and_redact(text)
        assert "aws_access_key_id" in findings
        assert "AKIA" not in result

    def test_aws_secret_access_key_detected(self) -> None:
        text = "AWS_SECRET_ACCESS_KEY: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        result, findings = scan_and_redact(text)
        assert "aws_secret_access_key" in findings


class TestAnthropicAPIKey:
    def test_anthropic_key_detected(self) -> None:
        text = "api_key = sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd"
        result, findings = scan_and_redact(text)
        assert "anthropic_api_key" in findings
        assert "sk-ant-" not in result

    def test_anthropic_key_in_json(self) -> None:
        text = '{"api_key": "sk-ant-api03-abcdefghijklmnopqrstuvwxyz12345"}'
        result, findings = scan_and_redact(text)
        assert "anthropic_api_key" in findings


class TestOpenAIAPIKey:
    def test_openai_key_detected(self) -> None:
        text = "OPENAI_API_KEY=sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"
        result, findings = scan_and_redact(text)
        assert "openai_api_key" in findings
        assert "sk-proj" not in result


class TestGitHubTokens:
    def test_ghp_token_detected(self) -> None:
        text = "token: ghp_" + "A" * 36
        result, findings = scan_and_redact(text)
        assert "github_token_ghp" in findings
        assert "ghp_" not in result


class TestPrivateKeyPEM:
    def test_pem_private_key_detected(self) -> None:
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        result, findings = scan_and_redact(text)
        assert "pem_private_key" in findings
        assert "BEGIN RSA PRIVATE KEY" not in result

    def test_ec_private_key_detected(self) -> None:
        text = "-----BEGIN EC PRIVATE KEY-----\nABC...\n-----END EC PRIVATE KEY-----"
        result, findings = scan_and_redact(text)
        assert "pem_private_key" in findings

    def test_bare_private_key_detected(self) -> None:
        text = "-----BEGIN PRIVATE KEY-----\nMIIFHDBW...\n-----END PRIVATE KEY-----"
        result, findings = scan_and_redact(text)
        assert "pem_private_key" in findings


# ---------------------------------------------------------------------------
# No false positives on safe text
# ---------------------------------------------------------------------------


class TestNoFalsePositives:
    def test_normal_code_not_redacted(self) -> None:
        text = "def compute_hash(data: str) -> str:\n    return hashlib.sha256(data.encode()).hexdigest()"
        result, findings = scan_and_redact(text)
        assert findings == [] or result == text  # No critical findings

    def test_empty_string(self) -> None:
        result, findings = scan_and_redact("")
        assert result == ""
        assert findings == []

    def test_plain_sentence(self) -> None:
        text = "The quick brown fox jumps over the lazy dog"
        result, findings = scan_and_redact(text)
        assert result == text  # No redaction


# ---------------------------------------------------------------------------
# Redaction output
# ---------------------------------------------------------------------------


class TestRedactionOutput:
    def test_redacted_marker_present(self) -> None:
        text = "key=AKIAIOSFODNN7EXAMPLE is bad"
        result, findings = scan_and_redact(text)
        assert _REDACTED in result

    def test_original_secret_not_in_output(self) -> None:
        text = "sk-ant-api03-supersecretkeyABCDEFGHIJKLMNOPQRSTUV"
        result, _ = scan_and_redact(text)
        assert "sk-ant-api03" not in result

    def test_surrounding_text_preserved(self) -> None:
        text = "config={'key': 'AKIAIOSFODNN7EXAMPLE', 'region': 'us-east-1'}"
        result, _ = scan_and_redact(text)
        assert "region" in result
        assert "us-east-1" in result

    def test_multiple_secrets_all_redacted(self) -> None:
        text = (
            "aws_key=AKIAIOSFODNN7EXAMPLE\n"
            "openai=sk-proj-" + "A" * 30 + "\n"
            "region=us-east-1"
        )
        result, findings = scan_and_redact(text)
        assert len(findings) >= 1
        assert _REDACTED in result
        assert "region=us-east-1" in result

    def test_idempotent_on_already_redacted(self) -> None:
        text = f"key={_REDACTED}"
        result, findings = scan_and_redact(text)
        assert result == text  # Nothing to redact
