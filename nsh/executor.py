"""Safe shell command execution and output capture."""

from __future__ import annotations

import re
import subprocess
from enum import Enum
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Dangerous-pattern detection
# ---------------------------------------------------------------------------


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DangerMatch(NamedTuple):
    description: str
    severity: Severity


_DANGEROUS_PATTERNS: list[tuple[str, DangerMatch]] = [
    # ---- critical: irreversible system damage ----
    (r"\brm\s+-rf\s+/", DangerMatch("rm -rf / — 递归删除根目录", Severity.CRITICAL)),
    (r"\brm\s+-rf\s+~", DangerMatch("rm -rf ~ — 递归删除用户主目录", Severity.CRITICAL)),
    (r"\brm\s+-rf\s+[$]HOME", DangerMatch("rm -rf $HOME — 递归删除用户主目录", Severity.CRITICAL)),
    (r">\s*/dev/sd[a-z]", DangerMatch("覆盖块设备 /dev/sdX", Severity.CRITICAL)),
    (r"\bdd\s+of=/dev/sd[a-z]", DangerMatch("dd 写入块设备 /dev/sdX", Severity.CRITICAL)),
    (r"\bdd\s+if=", DangerMatch("dd — 原始磁盘操作", Severity.CRITICAL)),
    (r"\bmkfs\.", DangerMatch("mkfs — 格式化文件系统", Severity.CRITICAL)),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", DangerMatch("fork bomb — 系统资源耗尽", Severity.CRITICAL)),
    (r"\b\(\)\s*\{\s*[^}]*\|\s*[^}]*&\s*\}", DangerMatch("疑似 fork bomb", Severity.CRITICAL)),
    (r":\s*>\s*\.?\s*&\s*", DangerMatch("fork bomb 变体 (: > . &)", Severity.CRITICAL)),
    (r"\b>?\s*/etc/passwd\b", DangerMatch("覆写 /etc/passwd — 破坏用户账户", Severity.CRITICAL)),
    (r"\b>?\s*/etc/shadow\b", DangerMatch("覆写 /etc/shadow — 破坏用户密码库", Severity.CRITICAL)),
    (r"\b>?\s*/etc/sudoers\b", DangerMatch("覆写 /etc/sudoers — 破坏 sudo 配置", Severity.CRITICAL)),

    # ---- high: significant risk ----
    (r"\brm\s+-rf\s+\*", DangerMatch("rm -rf * — 递归删除当前目录所有内容", Severity.HIGH)),
    (r"\brm\s+-rf\s+\.\b", DangerMatch("rm -rf . — 递归删除当前目录", Severity.HIGH)),
    (r"\bfdisk\b", DangerMatch("fdisk — 分区表操作", Severity.HIGH)),
    (r"\bchown\s+-R\s+\S+\s+/", DangerMatch("chown -R 作用于根目录", Severity.HIGH)),
    (r"\b>?\s*/boot/", DangerMatch("覆写 /boot — 可能损坏引导程序", Severity.HIGH)),
    (r"\bwget\b.*\|\s*(ba)?sh\b", DangerMatch("wget 管道到 shell — 远程代码执行", Severity.HIGH)),
    (r"\bcurl\b.*\|\s*(ba)?sh\b", DangerMatch("curl 管道到 shell — 远程代码执行", Severity.HIGH)),
    (r"\bchmod\s+777\s+/", DangerMatch("chmod 777 作用于根目录", Severity.HIGH)),
    (r"\beval\b.*\$", DangerMatch("eval 使用变量展开 — 潜在代码注入", Severity.HIGH)),

    # ---- medium: disruptive but recoverable ----
    (r"\bshutdown\b", DangerMatch("shutdown — 关闭系统", Severity.MEDIUM)),
    (r"\breboot\b", DangerMatch("reboot — 重启系统", Severity.MEDIUM)),
    (r"\bhalt\b", DangerMatch("halt — 停止系统", Severity.MEDIUM)),
    (r"\bpoweroff\b", DangerMatch("poweroff — 关闭电源", Severity.MEDIUM)),
    (r"\bkill\s+-9\s+-1\b", DangerMatch("kill -9 -1 — 杀死所有进程", Severity.MEDIUM)),
    (r"\bkillall\b", DangerMatch("killall — 按名称杀死所有匹配进程", Severity.MEDIUM)),
    (r"\bpkill\s+-9\b", DangerMatch("pkill -9 — 强制杀死匹配进程", Severity.MEDIUM)),
    (r"\bmv\s+.*\s+/dev/null\b", DangerMatch("mv 到 /dev/null — 数据丢失", Severity.MEDIUM)),
    (r"\bhistory\s+-c\b", DangerMatch("history -c — 清除命令历史", Severity.MEDIUM)),

    # ---- low: noisy but worth flagging ----
    (r"\brm\s+-rf\s+/tmp\b", DangerMatch("rm -rf /tmp — 删除临时文件", Severity.LOW)),
    (r"\bdpkg\s+--purge\b", DangerMatch("dpkg --purge — 彻底移除软件包及配置", Severity.LOW)),
    (r"\bapt\s+autoremove\b", DangerMatch("apt autoremove — 自动移除不再需要的包", Severity.LOW)),
    (r"\bdocker\s+system\s+prune\b", DangerMatch("docker system prune — 清理 Docker 数据", Severity.LOW)),
]


