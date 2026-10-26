#!/bin/bash

# ==============================================================================
# Installer for Rofi AI Translator
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_TARGET="$HOME/.local/bin/rofi-translate"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/rofi-translate"
CONFIG_FILE="$CONFIG_DIR/config.env"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/rofi-translate.desktop"

echo "✨ Installing Rofi AI Translator..."

# 1. Check dependencies
echo "🔍 Checking dependencies..."
for cmd in rofi curl jq wl-copy; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "⚠️ Warning: '$cmd' is not installed. Please install it using your package manager (e.g. sudo dnf install $cmd)"
    else
        echo "  ✓ $cmd found"
    fi
done

# 2. Setup configuration directory and file
echo "📁 Setting up configuration..."
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_FILE" ]; then
    cp "$SCRIPT_DIR/.env.example" "$CONFIG_FILE"
    chmod 600 "$CONFIG_FILE"
    echo "  ✓ Created config at $CONFIG_FILE"
    echo "  👉 Please edit $CONFIG_FILE and configure your Groq or Gemini API Key!"
else
    echo "  ✓ Existing configuration found at $CONFIG_FILE"
fi

# 3. Create symlink in ~/.local/bin
mkdir -p "$HOME/.local/bin"
chmod +x "$SCRIPT_DIR/rofi_translate.sh"
ln -sf "$SCRIPT_DIR/rofi_translate.sh" "$BIN_TARGET"
echo "  ✓ Linked binary to $BIN_TARGET"

# 4. Create Desktop Entry for shortcut binding
mkdir -p "$DESKTOP_DIR"
cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=Rofi AI Translate
Comment=Quick AI Translator with Rofi and Gemini
Exec=$BIN_TARGET
Icon=accessories-dictionary
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=false
EOF
chmod +x "$DESKTOP_FILE"
echo "  ✓ Created desktop entry at $DESKTOP_FILE"

# 5. Optional KWin fade effect
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
echo "You can now run 'rofi-translate' from your terminal or bind it to a keyboard shortcut."
