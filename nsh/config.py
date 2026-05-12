"""Local configuration management — API keys and user preferences.

Configuration is stored as JSON in ``~/.config/nsh/config.json``.
The ``ANTHROPIC_API_KEY`` environment variable always takes priority over
the config file for the api_key.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import typer

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".config" / "nsh"
CONFIG_PATH = CONFIG_DIR / "config.json"

# Schema defaults — used to fill in any missing keys on load.
DEFAULTS: dict[str, Any] = {
    "api_key": None,
    "base_url": "https://api.deepseek.com/anthropic",
    "model": "deepseek-v4-flash",
    "max_tokens": 500,
    "auto_execute": False,
    "safe_mode": True,
    "language": "zh",
}


# ---------------------------------------------------------------------------
# Config class
# ---------------------------------------------------------------------------


class Config:
    """Manages the local configuration file."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self._path = path
        self._dir = path.parent

    # ---- I/O helpers -------------------------------------------------------

    def _ensure_dir(self) -> None:
        """Create the config directory if it doesn't already exist."""
        self._dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        """Read ``config.json`` and return a dict with defaults filled in."""
        config: dict[str, Any] = dict(DEFAULTS)
        try:
            raw_text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return config
        try:
            raw_data: dict[str, Any] = json.loads(raw_text)
        except json.JSONDecodeError:
            return config
        config.update(raw_data)
        return config

    def save(self, data: dict[str, Any]) -> None:
        """Write *data* to ``config.json`` atomically.

        Writes to a temp file in the same directory first, then renames,
        to avoid corrupting the config on write failure.
        """
        self._ensure_dir()
        content = json.dumps(data, ensure_ascii=False, indent=2)
        # Atomic write: temp file → rename
        fd, tmp_path_str = tempfile.mkstemp(
            dir=str(self._dir), prefix=".config-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp_path_str, self._path)
        except BaseException:
            # Clean up the temp file on any failure
            Path(tmp_path_str).unlink(missing_ok=True)
            raise

    # ---- Single-key access -------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return a single config value."""
        data = self.load()
        return data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a single config value and persist immediately."""
        data = self.load()
        data[key] = value
        self.save(data)

    # ---- Convenience properties --------------------------------------------

    @property
    def api_key(self) -> str | None:
        """Return the API key, respecting env-var priority.

        ``ANTHROPIC_API_KEY`` from the environment takes priority over the
        value stored in the config file.  Returns ``None`` when neither
        is set.
        """
        env_key = os.environ.get("ANTHROPIC_API_KEY")
        if env_key:
            return env_key
        file_key = self.get("api_key")
        return file_key if file_key else None


# Module-level singleton ------------------------------------------------
_config = Config()


# -----------------------------------------------------------------------
# Typer sub-app for ``nsh config …``
# -----------------------------------------------------------------------

config_app = typer.Typer(name="config", help="Manage nsh configuration.")


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Set a configuration value.

    Examples::

        nsh config set model claude-sonnet-4-6
        nsh config set auto_execute true
    """
    # Coerce common bool / int strings so JSON types stay correct.
    coerced: Any = _coerce_value(value)
    _config.set(key, coerced)
    typer.echo(f"config.{key} = {_display_value(key, coerced)}")


@config_app.command("get")
def config_get(
    key: str | None = typer.Argument(
        None,
        help="Configuration key name. Omit to show all values.",
    ),
) -> None:
    """Get a configuration value, or all values if KEY is omitted.

    The api_key value is never printed — ``***`` is displayed instead.
    """
    if key:
        value = _config.get(key)
        typer.echo(f"{key} = {_display_value(key, value)}")
    else:
        data = _config.load()
        for k, v in data.items():
            typer.echo(f"{k} = {_display_value(k, v)}")


@config_app.command("path")
def config_path() -> None:
    """Print the path to the configuration file."""
    typer.echo(str(CONFIG_PATH))


@config_app.command("reset")
def config_reset(force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt.")) -> None:
    """Reset all configuration values to their defaults."""
    if not force:
        typer.echo(f"This will overwrite {CONFIG_PATH} with default values.")
        confirmed = typer.confirm("Are you sure?")
        if not confirmed:
            raise typer.Abort()
    _config.save(dict(DEFAULTS))
    typer.echo("Configuration reset to defaults.")


# ---- Helpers ----------------------------------------------------------


def _coerce_value(raw: str) -> Any:
    """Try to parse *raw* as a bool or int; fall back to str."""
    lower = raw.lower()
    if lower in ("true", "yes", "1"):
        return True
    if lower in ("false", "no", "0"):
        return False
    try:
        return int(raw)
    except ValueError:
        return raw


def _display_value(key: str, value: Any) -> str:
    """Return the string representation of *value*, redacting api_key."""
    if key == "api_key":
        return "***"
    return json.dumps(value, ensure_ascii=False)
