# 🌐 Ctrans (Convenient Translation & Quick AI Assistant)

[![Linux](https://img.shields.io/badge/OS-Linux%20%2F%20Wayland-blue?logo=linux&logoColor=white)](#)
[![Qt6](https://img.shields.io/badge/UI-PyQt6%20%2F%20Qt6-41cd52?logo=qt&logoColor=white)](#)
[![Groq](https://img.shields.io/badge/AI-Groq%20Cloud-f55036?logo=groq&logoColor=white)](#)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange?logo=google&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A minimalist, ultra-fast, and aesthetic **Glassmorphism Quick Translator & Universal AI Assistant** built with **native PyQt6 (Qt6)** and powered by **Groq Cloud API** (`openai/gpt-oss-120b` or `qwen/qwen3.8-27b`) with automatic failover to **Google Gemini API** (`gemini-3.5-flash-lite`).

Specially engineered for **Wayland compositors** (KDE Plasma 6, Hyprland, Sway, GNOME) with a seamless single-window Raycast/Spotlight experience, native Markdown rendering, command autocomplete, click-outside-to-dismiss, and backward-compatible Rofi fallback.

---

## ✨ Features

- ⚡ **Ultra-Fast Hybrid Backend:** Primary requests via **Groq Cloud API** (~0.6s sub-second response) with automatic failover to **Google Gemini API**.
- 🪟 **Single-Window Fluid HUD:** Frameless, frosted dark HUD (`rgba(28, 28, 30, 0.95)`). Smoothly transitions from Input to Loading and expands to Result with zero window churn or visual flicker.
- 📜 **Native CommonMark Rendering:** Renders headers, bold/italics, bullet points, blockquotes, and code blocks using Qt6's native Markdown engine.
- ↕️ **Smooth Mouse-Wheel Scrolling:** Responsive scrolling with custom glassmorphic slim scrollbars for long explanations.
- ⌨️ **Slash Command Autocomplete:** Type `/` to instantly open an interactive dropdown of all registered commands (`/help`, `/ask`, `/eva`).
- 📋 **1-Click Clipboard Copy:** Instant copy button on every response card with visual `"✓ Copied!"` feedback.
- 🖱️ **Wayland Click-to-Dismiss:** Closes automatically on <kbd>Enter</kbd>, <kbd>Esc</kbd>, or when clicking anywhere outside the HUD window.
- 🚀 **Modular Command Prompts:** Standalone prompt files (`commands/*.md`)—create new assistant personas without writing application code.
- 💻 **Headless CLI Mode:** Run queries directly in the terminal via `ctrans --cli [query]` for scripting or shell pipelines.
- 🛡️ **Backward Compatibility:** Seamlessly falls back to the legacy Rofi/Bash script (`Ctrans.sh`) if PyQt6 is not installed.

---

## 🛠️ Prerequisites

| Dependency | Package Name (Fedora) | Package Name (Arch / Ubuntu) | Purpose |
|------------|----------------------|------------------------------|---------|
| `python3` | `python3` | `python3` | Core runtime |
| `python3-pyqt6` | `python3-pyqt6` / `pip install PyQt6` | `python-pyqt6` / `python3-pyqt6` | Native Qt6 Glassmorphic HUD |
| `rofi` *(Optional)* | `rofi` | `rofi` / `rofi-wayland` | Fallback legacy UI |
| `curl` *(Optional)* | `curl` | `curl` | Fallback legacy network client |
| `jq` *(Optional)* | `jq` | `jq` | Fallback legacy JSON processing |

### Quick Install (Fedora):
```bash
sudo dnf install python3-pyqt6
# Or via pip:
pip install PyQt6
```

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/your-username/Ctrans.git ~/.local/bin/ctrans_project
cd ~/.local/bin/ctrans_project
```

### 2. Run the Installer
```bash
chmod +x install.sh
./install.sh
```
This script will:
- Verify Python 3 and PyQt6.
- Set up configuration directory at `~/.config/ctrans/` and `~/.config/ctrans/commands/`.
- Copy template configuration (`config.env`) and link default system prompt (`prompt.md`).
- Symlink default modular commands (`ask.md`, `eva.md`).
- Symlink `ctrans.py` to `~/.local/bin/ctrans` and `~/.local/bin/Ctrans`.
- Register `ctrans.desktop` for system-wide shortcut binding.

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
Or bind `ctrans` to a global keyboard shortcut in KDE Plasma / GNOME / Hyprland (e.g. `Meta + T` or `Ctrl + Alt + T`).

---

## 🎮 Workflow & Commands

| Input | Mode | Description |
|---|---|---|
| `<word or sentence>` | **Translator (Default)** | Direct English ↔ Vietnamese translation with IPA, keywords, or definitions. |
| `/help` or `/` | **Command Help** | Displays the interactive catalog of all available commands. |
| `/ask <topic>` | **Bilingual Explainer** | Clear, structured concept explanation in English followed by Vietnamese. |
| `/eva <sentence>` | **Language Coach** | Grammar critique in Vietnamese and 3 native English rephrasing suggestions. |

---

## 🧩 Adding Custom Slash Commands

You can create custom slash commands without touching any application code:

1. Create a markdown file inside `~/.config/ctrans/commands/`:
   ```bash
   nano ~/.config/ctrans/commands/summary.md
   ```
2. Define the header description on the first line, followed by the system prompt:
   ```markdown
   # /summary <text> - Summarize text into 3 concise bullet points
   <!-- Example: /summary Quantum entanglement is... -->

   You are an expert executive summarizer.
   When given text, distill the core insights into exactly 3 high-impact bullet points.
   ```
3. Save the file. Your new command is immediately available:
   - Type `/` to see `/summary` in the autocomplete list.
   - Run `/summary <paste article>` to execute!

---

## 📁 Project Structure

```
ctrans/
├── ctrans.py                  # Main executable entrypoint (PyQt6 HUD / CLI)
├── core/                      # Application core engine
│   ├── config.py              # Configuration loader (config.env / .env)
│   ├── router.py              # Slash command parser & deterministic router
│   ├── command_loader.py      # Scans commands/*.md and metadata
│   └── api_client.py          # Asynchronous Groq / Gemini hybrid client
├── ui/                        # PyQt6 Glassmorphism user interface
│   ├── app.py                 # QApplication lifecycle & font setup
│   ├── main_window.py         # Frameless single-window container & state machine
│   ├── input_bar.py           # QLineEdit with slash command autocomplete
│   ├── result_view.py         # QTextBrowser with CommonMark & 1-click copy
│   ├── loading_indicator.py   # Subtle animated request indicator
│   └── styles.qss             # Translucent Glassmorphism QSS stylesheet
├── commands/                  # Modular command prompt templates
│   ├── GUIDE.md               # Command authoring specifications
│   ├── ask.md                 # /ask bilingual explanation prompt
│   └── eva.md                 # /eva grammar and phrasing critique prompt
├── prompt.md                  # Default translation system prompt
├── install.sh                 # System installer & desktop entry setup
├── Ctrans.sh                  # Legacy Bash/Rofi fallback script
└── README.md                  # Documentation
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
