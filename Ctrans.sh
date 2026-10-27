#!/bin/bash

# ==============================================================================
# CTRANS - Convenient Translation (Wayland / Fedora / KDE Compatible)
# Glassmorphism Quick Translator powered by Groq Cloud & Google Gemini Hybrid
# ==============================================================================

set -o pipefail

# Config directory and file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/ctrans"
if [ ! -d "$CONFIG_DIR" ] && [ -d "${XDG_CONFIG_HOME:-$HOME/.config}/rofi-translate" ]; then
    CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/rofi-translate"
fi
CONFIG_FILE="$CONFIG_DIR/config.env"

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

# Decoupled system prompt file
PROMPT_FILE="$CONFIG_DIR/prompt.txt"
if [ ! -f "$PROMPT_FILE" ]; then
    PROMPT_FILE="$SCRIPT_DIR/prompt.txt"
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
    placeholder: \"Type your words...\";
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

# Clean up loading process on exit
trap 'kill $LOADING_PID 2>/dev/null; exit 0' INT TERM EXIT

# ==============================================================================
# API KEY VALIDATION
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
# STEP 1: USER INPUT
# ==============================================================================
INPUT=$(rofi -dmenu -theme-str "$THEME_INPUT" -kb-cancel 'Escape')
if [ -z "$INPUT" ]; then exit 0; fi

# Limit input to 500 characters
INPUT="${INPUT:0:500}"

# ==============================================================================
# STEP 2: LOADING INDICATOR
# ==============================================================================
rofi -dmenu -p "Analyzing..." -theme-str "$THEME_LOADING" </dev/null &
LOADING_PID=$!

# ==============================================================================
# STEP 3: API REQUEST (Groq Primary -> Gemini Fallback)
# ==============================================================================
# Load system prompt from file
if [ -f "$PROMPT_FILE" ]; then
    SYSTEM_PROMPT=$(cat "$PROMPT_FILE")
else
    SYSTEM_PROMPT="You are a fluent translator. If the input is English, translate to Vietnamese; if Vietnamese, translate to English."
fi

TRANSLATION=""
ERROR_MSG=""

# 3.1. Primary: Groq API (~0.5s - 0.8s)
if [ -n "$GROQ_API_KEY" ]; then
    GROQ_PAYLOAD=$(jq -n \
      --arg model "$GROQ_MODEL" \
      --arg sys "$SYSTEM_PROMPT" \
      --arg input "$INPUT" \
      '{
        model: $model,
        messages: [
          {role: "system", content: $sys},
          {role: "user", content: ("Translate: " + $input)}
        ],
        temperature: 0.2,
        max_tokens: 1000
      }')

    GROQ_RESPONSE=$(curl -4 -s --connect-timeout 5 --max-time 15 -X POST "https://api.groq.com/openai/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $GROQ_API_KEY" \
      -d "$GROQ_PAYLOAD")

    TRANSLATION=$(echo "$GROQ_RESPONSE" | jq -r '.choices[0].message.content // empty')
    if [ -z "$TRANSLATION" ]; then
        ERROR_MSG=$(echo "$GROQ_RESPONSE" | jq -r '.error.message // empty')
    fi
fi

# 3.2. Fallback: Google Gemini API
if [ -z "$TRANSLATION" ] && [ -n "$GEMINI_API_KEY" ]; then
    GEMINI_PAYLOAD=$(jq -n \
      --arg prompt "$SYSTEM_PROMPT" \
      --arg input "$INPUT" \
      '{contents: [{parts: [{text: ($prompt + "\n\nTranslate: " + $input)}]}]}')

    GEMINI_RESPONSE=$(curl -4 -s --connect-timeout 8 --max-time 45 -X POST "https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=$GEMINI_API_KEY" \
      -H 'Content-Type: application/json' \
      -d "$GEMINI_PAYLOAD")

    TRANSLATION=$(echo "$GEMINI_RESPONSE" | jq -r '.candidates[0].content.parts[0].text // empty')
    if [ -z "$TRANSLATION" ]; then
        GEMINI_ERR=$(echo "$GEMINI_RESPONSE" | jq -r '.error.message // empty')
        if [ -n "$GEMINI_ERR" ]; then
            ERROR_MSG="$GEMINI_ERR"
        fi
    fi
fi

# Stop loading indicator
kill $LOADING_PID 2>/dev/null
wait $LOADING_PID 2>/dev/null

# ==============================================================================
# STEP 4: DISPLAY RESULT
# ==============================================================================
if [ -n "$TRANSLATION" ]; then
    # Format soft-wrap for accurate Rofi height calculation
    DISPLAY_TEXT=$(format_display_text "$TRANSLATION")
    rofi -dmenu -mesg "$DISPLAY_TEXT"$'\n' -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
else
    if [ -z "$ERROR_MSG" ]; then
        ERROR_MSG="No response received from AI API (timeout or unstable network)."
    fi

    ERROR_DISPLAY="❌ Translation Error:

$ERROR_MSG"
    DISPLAY_TEXT=$(format_display_text "$ERROR_DISPLAY")
    rofi -dmenu -mesg "$DISPLAY_TEXT"$'\n' -theme-str "$THEME_RESULT" "${ROFI_MOUSE_FLAGS[@]}" </dev/null >/dev/null 2>&1
fi
