# 🌐 Rofi AI Translator

[![Linux](https://img.shields.io/badge/OS-Linux%20%2F%20Wayland-blue?logo=linux&logoColor=white)](#)
[![Rofi](https://img.shields.io/badge/UI-Rofi%202.0-purple)](#)
[![Groq](https://img.shields.io/badge/AI-Groq%20Cloud-f55036?logo=groq&logoColor=white)](#)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange?logo=google&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A minimalist, ultra-fast, and aesthetic **Glassmorphism Quick Translator** built with **Rofi** and powered by **Groq Cloud API** (`llama-3.3-70b-versatile`) with seamless fallback to **Google Gemini API** (`gemini-3.5-flash-lite`).

Specially engineered for **Wayland compositors** (KDE Plasma, Hyprland, Sway) with native-like click-to-dismiss behavior, smooth fade transitions, and auto-clipboard integration.

---

## ✨ Features

- ⚡ **Ultra-Fast Translation:** Powered by **Groq Cloud API** (`llama-3.3-70b-versatile`) with sub-second response (~0.6s), with automatic fallback to **Google Gemini API** (`gemini-3.5-flash-lite`).
- 🎨 **Minimal Glassmorphism UI:** Translucent frosted dark background with crisp typography (`Inter`).
- 🔄 **Seamless Continuity:** Transition between the search bar and the loading indicator without awkward resizing or layout shifting.
- 📐 **Fit-to-Content Layout:** The translation box dynamically wraps its height to fit the text content perfectly with zero dead space.
- 🖱️ **Wayland Click-to-Dismiss:** Overcomes Wayland's security isolation by using a full-surface interactive backdrop—clicking outside immediately closes the window.
- 📋 **Auto Clipboard Sync:** The translated result is automatically placed into your system clipboard via `wl-copy`.
- 🪟 **Smooth Fade Transitions:** Configured to eliminate jarring shrink/scale window animations on KDE Plasma.

---

## 🛠️ Prerequisites

Ensure the following packages are installed on your Linux system:

| Dependency | Package Name (Fedora) | Package Name (Arch / Ubuntu) | Purpose |
|------------|----------------------|------------------------------|---------|
| `rofi` | `rofi` | `rofi` / `rofi-wayland` | UI modal rendering |
| `curl` | `curl` | `curl` | API requests |
| `jq` | `jq` | `jq` | JSON parsing |
| `wl-copy` | `wl-clipboard` | `wl-clipboard` | Wayland clipboard integration |

On Fedora:
```bash
sudo dnf install rofi curl jq wl-clipboard
```

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/your-username/rofi-translate.git ~/.local/bin/rofi_translate
cd ~/.local/bin/rofi_translate
```

### 2. Run the Installer
```bash
chmod +x install.sh
./install.sh
```

### 3. Add your API Keys
Get your API keys:
- **Groq API Key (Recommended for ~0.6s speed):** Free at [console.groq.com](https://console.groq.com/keys)
- **Gemini API Key (Fallback):** Free at [Google AI Studio](https://aistudio.google.com/)

Edit your configuration file:
```bash
nano ~/.config/rofi-translate/config.env
```
Paste your keys:
```bash
# Groq API Key (Siêu tốc ~0.6s)
GROQ_API_KEY="your_groq_api_key_here"
GROQ_MODEL="llama-3.3-70b-versatile"

# Gemini API Key (Fallback dự phòng)
GEMINI_API_KEY="your_gemini_api_key_here"
GEMINI_MODEL="gemini-3.5-flash-lite"
```

### 4. Run Rofi Translate
Run it directly from terminal:
```bash
rofi-translate
```
Or bind `rofi-translate` (or `~/.local/bin/rofi-translate`) to a global shortcut in your Desktop Environment (e.g. `Meta + T` or `Ctrl + Alt + T`).

---

## 🎮 Workflow & Shortcuts

1. **Open Search Bar:** Type the word or phrase to translate (English ↔ Vietnamese) and hit <kbd>Enter</kbd>.
2. **Loading State:** A seamless indicator displays `✨ AI đang phân tích và dịch...`.
3. **Result Dialog:** Displays the main translation, key vocabulary notes, and contextual examples.
4. **Closing the Dialog:**
   - Press <kbd>Enter</kbd>
   - Press <kbd>Esc</kbd>
   - **Click anywhere outside the card** on the dimmed screen backdrop.

The translated text is automatically copied to your clipboard so you can immediately paste (<kbd>Ctrl</kbd> + <kbd>V</kbd>) it into any application.

---

## ⚙️ Configuration & Customization

All settings can be customized in `~/.config/rofi-translate/config.env` or directly in `rofi_translate.sh`:

- **Model selection:** Change `GEMINI_MODEL="gemini-3.5-flash-lite"` to any other available model (e.g., `gemini-3.8-flash`).
- **Translation prompt:** Customize `SYSTEM_PROMPT` inside `rofi_translate.sh` to adjust target languages, tone, or formatting.
- **Font & Sizing:** Change the font (`Inter`, `JetBrains Mono`, etc.) inside the `.rasi` themes in `rofi_translate.sh`.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
