"""Regression tests for the system prompt builder.

The hang bug analyzed on 2026-04-17: on Windows, the model kept emitting
POSIX commands (`ls -la`, `cat`, `grep`) because the system prompt did not
declare the host OS or available shell. cmd.exe rejected each attempt and
every retry spawned a new permission-request popup, which looks like a hang
to the user. The fix is `_platform_context()` — these tests lock in that
its output is included in `build_system_prompt()` and contains OS-specific
guidance.
"""

from __future__ import annotations

import platform
from unittest.mock import patch

from backend.core.system_prompt import _platform_context, build_system_prompt


class TestPlatformContext:
    def test_returns_platform_section_header(self):
        out = _platform_context()
        assert "## Platform" in out
        assert "- OS:" in out
        assert "- Shell:" in out
        assert "### Shell guidance" in out

    def test_includes_current_os_name(self):
        out = _platform_context()
        assert platform.system() in out

    def test_windows_guidance_warns_against_posix_tools(self):
        with patch("backend.core.system_prompt.platform.system", return_value="Windows"):
            out = _platform_context()
        # Core Windows commands mentioned
        assert "dir" in out
        assert "Get-ChildItem" in out
        assert "findstr" in out
        # Explicitly tells model NOT to use POSIX utilities
        assert "NOT" in out  # e.g. "NOT `ls`"
        assert "cmd.exe" in out

    def test_linux_guidance_mentions_posix(self):
        with patch("backend.core.system_prompt.platform.system", return_value="Linux"):
            out = _platform_context()
        assert "POSIX" in out

    def test_darwin_guidance_mentions_posix(self):
        with patch("backend.core.system_prompt.platform.system", return_value="Darwin"):
            out = _platform_context()
        assert "POSIX" in out


class TestBuildSystemPromptIncludesPlatform:
    def test_platform_section_present(self):
        prompt = build_system_prompt(working_directory=".")
        assert "## Platform" in prompt
        assert "### Shell guidance" in prompt

    def test_context_and_platform_both_present(self):
        prompt = build_system_prompt(working_directory="/tmp/example")
        assert "## Context" in prompt
        assert "## Platform" in prompt
        # Working directory still surfaces
        assert "/tmp/example" in prompt

    def test_windows_build_warns_against_ls(self):
        with patch("backend.core.system_prompt.platform.system", return_value="Windows"):
            prompt = build_system_prompt(working_directory="C:\\proj")
        assert "NOT `ls`" in prompt or "NOT `ls`." in prompt

    def test_append_still_appears_after_platform(self):
        prompt = build_system_prompt(working_directory=".", append="extra-rule-xyz")
        assert "## Platform" in prompt
        assert "extra-rule-xyz" in prompt
        # Platform comes before the Additional Instructions block
        assert prompt.index("## Platform") < prompt.index("extra-rule-xyz")
