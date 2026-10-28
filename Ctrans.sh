#!/bin/bash

# ==============================================================================
# CTRANS - Convenient Translation & Quick AI Assistant
# Glassmorphism Quick Translator & Universal AI Assistant
# Powered by Groq Cloud & Google Gemini Hybrid + Modular Slash Command Router
# ==============================================================================

set -o pipefail

# Config directory and file paths
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/ctrans"
if [ ! -d "$CONFIG_DIR" ] && [ -d "${XDG_CONFIG_HOME:-$HOME/.config}/rofi-translate" ]; then
    CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/rofi-translate"
fi
CONFIG_FILE="$CONFIG_DIR/config.env"
USER_COMMANDS_DIR="$CONFIG_DIR/commands"
DEFAULT_COMMANDS_DIR="$SCRIPT_DIR/commands"

# Configuration load order:
# 1. ~/.config/ctrans/config.env (or ~/.config/rofi-translate/config.env)
# 2. config.env in script directory
# 3. .env in script directory
if [ -f "$CONFIG_FILE" ]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
elif [ -f "$SCRIPT_DIR/config.env" ]; then
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/config.env"
elif [ -f "$SCRIPT_DIR/.env" ]; then
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env"
fi

# Decoupled system prompt file for default translation mode
# Priority:
# 1. $PROMPT_FILE (if explicitly defined in config)
# 2. prompt.md in script directory
# 3. prompt.md in config directory
# 4. prompt.txt fallback
if [ -z "$PROMPT_FILE" ] || [ ! -f "$PROMPT_FILE" ]; then
    if [ -f "$SCRIPT_DIR/prompt.md" ]; then
        PROMPT_FILE="$SCRIPT_DIR/prompt.md"
    elif [ -f "$CONFIG_DIR/prompt.md" ]; then
        PROMPT_FILE="$CONFIG_DIR/prompt.md"
    elif [ -f "$SCRIPT_DIR/prompt.txt" ]; then
        PROMPT_FILE="$SCRIPT_DIR/prompt.txt"
    elif [ -f "$CONFIG_DIR/prompt.txt" ]; then
        PROMPT_FILE="$CONFIG_DIR/prompt.txt"
    fi
fi

# API configuration: Groq primary, Gemini fallback
GROQ_API_KEY="${GROQ_API_KEY:-}"
GROQ_MODEL="${GROQ_MODEL:-openai/gpt-oss-120b}"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash-lite}"

# ==============================================================================
# GLASSMORPHISM THEMES (Center & Fit-to-content)
# ==============================================================================