def is_dangerous(command: str) -> list[str]:
    """Check a command against known dangerous patterns.

    Returns a list of human-readable descriptions for every dangerous
    pattern found.  An empty list means the command looks safe.

    This is purely advisory — it does *not* block execution.
    """
    matched: list[str] = []
    for pattern, dm in _DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            matched.append(dm.description)
    return matched


def assess_danger(command: str) -> list[DangerMatch]:
    """Return full DangerMatch tuples (severity + description) for a command.

    Use this when you need to differentiate between critical and low-risk
    dangerous patterns.
    """
    matched: list[DangerMatch] = []
    for pattern, dm in _DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            matched.append(dm)
    return matched


def max_severity(command: str) -> Severity | None:
    """Return the highest severity level found in *command*, or None."""
    best: Severity | None = None
    rank = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
    for _, dm in _DANGEROUS_PATTERNS:
        if re.search(_, command, re.IGNORECASE):
            if best is None or rank[dm.severity] > rank[best]:
                best = dm.severity
    return best


# ---------------------------------------------------------------------------
# Markdown / whitespace cleanup
# ---------------------------------------------------------------------------

_MARKDOWN_FENCE_RE = re.compile(
    r"^\s*```(?:bash|sh|shell|zsh)?\s*\n(.*?)\n\s*```\s*$",
    re.DOTALL,
)


def sanitize_command(command: str) -> str:
    """Strip markdown code fences and leading / trailing whitespace.

    Handles both ```bash ... ``` and bare ``` ... ``` fences.  Also
    collapses a trailing newline inside the fence so the resulting
    command string is ready to execute.
    """
    stripped = command.strip()
    m = _MARKDOWN_FENCE_RE.match(stripped)
    if m:
        return m.group(1).strip()
    return stripped


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def run(
    command: str,
    *,
    cwd: str | None = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """Execute a shell command and capture its output.

    Parameters
    ----------
    command:
        The shell command string to execute.
    cwd:
        Working directory for the child process.  ``None`` inherits
        the current process working directory.
    timeout:
        Maximum wall-clock seconds before the process is killed.

    Returns
    -------
    (returncode, stdout, stderr)
        ``stdout`` and ``stderr`` are decoded with the system default
        encoding, using "replace" for undecodable bytes.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return (
            -1,
            exc.stdout.decode(errors="replace") if exc.stdout else "",
            exc.stderr.decode(errors="replace") if exc.stderr else "",
        )
    return (
        result.returncode,
        result.stdout.decode(errors="replace"),
        result.stderr.decode(errors="replace"),
    )


def run_interactive(command: str) -> int:
    """Run a command interactively with the terminal connected.

    stdin, stdout, and stderr are inherited from the parent process
    so that pagers, editors, and interactive prompts work correctly.

    Returns the exit code of the command.
    """
    result = subprocess.run(
        command,
        shell=True,
    )
    return result.returncode
