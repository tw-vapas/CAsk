#!/bin/bash

# ==============================================================================
# Installer for Ctrans (Convenient Translation & Quick AI Assistant)
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
BIN_TARGET="$HOME/.local/bin/ctrans"
BIN_TARGET_ALIAS="$HOME/.local/bin/Ctrans"
BIN_TARGET_LEGACY="$HOME/.local/bin/ctrans-legacy"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/ctrans"
CONFIG_FILE="$CONFIG_DIR/config.env"
PROMPT_TARGET="$CONFIG_DIR/prompt.md"
COMMANDS_DIR="$CONFIG_DIR/commands"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/ctrans.desktop"

echo "✨ Installing Ctrans (Convenient Translation & Quick AI Assistant)..."

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

# 2. Setup configuration directory and files
echo "📁 Setting up configuration..."
mkdir -p "$CONFIG_DIR"
mkdir -p "$COMMANDS_DIR"

if [ ! -f "$CONFIG_FILE" ]; then
    cp "$SCRIPT_DIR/.env.example" "$CONFIG_FILE"
    chmod 600 "$CONFIG_FILE"
    echo "  ✓ Created config at $CONFIG_FILE"
    echo "  👉 Please edit $CONFIG_FILE and configure your Groq or Gemini API Key!"
else
    echo "  ✓ Existing configuration found at $CONFIG_FILE"
fi

if [ -f "$SCRIPT_DIR/prompt.md" ]; then
    ln -sf "$SCRIPT_DIR/prompt.md" "$PROMPT_TARGET"
    echo "  ✓ Linked customizable prompt at $PROMPT_TARGET"
elif [ -f "$SCRIPT_DIR/prompt.txt" ]; then
    ln -sf "$SCRIPT_DIR/prompt.txt" "$PROMPT_TARGET"
    echo "  ✓ Linked customizable prompt at $PROMPT_TARGET"
fi

if [ -d "$SCRIPT_DIR/commands" ]; then
    # Clean up broken/dangling symlinks from deleted or renamed commands
    find "$COMMANDS_DIR" -xtype l -delete 2>/dev/null || true

    for cmd_file in "$SCRIPT_DIR/commands"/*.md; do
        [ -f "$cmd_file" ] || continue
        cmd_name="$(basename "$cmd_file")"
        ln -sf "$cmd_file" "$COMMANDS_DIR/$cmd_name"
    done
    echo "  ✓ Linked modular command prompts in $COMMANDS_DIR"
fi

# 3. Create symlinks in ~/.local/bin
mkdir -p "$HOME/.local/bin"
chmod +x "$SCRIPT_DIR/ctrans.py"

# Clean up legacy link if present
if [ -L "$BIN_TARGET_LEGACY" ] || [ -f "$BIN_TARGET_LEGACY" ]; then
    rm -f "$BIN_TARGET_LEGACY"
fi

ln -sf "$SCRIPT_DIR/ctrans.py" "$BIN_TARGET"
ln -sf "$SCRIPT_DIR/ctrans.py" "$BIN_TARGET_ALIAS"
echo "  ✓ Linked executable: $BIN_TARGET and $BIN_TARGET_ALIAS"

# 4. Create Desktop Entry for global shortcut binding
mkdir -p "$DESKTOP_DIR"
cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=Ctrans
GenericName=Convenient Translation & AI Assistant
Comment=Quick AI Assistant with Native Qt6 Glassmorphism HUD
Exec=$BIN_TARGET
Icon=accessories-dictionary
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=false
EOF
chmod +x "$DESKTOP_FILE"
echo "  ✓ Created desktop entry at $DESKTOP_FILE"

# 5. Optional KWin window effects for KDE Plasma
if command -v kwriteconfig6 >/dev/null 2>&1 && [ "$XDG_CURRENT_DESKTOP" = "KDE" ]; then
    echo "🎨 Configuring KDE KWin window effects (Fade instead of Scale)..."
    kwriteconfig6 --file kwinrc --group Plugins --key scaleEnabled false 2>/dev/null || true
    kwriteconfig6 --file kwinrc --group Plugins --key fadeEnabled true 2>/dev/null || true
    if command -v qdbus-qt6 >/dev/null 2>&1; then
        qdbus-qt6 org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect "scale" 2>/dev/null || true
        qdbus-qt6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect "fade" 2>/dev/null || true
        qdbus-qt6 org.kde.KWin /KWin org.kde.KWin.reconfigure 2>/dev/null || true
    fi
fi

echo ""
echo "🎉 Installation complete!"
echo "Run 'ctrans' from terminal or trigger it via your configured keyboard shortcut."