# 1. Input theme: 600px floating window, non-blocking
THEME_INPUT="
  * { background-color: transparent; text-color: #ffffff; font: \"Inter Display 14\"; }
  window {
    location: center;
    anchor: center;
    width: 600px;
    background-color: transparent;
    border: 0px;
    padding: 0px;
    margin: 0px;
  }
  mainbox {
    width: 600px;
    children: [ inputbar ];
    background-color: rgba(28, 28, 30, 0.95);
    border: 1px;
    border-color: rgba(255, 255, 255, 0.18);
    border-radius: 20px;
    padding: 10px 14px;
  }
  inputbar {
    children: [ entry ];
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 12px 18px;
  }
  entry {
    placeholder: \"Type words to translate or /help for commands...\";
    placeholder-color: rgba(255, 255, 255, 0.35);
    text-color: #ffffff;
    vertical-align: 0.5;
  }
"

# 2. Loading theme: Matches input bar geometry, non-blocking
THEME_LOADING="
  * { background-color: transparent; text-color: #ffffff; font: \"Inter Display 14\"; }
  window {
    location: center;
    anchor: center;
    width: 600px;
    background-color: transparent;
    border: 0px;
    padding: 0px;
    margin: 0px;
  }
  mainbox {
    width: 600px;
    children: [ inputbar ];
    background-color: rgba(28, 28, 30, 0.95);
    border: 1px;
    border-color: rgba(255, 255, 255, 0.18);
    border-radius: 20px;
    padding: 10px 14px;
  }
  inputbar {
    children: [ prompt ];
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 12px 18px;
  }
  prompt {
    text-color: #818cf8;
    horizontal-align: 0.0;
    vertical-align: 0.5;
    font: \"Inter Display 14\";
  }
"

# 3. Result theme: Fullscreen backdrop, click-outside to dismiss, auto-fit height
THEME_RESULT="
  * { background-color: transparent; text-color: #ffffff; font: \"Inter 13\"; }
  window {
    fullscreen: true;
    background-color: rgba(10, 10, 10, 0.45);
    children: [ dummy-top, h-box, dummy-bottom ];
  }
  dummy-top, dummy-bottom { expand: true; }
  h-box { orientation: horizontal; children: [ dummy-left, mainbox, dummy-right ]; expand: false; }
  dummy-left, dummy-right { expand: true; }
  mainbox {
    width: 760px;
    expand: false;
    children: [ message ];
    background-color: rgba(28, 28, 30, 0.95);
    border: 1px;
    border-color: rgba(255, 255, 255, 0.18);
    border-radius: 20px;
    padding: 24px 32px;
  }
  message {
    padding: 0px;
    margin: 0px;
    border: 0px;
  }
  textbox {
    text-color: #f3f4f6;
    padding: 0px;
    margin: 0px;
    wrap: true;
    font: \"Inter 13\";
    vertical-align: 0.0;
    markup: false;
  }
"

# Auto soft-wrap formatter to ensure accurate Rofi height calculation
format_display_text() {
    local text="$1"
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "
import sys, textwrap
text = sys.stdin.read()
lines = []
for line in text.splitlines():
    if not line.strip():
        lines.append('')
        continue
    indent_len = len(line) - len(line.lstrip(' \t'))
    prefix = line[:indent_len]
    stripped = line[indent_len:]
    sub_indent = prefix + ('  ' if stripped.startswith('•') else '')
    lines.extend(textwrap.wrap(line, width=78, subsequent_indent=sub_indent))
print('\n'.join(lines))
" <<< "$text"
    elif command -v fold >/dev/null 2>&1; then
        echo "$text" | fold -s -w 78
    else
        echo "$text"
    fi
}

# Wayland mouse flags: click backdrop outside card to cancel/close
ROFI_MOUSE_FLAGS=(
  -hover-select
  -me-select-entry ''
  -me-accept-entry '!MousePrimary'
  -kb-cancel 'Escape,MousePrimary'
)

# Clean up background loading process on exit
LOADING_PID=""
trap 'if [ -n "$LOADING_PID" ]; then kill "$LOADING_PID" 2>/dev/null; fi; exit 0' INT TERM EXIT

# Dynamically generate command catalog for /help and error displays
generate_help_text() {
    local -A seen_cmds
    local -a cmd_names

    for dir in "$USER_COMMANDS_DIR" "$DEFAULT_COMMANDS_DIR"; do
        if [ -d "$dir" ]; then
            for f in "$dir"/*.md; do
                [ -f "$f" ] || continue
                local cmd
                cmd="$(basename "$f" .md)"
                if [ -z "${seen_cmds[$cmd]:-}" ]; then
                    seen_cmds["$cmd"]="$f"
                    cmd_names+=("$cmd")
                fi
            done
        fi
    done

    echo "💡 Ctrans Quick AI Assistant - Commands and Usage Guide"
    echo ""
    echo "Available Commands:"
    printf "  • /%-20s %s\n" "help" "Show available commands and usage guide"

    for cmd in "${cmd_names[@]}"; do
        local file="${seen_cmds[$cmd]}"
        local first_line
        first_line=$(awk 'NF{print;exit}' "$file" 2>/dev/null)
        local sig="/$cmd <input>"
        local desc="Custom command prompt"
        if [[ "$first_line" =~ ^#[[:space:]]*(\/[a-zA-Z0-9_-]+([[:space:]]+<[^>]+>)?)[[:space:]]*[-:][[:space:]]*(.*)$ ]]; then
            sig="${BASH_REMATCH[1]}"
            desc="${BASH_REMATCH[3]}"
        elif [ -n "$first_line" ]; then
            desc="$(echo "$first_line" | sed -E 's/^#[[:space:]]*//')"
        fi
        printf "  • /%-20s %s\n" "${sig#/}" "$desc"
    done

    echo ""
    echo "Quick Tips:"
    echo "  • Type any word or sentence without '/' for instant translation (EN <-> VI)."
    echo "  • Press Enter, Esc, or click outside this card to dismiss."
}

# ==============================================================================
# STEP 1: USER INPUT
# ==============================================================================
INPUT=$(rofi -dmenu -theme-str "$THEME_INPUT" -kb-cancel 'Escape')
if [ -z "$INPUT" ]; then exit 0; fi

# Limit input to 500 characters
INPUT="${INPUT:0:500}"

# ==============================================================================
# STEP 2: PROGRAMMATIC BASH ROUTER
# ==============================================================================
COMMAND=""
PAYLOAD=""
LOADING_MSG="Analyzing..."
SYSTEM_PROMPT=""

# 2.1. Built-in /help command or solitary '/'
if [ "$INPUT" = "/" ] || [ "$INPUT" = "/help" ] || [[ "$INPUT" =~ ^/help([[:space:]].*)?$ ]]; then
    HELP_TEXT=$(generate_help_text)
    DISPLAY_TEXT=$(format_display_text "$HELP_TEXT")
    rofi -dmenu -mesg "$DISPLAY_TEXT"$'\n' -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
    exit 0
fi

# 2.2. Match slash command pattern: require whitespace before arguments to avoid matching file paths (e.g. /etc/hosts)
if [[ "$INPUT" =~ ^/([a-zA-Z0-9_-]+)([[:space:]]+(.*))?$ ]]; then
    COMMAND="${BASH_REMATCH[1]}"
    PAYLOAD="${BASH_REMATCH[3]}"

    # Locate modular command file (User config -> Repo defaults)
    COMMAND_FILE=""
    if [ -f "$USER_COMMANDS_DIR/${COMMAND}.md" ]; then
        COMMAND_FILE="$USER_COMMANDS_DIR/${COMMAND}.md"
    elif [ -f "$DEFAULT_COMMANDS_DIR/${COMMAND}.md" ]; then
        COMMAND_FILE="$DEFAULT_COMMANDS_DIR/${COMMAND}.md"
    fi

    # Unknown command entered: show error dialog without consuming API tokens
    if [ -z "$COMMAND_FILE" ]; then
        UNKNOWN_ERR="⚠️ Unknown Command: /$COMMAND

$(generate_help_text)"
        DISPLAY_TEXT=$(format_display_text "$UNKNOWN_ERR")
        rofi -dmenu -mesg "$DISPLAY_TEXT"$'\n' -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
        exit 1
    fi

    # Validate argument payload
    if [ -z "$PAYLOAD" ]; then
        FIRST_LINE=$(awk 'NF{print;exit}' "$COMMAND_FILE" 2>/dev/null)
        USAGE_HINT="/$COMMAND <input>"
        CMD_DESC="Custom command prompt"
        if [[ "$FIRST_LINE" =~ ^#[[:space:]]*(\/[a-zA-Z0-9_-]+([[:space:]]+<[^>]+>)?)[[:space:]]*[-:][[:space:]]*(.*)$ ]]; then
            USAGE_HINT="${BASH_REMATCH[1]}"
            CMD_DESC="${BASH_REMATCH[3]}"
        elif [ -n "$FIRST_LINE" ]; then
            CMD_DESC="$(echo "$FIRST_LINE" | sed -E 's/^#[[:space:]]*//')"
        fi

        EXAMPLE_HINT=$(grep -m 1 -i '^[[:space:]]*<!--[[:space:]]*Example:[[:space:]]*' "$COMMAND_FILE" 2>/dev/null | sed -E 's/^[[:space:]]*<!--[[:space:]]*[Ee]xample:[[:space:]]*//; s/[[:space:]]*-->$//')
        [ -z "$EXAMPLE_HINT" ] && EXAMPLE_HINT="$USAGE_HINT ..."

        MISSING_ARG_MSG="⚠️ Missing argument for /$COMMAND

Usage:
  $USAGE_HINT

Description:
  $CMD_DESC

Example:
  $EXAMPLE_HINT"
        DISPLAY_TEXT=$(format_display_text "$MISSING_ARG_MSG")
        rofi -dmenu -mesg "$DISPLAY_TEXT"$'\n' -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
        exit 1
    fi

    # Command matched & validated: load prompt and configure dynamic loading label
    SYSTEM_PROMPT=$(cat "$COMMAND_FILE")
    case "$COMMAND" in
        ask) LOADING_MSG="Asking AI [/ask]..." ;;
        eva) LOADING_MSG="Evaluating [/eva]..." ;;
        *)   LOADING_MSG="Processing [/$COMMAND]..." ;;
    esac
else
    # 2.3. Default translation mode (No slash command)
    if [ -f "$PROMPT_FILE" ]; then
        SYSTEM_PROMPT=$(cat "$PROMPT_FILE")
    else
        SYSTEM_PROMPT="You are an expert bilingual translator. If the input is English, translate to Vietnamese; if Vietnamese, translate to English."
    fi
    LOADING_MSG="Analyzing..."
fi

# ==============================================================================
# API KEY VALIDATION (Executed only when AI request is required)
# ==============================================================================
if [ -z "$GROQ_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
    NO_KEY_MSG="⚠️ API Key not configured!

Please configure GROQ_API_KEY or GEMINI_API_KEY in:
$CONFIG_FILE
(See .env.example for template)"
    DISPLAY_TEXT=$(format_display_text "$NO_KEY_MSG")
    rofi -dmenu -mesg "$DISPLAY_TEXT"$'\n' -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
    exit 1
fi

# ==============================================================================
# STEP 3: LOADING INDICATOR
# ==============================================================================
rofi -dmenu -p "$LOADING_MSG" -theme-str "$THEME_LOADING" </dev/null &
LOADING_PID=$!

# ==============================================================================
# STEP 4: API REQUEST (Groq Primary -> Gemini Fallback)
# ==============================================================================
# Prepare user message content based on mode
if [ -n "$COMMAND" ]; then
    USER_PROMPT_CONTENT="$PAYLOAD"
else
    USER_PROMPT_CONTENT="Translate: $INPUT"
fi

RESPONSE_TEXT=""
ERROR_MSG=""

# 4.1. Primary: Groq API (~0.5s - 0.8s)
if [ -n "$GROQ_API_KEY" ]; then
    GROQ_PAYLOAD=$(jq -n \
      --arg model "$GROQ_MODEL" \
      --arg sys "$SYSTEM_PROMPT" \
      --arg input "$USER_PROMPT_CONTENT" \
      '{
        model: $model,
        messages: [
          {role: "system", content: $sys},
          {role: "user", content: $input}
        ],
        temperature: 0.2,
        max_tokens: 1000
      }')

    GROQ_RESPONSE=$(curl -4 -s --connect-timeout 5 --max-time 15 -X POST "https://api.groq.com/openai/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $GROQ_API_KEY" \
      -d "$GROQ_PAYLOAD")

    RESPONSE_TEXT=$(echo "$GROQ_RESPONSE" | jq -r '.choices[0].message.content // empty')
    if [ -z "$RESPONSE_TEXT" ]; then
        ERROR_MSG=$(echo "$GROQ_RESPONSE" | jq -r '.error.message // empty')
    fi
fi

# 4.2. Fallback: Google Gemini API
if [ -z "$RESPONSE_TEXT" ] && [ -n "$GEMINI_API_KEY" ]; then
    if [ -n "$COMMAND" ]; then
        GEMINI_TEXT_PAYLOAD="$SYSTEM_PROMPT

User Query:
$USER_PROMPT_CONTENT"
    else
        GEMINI_TEXT_PAYLOAD="$SYSTEM_PROMPT

Translate: $INPUT"
    fi

    GEMINI_PAYLOAD=$(jq -n \
      --arg fulltext "$GEMINI_TEXT_PAYLOAD" \
      '{contents: [{parts: [{text: $fulltext}]}]}')

    GEMINI_RESPONSE=$(curl -4 -s --connect-timeout 8 --max-time 45 -X POST "https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=$GEMINI_API_KEY" \
      -H 'Content-Type: application/json' \
      -d "$GEMINI_PAYLOAD")

    RESPONSE_TEXT=$(echo "$GEMINI_RESPONSE" | jq -r '.candidates[0].content.parts[0].text // empty')
    if [ -z "$RESPONSE_TEXT" ]; then
        GEMINI_ERR=$(echo "$GEMINI_RESPONSE" | jq -r '.error.message // empty')
        if [ -n "$GEMINI_ERR" ]; then
            ERROR_MSG="$GEMINI_ERR"
        fi
    fi
fi

# Stop loading indicator
if [ -n "$LOADING_PID" ]; then
    kill "$LOADING_PID" 2>/dev/null
    wait "$LOADING_PID" 2>/dev/null
    LOADING_PID=""
fi

# ==============================================================================
# STEP 5: DISPLAY RESULT
# ==============================================================================
if [ -n "$RESPONSE_TEXT" ]; then
    # Format soft-wrap for accurate Rofi height calculation
    DISPLAY_TEXT=$(format_display_text "$RESPONSE_TEXT")
    rofi -dmenu -mesg "$DISPLAY_TEXT"$'\n' -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
else
    if [ -z "$ERROR_MSG" ]; then
        ERROR_MSG="No response received from AI API (timeout or unstable network)."
    fi

    if [ -n "$COMMAND" ]; then
        ERROR_TITLE="❌ Execution Error [/$COMMAND]"
    else
        ERROR_TITLE="❌ Translation Error"
    fi

    ERROR_DISPLAY="$ERROR_TITLE:

$ERROR_MSG"
    DISPLAY_TEXT=$(format_display_text "$ERROR_DISPLAY")
    rofi -dmenu -mesg "$DISPLAY_TEXT"$'\n' -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
fi
