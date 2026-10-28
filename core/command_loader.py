"""Modular slash command scanner and metadata parser.

Reads command markdown files from user config and repository defaults,
extracting signatures, descriptions, examples, and prompt templates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import Config

IGNORED_COMMAND_NAMES = {"guide", "readme", "default"}

# Regex for line 1 metadata: # /<command> <arg> - <description>
META_SIG_PATTERN = re.compile(
    r"^#\s*(\/[a-zA-Z0-9_-]+(?:\s+<[^>]+>)?)\s*[-:]\s*(.*)$"
)

# Regex for example comments: <!-- Example: ... -->
EXAMPLE_PATTERN = re.compile(
    r"^\s*<!--\s*Example:\s*(.*?)\s*-->\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CommandMetadata:
    """Metadata describing a single slash command."""
    name: str
    file_path: Path
    signature: str
    description: str
    example: str
    prompt: str


class CommandCatalog:
    """Collection of loaded slash commands with catalog and help generation."""

    def __init__(self, commands: dict[str, CommandMetadata]) -> None:
        self._commands = commands

    @property
    def commands(self) -> dict[str, CommandMetadata]:
        return self._commands

    def get(self, name: str) -> Optional[CommandMetadata]:
        """Lookup command by exact name."""
        return self._commands.get(name.lower())

    def list_names(self) -> list[str]:
        """Return sorted list of available command names."""
        return sorted(self._commands.keys())

    def generate_help_text(self) -> str:
        """Format dynamic commands catalog matching established CLI output."""
        lines = [
            "Ctrans Quick AI Assistant - Commands and Usage Guide",
            "",
            "Available Commands:",
            f"  • /{ 'help':<20} Show available commands and usage guide",
        ]

        for name in sorted(self._commands.keys()):
            cmd = self._commands[name]
            sig_display = cmd.signature.lstrip("/")
            lines.append(f"  • /{sig_display:<20} {cmd.description}")

        lines.extend([
            "",
            "Quick Tips:",
            "  • Type any word or sentence without '/' for instant translation (EN <-> VI).",
            "  • Press Enter, Esc, or click outside this card to dismiss.",
        ])

        return "\n".join(lines)


def parse_command_file(file_path: Path) -> Optional[CommandMetadata]:
    """Parse a single command markdown prompt file."""
    cmd_name = file_path.stem.lower()
    if cmd_name in IGNORED_COMMAND_NAMES:
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return None

    lines = content.splitlines()
    if not lines:
        return None

    first_line = lines[0].strip()
    sig = f"/{cmd_name} <input>"
    desc = "Custom command prompt"

    match = META_SIG_PATTERN.match(first_line)
    if match:
        sig = match.group(1).strip()
        desc = match.group(2).strip()
    elif first_line.startswith("#"):
        desc = first_line.lstrip("#").strip()

    example = ""
    for line in lines[1:5]:
        ex_match = EXAMPLE_PATTERN.match(line)
        if ex_match:
            example = ex_match.group(1).strip()
            break

    if not example:
        example = f"{sig} ..."

    return CommandMetadata(
        name=cmd_name,
        file_path=file_path,
        signature=sig,
        description=desc,
        example=example,
        prompt=content,
    )


def load_commands(config: Config) -> CommandCatalog:
    """Scan command directories in priority order and construct command catalog."""
    discovered: dict[str, CommandMetadata] = {}

    search_dirs = [
        config.user_commands_dir,
        config.default_commands_dir,
    ]

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue

        for candidate in sorted(search_dir.glob("*.md")):
            name = candidate.stem.lower()
            if name in IGNORED_COMMAND_NAMES or name in discovered:
                continue

            metadata = parse_command_file(candidate)
            if metadata:
                discovered[name] = metadata

    return CommandCatalog(discovered)
