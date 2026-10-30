#!/bin/bash

# ==============================================================================
# Installer for CAsk (Universal Quick AI Assistant & Command Runner)
# Native PyQt6 Glassmorphism HUD Architecture
# ==============================================================================

set -e

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
BIN_TARGET="$HOME/.local/bin/cask"
BIN_TARGET_ALIAS="$HOME/.local/bin/CAsk"
BIN_TARGET_CTRANS="$HOME/.local/bin/ctrans"
BIN_TARGET_LEGACY="$HOME/.local/bin/ctrans-legacy"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cask"
CONFIG_FILE="$CONFIG_DIR/config.env"
PROMPT_TARGET="$CONFIG_DIR/prompt.md"
EXECUTION_DIR="$CONFIG_DIR/execution"
COMMANDS_DIR="$EXECUTION_DIR/commands"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/cask.desktop"

echo "✨ Installing CAsk (Universal Quick AI Assistant & Command Runner)..."

# 1. Check Python & PyQt6 dependencies
echo "🔍 Checking dependencies..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: 'python3' is not installed. Please install it using your system package manager (e.g. sudo dnf install python3)."
    exit 1
else
    echo "  ✓ python3 found"
fi

if python3 -c "import PyQt6" >/dev/null 2>&1; then
    echo "  ✓ PyQt6 found"
else
    echo "⚠️ Warning: PyQt6 is not yet installed for Python."
    echo "   Please install it before running the GUI HUD:"
    echo "     sudo dnf install python3-pyqt6   (Fedora)"
    echo "     sudo apt install python3-pyqt6   (Ubuntu/Debian)"
    echo "     pip install PyQt6                (User install)"
fi

if python3 -c "import markdown" >/dev/null 2>&1; then
    echo "  ✓ python-markdown found"
else
    echo "  ℹ️ Installing python-markdown for GFM tables..."
    python3 -m pip install --user markdown >/dev/null 2>&1 || true
fi

# 2. Setup configuration directory and files
echo "📁 Setting up configuration..."
mkdir -p "$CONFIG_DIR"
mkdir -p "$EXECUTION_DIR"
mkdir -p "$COMMANDS_DIR"

if [ ! -f "$CONFIG_FILE" ]; then
    if [ -f "$SCRIPT_DIR/config.env" ]; then
        cp "$SCRIPT_DIR/config.env" "$CONFIG_FILE"
        chmod 600 "$CONFIG_FILE"
        echo "  ✓ Copied active config from repo to $CONFIG_FILE"
    elif [ -f "$SCRIPT_DIR/.env" ]; then
        cp "$SCRIPT_DIR/.env" "$CONFIG_FILE"
        chmod 600 "$CONFIG_FILE"
        echo "  ✓ Copied active .env from repo to $CONFIG_FILE"
    else
        cp "$SCRIPT_DIR/.env.example" "$CONFIG_FILE"
        chmod 600 "$CONFIG_FILE"
        echo "  ✓ Created config at $CONFIG_FILE"
        echo "  👉 Please edit $CONFIG_FILE and configure your Groq or Gemini API Key!"
    fi
else
    echo "  ✓ Existing configuration found at $CONFIG_FILE"
fi

# Clean up legacy prompt target if it exists
if [ -L "$PROMPT_TARGET" ] || [ -f "$PROMPT_TARGET" ]; then
    rm -f "$PROMPT_TARGET"
fi

# Setup execution templates: DEFAULT.md and GUIDE.md
# Only copy DEFAULT.md if user has not already customized it in ~/.config/cask/execution/DEFAULT.md
if [ -f "$SCRIPT_DIR/execution/DEFAULT.md" ]; then
    if [ ! -f "$EXECUTION_DIR/DEFAULT.md" ]; then
        cp "$SCRIPT_DIR/execution/DEFAULT.md" "$EXECUTION_DIR/DEFAULT.md"
        echo "  ✓ Initialized default persona at $EXECUTION_DIR/DEFAULT.md"
    else
        echo "  ✓ Preserved custom default persona at $EXECUTION_DIR/DEFAULT.md"
    fi
