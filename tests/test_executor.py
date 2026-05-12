from __future__ import annotations

from nsh.executor import Severity, is_dangerous, max_severity, sanitize_command


def test_sanitize_command_strips_bash_fence() -> None:
    """Strip markdown code fences from generated commands."""
    assert sanitize_command("```bash\nls -la\n```") == "ls -la"


def test_sanitize_command_preserves_plain_command() -> None:
    """Return plain commands unchanged except surrounding whitespace."""
    assert sanitize_command("  find . -name '*.py'  ") == "find . -name '*.py'"


def test_danger_detection_marks_critical_root_delete() -> None:
    """Flag destructive root deletion as critical."""
    command = "rm -rf / --no-preserve-root"

    assert "rm -rf /" in is_dangerous(command)[0]
    assert max_severity(command) is Severity.CRITICAL
