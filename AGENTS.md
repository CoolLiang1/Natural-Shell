# AGENTS.md — nsh (Natural Shell)

## Overview

**nsh** is a CLI tool that translates natural language into Ubuntu shell
commands.  You describe what you want to do in plain English (or Chinese)
and nsh uses the Anthropic API to generate the corresponding command,
optionally executing it after confirmation.

## Tech stack

- **Language:** Python 3.13+
- **CLI framework:** [Typer](https://typer.tiangolo.com/) with Rich for
  formatted output
- **AI:** [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
  (`anthropic` package) targeting Codex
- **Shell execution:** `subprocess` with safety-pattern detection
  (no third-party shell wrapper)

## Architecture

```
nsh/
├── __init__.py       # package init
├── main.py           # Typer app entry point, CLI commands (nsh ask, nsh run, nsh config)
├── config.py         # ~/.config/nsh/config.json management (API key, preferences)
├── translator.py     # Anthropic API call: NL → command translation
└── executor.py       # command safety check, sanitize, execute, capture

~/.config/nsh/
└── config.json       # user configuration (created automatically on first run)
```

## Key design decisions

- **Never auto-execute by default.** Always show the generated command
  and ask for confirmation before running it, unless the user passes
  `--yes` / configures `auto_execute: true`.
- **Safety first.** `executor.py` maintains a list of dangerous command
  patterns (e.g., `rm -rf /`, `mkfs`, fork bombs) and warns loudly before
  execution.
- **API key from env first.** `ANTHROPIC_API_KEY` environment variable
  takes priority over the value in `~/.config/nsh/config.json`.
- **Chinese-first UX.** Default UI language is Chinese; configurable via
  `config.language`.

## Commands (planned)

| Command | Description |
|---|---|
| `nsh ask "list all PDFs modified this week"` | Translate NL → command, print it |
| `nsh run "list all PDFs modified this week"` | Translate → show → confirm → execute |
| `nsh config set model Codex-sonnet-4-6` | Set configuration values |
| `nsh config get` | Show current configuration |
| `nsh config path` | Print path to config file |
| `nsh config reset` | Reset config to defaults |

## Coding conventions

- Type-annotate all public functions (strict mode not required).
- Use `from __future__ import annotations` in every module.
- Single-line docstrings for functions; triple-quoted module docstrings.
- Chinese strings use `"` quotes; English strings use `"` quotes.
- No comments that describe *what* code does — only *why* when non-obvious.
