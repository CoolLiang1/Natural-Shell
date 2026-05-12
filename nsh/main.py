"""nsh CLI — natural language shell command translation and execution."""

from __future__ import annotations

import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table
from rich import box

# ---------------------------------------------------------------------------
# Force UTF-8 on Windows consoles so Chinese text renders correctly.
# Must happen before any output is written.
# ---------------------------------------------------------------------------
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from nsh import __version__
from nsh.config import Config, config_app
from nsh.executor import Severity, is_dangerous, max_severity, run, run_interactive
from nsh.session import Session
from nsh.translator import translate

cli = typer.Typer(
    name="nsh",
    help="自然语言 → Ubuntu shell 命令",
    rich_markup_mode="rich",
    invoke_without_command=True,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
cli.add_typer(config_app, name="config")

console = Console(force_terminal=True, legacy_windows=False)
_config = Config()
_session = Session()
_COMMAND_NAMES = {"ask", "config", "session", "run-cmd"}
_APP_OPTIONS = {"--help", "-h", "--version", "-V"}
_ROOT_FLAGS = {"--yes", "-y", "--no-session", "--interactive", "-i"}
_ROOT_VALUE_OPTIONS = {"--model", "-m"}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _render_command_panel(command: str, *, danger: list[str] | None = None) -> Panel:
    """Render a command inside a Rich Panel with syntax highlighting.

    When *danger* is non-empty, the panel gets a red border and the
    dangerous patterns are listed inside the panel body.
    """
    syntax = Syntax(command, "bash", theme="monokai", line_numbers=False)
    title = "生成的命令"
    border_style = "green"
    body_parts: list = [syntax]

    if danger:
        title = "⚠ 危险命令"
        border_style = "red"
        body_parts.append(Text(""))
        body_parts.append(Text("🚫 检测到以下危险模式：", style="bold red"))
        for d in danger:
            body_parts.append(Text(f"  • {d}", style="red"))

    return Panel(
        "\n".join(str(p) for p in body_parts) if len(body_parts) > 1 else body_parts[0],
        title=title,
        border_style=border_style,
        box=box.HEAVY,
        padding=(1, 2),
    )


def _show_and_confirm(command: str) -> bool:
    """Display command in panel, run safety check, ask for confirmation.

    Returns True if the user wants to proceed.
    """
    danger = is_dangerous(command)
    panel = _render_command_panel(command, danger=danger)
    console.print(panel)

    if danger:
        console.print(
            Panel(
                "此命令包含危险操作，执行可能导致数据丢失或系统损坏。\n"
                "请仔细检查命令内容后再确认执行。",
                title="⚠ 安全警告",
                border_style="red",
                padding=(1, 2),
            )
        )
        confirmed = typer.confirm("\n确定要执行此危险命令吗？")
        if not confirmed:
            console.print("[yellow]已取消执行。[/yellow]")
            return False
        # Double confirm for critical-severity patterns
        severity = max_severity(command)
        if severity is Severity.CRITICAL:
            console.print(
                "[bold red]⚠ 此命令可能造成不可逆的系统损坏！[/bold red]"
            )
            double = typer.confirm("再次确认：你真的要执行吗？")
            if not double:
                console.print("[yellow]已取消执行。[/yellow]")
                return False
    else:
        confirmed = typer.confirm("\n是否执行此命令？")
        if not confirmed:
            console.print("[yellow]已取消。[/yellow]")
            return False
    return True


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def _first_prompt_arg(args: list[str]) -> str | None:
    """Return the first non-option argument meant for the root run command."""
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in _ROOT_VALUE_OPTIONS:
            index += 2
            continue
        if arg in _ROOT_FLAGS:
            index += 1
            continue
        if arg.startswith("-"):
            return None
        return arg
    return None


def _should_run_from_root(args: list[str]) -> bool:
    """Decide whether argv targets the default natural-language runner."""
    if any(arg in _APP_OPTIONS for arg in args):
        return False
    first_prompt_arg = _first_prompt_arg(args)
    if first_prompt_arg is None:
        return False
    return first_prompt_arg not in _COMMAND_NAMES


def _run_from_root_args(args: list[str]) -> None:
    """Parse root options and execute the natural-language prompt."""
    model: str | None = None
    yes = False
    no_session = False
    interactive = False
    prompt_parts: list[str] = []

    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ("--model", "-m"):
            try:
                model = args[index + 1]
            except IndexError:
                console.print("[red]--model 需要一个值。[/red]")
                raise typer.Exit(code=2)
            index += 2
            continue
        if arg in ("--yes", "-y"):
            yes = True
            index += 1
            continue
        if arg == "--no-session":
            no_session = True
            index += 1
            continue
        if arg in ("--interactive", "-i"):
            interactive = True
            index += 1
            continue

        prompt_parts.append(arg)
        index += 1

    prompt = " ".join(prompt_parts).strip()
    if not prompt:
        cli()
        return

    _translate_and_run(
        prompt,
        model=model,
        yes=yes,
        no_session=no_session,
        interactive=interactive,
    )


def _translate_and_run(
    prompt: str,
    *,
    model: str | None = None,
    yes: bool = False,
    no_session: bool = False,
    interactive: bool = False,
) -> None:
    """Translate natural language into a shell command and execute it."""
    cfg = Config()
    if model:
        cfg.set("model", model)

    sess = None if no_session else _session

    with console.status("[bold green]正在生成命令…[/bold green]"):
        try:
            command = translate(prompt, session=sess, config=cfg)
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

    if yes or cfg.get("auto_execute"):
        console.print(_render_command_panel(command, danger=is_dangerous(command)))
        console.print("[yellow]自动执行模式已开启，跳过确认。[/yellow]")
    elif not _show_and_confirm(command):
        raise typer.Exit(code=0)

    if sess:
        sess.add(prompt, command)

    if interactive:
        console.print("[bold]执行中（交互模式）…[/bold]")
        run_interactive(command)
    else:
        console.print("[bold]执行中…[/bold]")
        returncode, stdout, stderr = run(command)

        if stdout:
            console.print(stdout)
        if stderr:
            console.print(f"[red]{stderr}[/red]")

        if returncode == 0:
            console.print(f"\n[green]✓ 执行成功 (exit code: {returncode})[/green]")
        else:
            console.print(f"\n[red]✗ 执行失败 (exit code: {returncode})[/red]")


@cli.command()
def ask(
    prompt: Annotated[
        str, typer.Argument(help="自然语言描述，例如 '列出所有本周修改的 PDF 文件'")
    ],
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="覆盖配置中的 model"),
    ] = None,
    no_session: Annotated[
        bool,
        typer.Option("--no-session", help="本次不注入会话上下文"),
    ] = False,
) -> None:
    """将自然语言翻译为 shell 命令（仅翻译，不执行）。"""
    cfg = Config()
    if model:
        cfg.set("model", model)

    sess = None if no_session else _session

    with console.status("[bold green]正在生成命令…[/bold green]"):
        try:
            command = translate(prompt, session=sess, config=cfg)
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

    panel = _render_command_panel(command, danger=is_dangerous(command))
    console.print(panel)

    # Record in session
    if sess:
        sess.add(prompt, command)


