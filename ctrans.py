#!/usr/bin/env python3
"""Ctrans - Convenient Translation & Quick AI Assistant.

Main entry point supporting native PyQt6 Glassmorphism HUD,
CLI query execution, and seamless fallback to Bash/Rofi mode.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.command_loader import load_commands
from core.config import load_config
from core.router import RouteType, route_input

VERSION = "2.0.0"


def run_cli_mode(query: str, config, catalog) -> int:
    """Execute query in headless terminal mode and output to stdout."""
    from core.api_client import APIClient

    route = route_input(query, catalog, config)

    if route.route_type == RouteType.EMPTY:
        return 0

    if route.route_type in (
        RouteType.HELP,
        RouteType.MISSING_ARG,
        RouteType.UNKNOWN_COMMAND,
    ):
        print(route.display_text)
        return 0 if route.route_type == RouteType.HELP else 1

    if not config.has_any_api_key:
        print("Error: No API key configured in config.env or environment.")
        return 1

    print(f"[{route.loading_label}]", file=sys.stderr)
    content, err = APIClient.request(
        route.system_prompt,
        route.user_prompt_content,
        config,
    )

    if content:
        print(content)
        return 0
    else:
        print(f"Error: {err}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ctrans: Fast AI Translator & Quick Assistant",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show help and command list")
    parser.add_argument("-v", "--version", action="store_true", help="Show version information")
    parser.add_argument("--cli", action="store_true", help="Execute directly in terminal without GUI")
    parser.add_argument("query", nargs="*", help="Optional initial query or slash command")

    args = parser.parse_args()

    config = load_config(script_dir=PROJECT_ROOT)
    catalog = load_commands(config)

    if args.version:
        print(f"Ctrans v{VERSION} (Native PyQt6 HUD & Groq/Gemini Hybrid)")
        return 0

    if args.help:
        print(catalog.generate_help_text())
        print("\nCLI Options:")
        print("  -h, --help       Show this help message and exit")
        print("  -v, --version    Show version info")
        print("  --cli [QUERY]    Execute query directly in terminal without GUI")
        print("  [QUERY]          Open HUD with pre-filled query or execute directly")
        return 0

    joined_query = " ".join(args.query).strip()

    if args.cli:
        if not joined_query:
            print("Error: --cli requires a query string.")
            return 1
        return run_cli_mode(joined_query, config, catalog)

    # Check PyQt6 GUI availability
    try:
        import PyQt6
        from ui.app import run_gui

        return run_gui(
            config=config,
            catalog=catalog,
            initial_input=joined_query,
        )
    except ImportError as e:
        # Inform user and fall back to legacy Ctrans.sh
        legacy_script = PROJECT_ROOT / "Ctrans.sh"
        if legacy_script.is_file():
            print(
                "Notice: PyQt6 not detected. Falling back to legacy Rofi interface...\n"
                "To enable the native Qt6 HUD, install PyQt6:\n"
                "  sudo dnf install python3-pyqt6  (or pip install PyQt6)\n",
                file=sys.stderr,
            )
            return subprocess.call([str(legacy_script)] + sys.argv[1:])
        else:
            print(
                f"Error: PyQt6 is required but could not be imported: {e}\n"
                "Please run: sudo dnf install python3-pyqt6  (or pip install PyQt6)",
                file=sys.stderr,
            )
            return 1


if __name__ == "__main__":
    sys.exit(main())
