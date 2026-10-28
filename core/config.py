"""Configuration loader for Ctrans.

Loads API keys and paths following the established precedence hierarchy.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Config:
    """Application configuration parameters."""
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    prompt_file: Optional[Path] = None
    config_dir: Path = Path.home() / ".config" / "ctrans"
    script_dir: Path = Path(__file__).resolve().parent.parent
    user_commands_dir: Path = Path.home() / ".config" / "ctrans" / "commands"
    default_commands_dir: Path = Path(__file__).resolve().parent.parent / "commands"

    @property
    def has_any_api_key(self) -> bool:
        """Return True if at least one AI provider API key is present."""
        return bool(self.groq_api_key.strip() or self.gemini_api_key.strip())


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse bash-compatible key=value environment file."""
    env_vars: dict[str, str] = {}
    if not path.is_file():
        return env_vars

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return env_vars

    line_pattern = re.compile(
        r"^\s*(?:export\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$"
    )

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        match = line_pattern.match(line)
        if not match:
            continue

        key, raw_val = match.group(1), match.group(2).strip()
        if (raw_val.startswith('"') and raw_val.endswith('"')) or (
            raw_val.startswith("'") and raw_val.endswith("'")
        ):
            val = raw_val[1:-1]
        else:
            val = raw_val.split("#", 1)[0].strip()

        env_vars[key] = val

    return env_vars


def resolve_config_dir() -> Path:
    """Resolve configuration directory with fallback support."""
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    base_dir = Path(xdg_config) if xdg_config else Path.home() / ".config"
    target_dir = base_dir / "ctrans"

    if not target_dir.exists():
        legacy_dir = base_dir / "rofi-translate"
        if legacy_dir.exists():
            return legacy_dir

    return target_dir


def load_config(script_dir: Optional[Path] = None) -> Config:
    """Load and merge configuration from config files and system environment."""
    if script_dir is None:
        script_dir = Path(__file__).resolve().parent.parent

    config_dir = resolve_config_dir()
    user_commands_dir = config_dir / "commands"
    default_commands_dir = script_dir / "commands"

    # Search order:
    # 1. ~/.config/ctrans/config.env (or ~/.config/rofi-translate/config.env)
    # 2. config.env in script directory
    # 3. .env in script directory
    file_vars: dict[str, str] = {}
    for candidate in [
        config_dir / "config.env",
        script_dir / "config.env",
        script_dir / ".env",
    ]:
        if candidate.is_file():
            file_vars = parse_env_file(candidate)
            break

    # Environment variables override file definitions if set
    def get_val(key: str, default: str = "") -> str:
        env_val = os.getenv(key)
        if env_val is not None:
            return env_val
        return file_vars.get(key, default)

    groq_api_key = get_val("GROQ_API_KEY", "")
    groq_model = get_val("GROQ_MODEL", "openai/gpt-oss-120b")
    gemini_api_key = get_val("GEMINI_API_KEY", "")
    gemini_model = get_val("GEMINI_MODEL", "gemini-3.5-flash-lite")

    # Resolve default translation prompt file
    explicit_prompt = get_val("PROMPT_FILE", "")
    prompt_file: Optional[Path] = None
    if explicit_prompt:
        candidate = Path(explicit_prompt)
        if candidate.is_file():
            prompt_file = candidate

    if prompt_file is None:
        for candidate in [
            script_dir / "prompt.md",
            config_dir / "prompt.md",
            script_dir / "prompt.txt",
            config_dir / "prompt.txt",
        ]:
            if candidate.is_file():
                prompt_file = candidate
                break

    return Config(
        groq_api_key=groq_api_key,
        groq_model=groq_model,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        prompt_file=prompt_file,
        config_dir=config_dir,
        script_dir=script_dir,
        user_commands_dir=user_commands_dir,
        default_commands_dir=default_commands_dir,
    )
