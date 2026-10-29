"""Deterministic slash command parser and router.

Parses user input, handles /help, unknown commands, argument validation,
and paths without consuming AI API tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from .command_loader import CommandCatalog
from .config import Config

DEFAULT_TRANSLATION_PROMPT = (
    "You are an expert bilingual translator. "
    "If the input is English, translate to Vietnamese; "
    "if Vietnamese, translate to English."
)

SLASH_COMMAND_PATTERN = re.compile(
    r"^/([a-zA-Z0-9_-]+)(?:\s+(.*))?$",
    re.DOTALL,
)


class RouteType(Enum):
    """Classification of routed user input."""
    EMPTY = auto()
    HELP = auto()
    COMMAND = auto()
    MISSING_ARG = auto()
    UNKNOWN_COMMAND = auto()
    DEFAULT = auto()
    TRANSLATION = DEFAULT  # Backward compatibility alias


@dataclass(frozen=True)
class RouteResult:
    """Outcome of routing user input."""
    route_type: RouteType
    command: str = ""
    payload: str = ""
    system_prompt: str = ""
    loading_label: str = "Analyzing..."
    display_text: Optional[str] = None
    user_prompt_content: str = ""


def format_missing_arg_message(cmd_name: str, signature: str, description: str, example: str) -> str:
    """Format structured missing argument message."""
    return (
        f"Missing argument for **<span style=\"color: #f9e2af;\">/{cmd_name}</span>**\n\n"
        "Usage:\n"
        f"  `{signature}`\n\n"
        "Description:\n"
        f"  {description}\n\n"
        "Example:\n"
        f"  `{example}`"
    )


def route_input(
    raw_input: str,
    catalog: CommandCatalog,
    config: Config,
) -> RouteResult:
    """Route input deterministically to the corresponding handler."""
    text = raw_input.strip()
    if not text:
        return RouteResult(
            route_type=RouteType.EMPTY,
            display_text="",
        )

    # Truncate input to 500 characters
    if len(text) > 500:
        text = text[:500]

    # Built-in /help command or solitary '/'
    if text == "/" or text == "/help" or text.startswith("/help "):
        return RouteResult(
            route_type=RouteType.HELP,
            command="help",
            display_text=catalog.generate_help_text(),
        )

    # Check for slash command pattern
    match = SLASH_COMMAND_PATTERN.match(text)
    if match:
        cmd_name = match.group(1).lower()
        payload = (match.group(2) or "").strip()

        command_meta = catalog.get(cmd_name)
        if command_meta is None:
            unknown_msg = (
                f"Unknown Command: /{cmd_name}\n\n"
                f"{catalog.generate_help_text()}"
            )
            return RouteResult(
                route_type=RouteType.UNKNOWN_COMMAND,
                command=cmd_name,
                display_text=unknown_msg,
            )

        if not payload:
            missing_msg = format_missing_arg_message(
                cmd_name=cmd_name,
                signature=command_meta.signature,
                description=command_meta.description,
                example=command_meta.example,
            )
            return RouteResult(
                route_type=RouteType.MISSING_ARG,
                command=cmd_name,
                display_text=missing_msg,
            )

        return RouteResult(
            route_type=RouteType.COMMAND,
            command=cmd_name,
            payload=payload,
            system_prompt=command_meta.prompt,
            loading_label=f"processing /{cmd_name}...",
            user_prompt_content=payload,
        )

    # Fallback to customizable default assistant mode (from commands/default.md)
    system_prompt = DEFAULT_TRANSLATION_PROMPT
    if config.prompt_file and config.prompt_file.is_file():
        try:
            loaded_prompt = config.prompt_file.read_text(encoding="utf-8").strip()
            if loaded_prompt:
                system_prompt = loaded_prompt
        except OSError:
            pass

    return RouteResult(
        route_type=RouteType.DEFAULT,
        command="",
        payload=text,
        system_prompt=system_prompt,
        loading_label="Thinking...",
        user_prompt_content=text,
    )