@cli.command(hidden=True)
def run_cmd(
    prompt: Annotated[
        str, typer.Argument(help="自然语言描述，例如 '安装 nginx 并启动'")
    ],
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="覆盖配置中的 model"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="跳过确认，直接执行"),
    ] = False,
    no_session: Annotated[
        bool,
        typer.Option("--no-session", help="本次不注入会话上下文"),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option("--interactive", "-i", help="交互模式执行（保留终端控制权）"),
    ] = False,
) -> None:
    """将自然语言翻译为 shell 命令，确认后执行。"""
    _translate_and_run(
        prompt,
        model=model,
        yes=yes,
        no_session=no_session,
        interactive=interactive,
    )


@cli.command()
def session(
    clear: Annotated[
        bool,
        typer.Option("--clear", "-c", help="清除所有会话历史"),
    ] = False,
) -> None:
    """查看或管理会话历史（上下文记忆）。"""
    if clear:
        _session.clear()
        console.print("[green]会话历史已清除。[/green]")
        return

    entries = _session._entries
    if not entries:
        console.print("[dim]会话历史为空。[/dim]")
        return

    table = Table(title="会话历史", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("自然语言", style="cyan")
    table.add_column("命令", style="green")
    table.add_column("时间", style="dim")

    for i, entry in enumerate(entries, 1):
        table.add_row(str(i), entry["nl"], entry["command"], entry["ts"])

    console.print(table)


@cli.callback()
def callback(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option("--version", "-V", help="显示版本号"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="覆盖配置中的 model"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="跳过确认，直接执行"),
    ] = False,
    no_session: Annotated[
        bool,
        typer.Option("--no-session", help="本次不注入会话上下文"),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option("--interactive", "-i", help="交互模式执行（保留终端控制权）"),
    ] = False,
) -> None:
    if version:
        console.print(f"nsh v{__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        if ctx.args:
            _translate_and_run(
                " ".join(ctx.args),
                model=model,
                yes=yes,
                no_session=no_session,
                interactive=interactive,
            )
            raise typer.Exit()
        click_ctx = ctx.parent or ctx
        typer.echo(click_ctx.get_help())
        raise typer.Exit()


def main() -> None:
    """Console script entry point."""
    args = sys.argv[1:]
    if _should_run_from_root(args):
        try:
            _run_from_root_args(args)
        except typer.Exit as exc:
            raise SystemExit(exc.exit_code)
        return
    cli()


def app() -> None:
    """Backward-compatible entry point for existing console scripts."""
    main()


if __name__ == "__main__":
    main()