fi
if [ -f "$SCRIPT_DIR/execution/GUIDE.md" ]; then
    ln -sf "$SCRIPT_DIR/execution/GUIDE.md" "$EXECUTION_DIR/GUIDE.md"
fi

# Link modular command prompts inside execution/commands
if [ -d "$SCRIPT_DIR/execution/commands" ]; then
    find "$COMMANDS_DIR" -xtype l -delete 2>/dev/null || true

    for cmd_file in "$SCRIPT_DIR/execution/commands"/*.md; do
        [ -f "$cmd_file" ] || continue
        cmd_name="$(basename "$cmd_file")"
        ln -sf "$cmd_file" "$COMMANDS_DIR/$cmd_name"
    done
    echo "  ✓ Linked default persona (DEFAULT.md) and command prompts in $COMMANDS_DIR"
fi

# 3. Create symlinks in ~/.local/bin
mkdir -p "$HOME/.local/bin"
chmod +x "$SCRIPT_DIR/cask.py"

# Clean up legacy links if present
if [ -L "$BIN_TARGET_LEGACY" ] || [ -f "$BIN_TARGET_LEGACY" ]; then
    rm -f "$BIN_TARGET_LEGACY"
fi
if [ -L "$BIN_TARGET_CTRANS" ] || [ -f "$BIN_TARGET_CTRANS" ]; then
    rm -f "$BIN_TARGET_CTRANS"
fi

ln -sf "$SCRIPT_DIR/cask.py" "$BIN_TARGET"
ln -sf "$SCRIPT_DIR/cask.py" "$BIN_TARGET_ALIAS"
echo "  ✓ Linked executables: $BIN_TARGET and $BIN_TARGET_ALIAS"

# 4. Create Desktop Entry for global shortcut binding
mkdir -p "$DESKTOP_DIR"
cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=CAsk
GenericName=Universal AI Assistant & Command Runner
Comment=Quick AI Assistant with Native Qt6 Glassmorphism HUD
Exec=$BIN_TARGET
Icon=$SCRIPT_DIR/assets/logo.png
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=false
EOF
chmod +x "$DESKTOP_FILE"
echo "  ✓ Created desktop entry at $DESKTOP_FILE"

# 5. Optional KWin window effects for KDE Plasma
if command -v kwriteconfig6 >/dev/null 2>&1 && [ "$XDG_CURRENT_DESKTOP" = "KDE" ]; then
    echo "🎨 Configuring KDE KWin window effects (Background Blur & Smooth Fading)..."
    # Ensure no stale forced above rules override dynamic runtime layering
    kwriteconfig6 --file kwinrulesrc --group General --key count 0 2>/dev/null || true
    kwriteconfig6 --file kwinrulesrc --group General --key rules "" 2>/dev/null || true

    kwriteconfig6 --file kwinrc --group Plugins --key scaleEnabled false 2>/dev/null || true
    kwriteconfig6 --file kwinrc --group Plugins --key fadeEnabled true 2>/dev/null || true
    kwriteconfig6 --file kwinrc --group Plugins --key blurEnabled true 2>/dev/null || true
    if command -v qdbus-qt6 >/dev/null 2>&1; then
        qdbus-qt6 org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect "scale" 2>/dev/null || true
        qdbus-qt6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect "fade" 2>/dev/null || true
        qdbus-qt6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect "blur" 2>/dev/null || true
        qdbus-qt6 org.kde.KWin /KWin org.kde.KWin.reconfigure 2>/dev/null || true
    elif command -v busctl >/dev/null 2>&1; then
        busctl --user call org.kde.KWin /KWin org.kde.KWin reconfigure 2>/dev/null || true
    fi
fi

echo ""
echo "🎉 Installation complete!"
echo "Run 'cask' from terminal or trigger it via your configured keyboard shortcut."
