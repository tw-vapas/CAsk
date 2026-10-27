# 🌐 Ctrans (Convenient Translation)

[![Linux](https://img.shields.io/badge/OS-Linux%20%2F%20Wayland-blue?logo=linux&logoColor=white)](#)
[![Rofi](https://img.shields.io/badge/UI-Rofi%202.0-purple)](#)
[![Groq](https://img.shields.io/badge/AI-Groq%20Cloud-f55036?logo=groq&logoColor=white)](#)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange?logo=google&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A minimalist, ultra-fast, and aesthetic **Glassmorphism Quick Translator** built on top of **Rofi** and powered by **Groq Cloud API** (`openai/gpt-oss-120b` or `qwen/qwen3.8-27b`) with seamless fallback to **Google Gemini API** (`gemini-3.5-flash-lite`).

Specially engineered for **Wayland compositors** (KDE Plasma 6, Hyprland, Sway) with native layer-shell exclusive keyboard focus, click-outside-to-dismiss behavior, and decoupled prompt customization.

---

## ✨ Features

- ⚡ **Ultra-Fast Hybrid Backend:** Primary requests via **Groq Cloud API** (~0.6s sub-second response) with automatic failover to **Google Gemini API**.
- 🎨 **Minimal Glassmorphism UI:** Translucent frosted dark background (`rgba(28, 28, 30, 0.95)`) with crisp typography (`Inter Display`).
- 🔄 **Seamless Continuity:** Transition between the search bar and the loading state (`Analyzing...`) at the exact same coordinates without jarring layout shifting.
- 📐 **Dynamic Fit-to-Content:** Intelligent soft-wrapping with auto-expansion for translation cards from 3 lines to 30+ lines with zero clipping.
- 📝 **Decoupled System Prompt:** System prompts live in a dedicated `prompt.md` file—customize your translation formats and rules without touching a single line of script code!
- ✂️ **Smart Input Limiter:** Enforces a clean 500-character limit, automatically truncating overlength pasted text to prevent API payload overflow.
- 🖱️ **Wayland Click-to-Dismiss:** Fullscreen backdrop on response mode allowing you to dismiss the card with <kbd>Enter</kbd>, <kbd>Esc</kbd>, or by **clicking anywhere outside the card**.

---

## 🛠️ Prerequisites

Ensure the following packages are installed on your Linux system:

| Dependency | Package Name (Fedora) | Package Name (Arch / Ubuntu) | Purpose |
|------------|----------------------|------------------------------|---------|
| `rofi` | `rofi` | `rofi` / `rofi-wayland` | UI modal rendering |
| `curl` | `curl` | `curl` | Fast IPv4 API requests |
| `jq` | `jq` | `jq` | JSON payload serialization |

On Fedora:
```bash
sudo dnf install rofi curl jq
```

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/your-username/rofi_translate.git ~/.local/bin/ctrans_project
cd ~/.local/bin/ctrans_project
```

### 2. Run the Installer
```bash
chmod +x install.sh
./install.sh
```
This script will:
- Check all dependencies.
- Create configuration folder at `~/.config/ctrans/`.
- Copy template configuration (`config.env`) and link default system prompt (`prompt.md`).
- Symlink the executable to `~/.local/bin/ctrans` and `~/.local/bin/Ctrans`.
- Register a desktop entry `ctrans.desktop` for system-wide shortcut binding.

### 3. Add your API Keys
Get your API keys:
- **Groq API Key (Recommended for ~0.6s speed):** Free at [console.groq.com](https://console.groq.com/keys)
- **Gemini API Key (Fallback):** Free at [Google AI Studio](https://aistudio.google.com/)

Edit your configuration:
```bash
nano ~/.config/ctrans/config.env
```
Paste your keys:
```bash
# Groq API Key (Fast ~0.6s)
GROQ_API_KEY="your_groq_api_key_here"
GROQ_MODEL="openai/gpt-oss-120b"

# Gemini API Key (Fallback)
GEMINI_API_KEY="your_gemini_api_key_here"
GEMINI_MODEL="gemini-3.5-flash-lite"
```

### 4. Run Ctrans
Run it directly from your terminal:
```bash
ctrans
```
Or bind `ctrans` (or `~/.local/bin/ctrans`) to a global shortcut in your Desktop Environment settings (e.g. `Meta + T` or `Ctrl + Alt + T`).

---

## 📝 Customizing the System Prompt

You can customize how the AI translates without touching the source code:

1. Open the prompt file:
   ```bash
   nano ~/.config/ctrans/prompt.md
   ```
2. Modify the rules, language directions, or format presets (e.g., adding slang definitions, formal vs casual tone, or specialized jargon).
3. Save the file. Ctrans will immediately load your custom prompt on the next execution!

---

## 🎮 Workflow & Shortcuts

1. **Open Search Bar:** Type or paste (<kbd>Ctrl</kbd> + <kbd>V</kbd>) the word or sentence to translate and hit <kbd>Enter</kbd>.
2. **Loading State:** `Analyzing...` appears seamlessly in place of the input bar.
3. **Result Dialog:** Displays the formatted translation card, evaluation, and keyword notes.
4. **Closing the Dialog:**
   - Press <kbd>Enter</kbd>
   - Press <kbd>Esc</kbd>
   - **Click anywhere outside the card** on the dimmed screen backdrop.

---

## 📁 Project Structure

```
rofi_translate/ (Ctrans)
├── .env.example         # Template configuration (Groq + Gemini)
├── .gitignore           # Excludes sensitive keys, logs, and context.md
├── prompt.md            # Default decoupled AI System Prompt
├── Ctrans.sh            # Main execution script
├── install.sh           # Automated installer & desktop integration
├── LICENSE              # MIT Open Source License
├── README.md            # User guide and documentation
└── context.md           # Internal architectural decisions (gitignored)
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
