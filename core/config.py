"""Configuration loader for CAsk.

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
    max_tokens: int = 4096
    prompt_file: Optional[Path] = None
    config_dir: Path = Path.home() / ".config" / "cask"
    script_dir: Path = Path(__file__).resolve().parent.parent
    user_execution_dir: Path = Path.home() / ".config" / "cask" / "execution"
    user_commands_dir: Path = Path.home() / ".config" / "cask" / "execution" / "commands"
    default_execution_dir: Path = Path(__file__).resolve().parent.parent / "execution"
    default_commands_dir: Path = Path(__file__).resolve().parent.parent / "execution" / "commands"

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
    """Resolve configuration directory for CAsk."""
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    base_dir = Path(xdg_config) if xdg_config else Path.home() / ".config"
    return base_dir / "cask"


def is_placeholder_key(val: str) -> bool:
    """Return True if an API key string is empty or matches known placeholder templates."""
    cleaned = val.strip().strip("'\"").lower()
    if not cleaned:
        return True
    placeholders = {
        "your_groq_api_key_here",
        "your_gemini_api_key_here",
        "your_api_key_here",
        "aizasyyourgeminiapikeyhere",
        "gsk_your_groq_api_key_here",
    }
    return (
        cleaned in placeholders
        or cleaned.startswith("your_")
        or cleaned.endswith("_here")
        or "your_api_key" in cleaned
    )


def load_config(script_dir: Optional[Path] = None) -> Config:
    """Load and merge configuration from config files and system environment."""
    if script_dir is None:
        script_dir = Path(__file__).resolve().parent.parent

    config_dir = resolve_config_dir()
    user_execution_dir = config_dir / "execution"
    user_commands_dir = user_execution_dir / "commands"
    default_execution_dir = script_dir / "execution"
    default_commands_dir = default_execution_dir / "commands"

    # Merge configuration with priority:
    # 1. Base: script_dir / .env
    # 2. Repo: script_dir / config.env
    # 3. User: config_dir / config.env (ignores placeholder template values)
    # 4. System Environment variables
    file_vars: dict[str, str] = {}
    for candidate in [
        script_dir / ".env",
        script_dir / "config.env",
        config_dir / "config.env",
    ]:
        if candidate.is_file():
            parsed = parse_env_file(candidate)
            for k, v in parsed.items():
                if "KEY" in k:
                    if not is_placeholder_key(v):
                        file_vars[k] = v
                elif v:
                    file_vars[k] = v

    # Environment variables override file definitions if set and non-placeholder
    def get_val(key: str, default: str = "") -> str:
        env_val = os.getenv(key)
        if env_val is not None:
            if "KEY" in key and is_placeholder_key(env_val):
                pass
            else:
                return env_val
        val = file_vars.get(key, default)
        if "KEY" in key and is_placeholder_key(val):
            return ""
        return val

    groq_api_key = get_val("GROQ_API_KEY", "")
    groq_model = get_val("GROQ_MODEL", "openai/gpt-oss-120b")
    gemini_api_key = get_val("GEMINI_API_KEY", "")
    gemini_model = get_val("GEMINI_MODEL", "gemini-3.5-flash-lite")
    try:
        max_tokens = int(get_val("MAX_TOKENS", "4096"))
    except (ValueError, TypeError):
        max_tokens = 4096

    # Resolve default AI assistant prompt file:
    # 1. $PROMPT_FILE override (if explicitly set in config/env)
    # 2. User custom default: ~/.config/cask/execution/DEFAULT.md
    # 3. Repository default: execution/DEFAULT.md
    # 4. Fallback legacy candidates: default.md / prompt.md
    explicit_prompt = get_val("PROMPT_FILE", "")
    prompt_file: Optional[Path] = None
    if explicit_prompt:
        candidate = Path(explicit_prompt)
        if candidate.is_file():
            prompt_file = candidate

    if prompt_file is None:
        for candidate in [
            user_execution_dir / "DEFAULT.md",
            default_execution_dir / "DEFAULT.md",
            user_execution_dir / "default.md",
            default_execution_dir / "default.md",
            user_commands_dir / "DEFAULT.md",
            user_commands_dir / "default.md",
            config_dir / "commands" / "default.md",
            script_dir / "commands" / "default.md",
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
        max_tokens=max_tokens,
        prompt_file=prompt_file,
        config_dir=config_dir,
        script_dir=script_dir,
        user_execution_dir=user_execution_dir,
        user_commands_dir=user_commands_dir,
        default_execution_dir=default_execution_dir,
        default_commands_dir=default_commands_dir,
    )
