# 🌐 Ctrans (Convenient Translation & Quick AI Assistant)

[![Linux](https://img.shields.io/badge/OS-Linux%20%2F%20Wayland-blue?logo=linux&logoColor=white)](#)
[![Rofi](https://img.shields.io/badge/UI-Rofi%202.0-purple)](#)
[![Groq](https://img.shields.io/badge/AI-Groq%20Cloud-f55036?logo=groq&logoColor=white)](#)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange?logo=google&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A minimalist, ultra-fast, and aesthetic **Glassmorphism Quick Translator & Universal AI Assistant** built on top of **Rofi** and powered by **Groq Cloud API** (`openai/gpt-oss-120b` or `qwen/qwen3.8-27b`) with seamless fallback to **Google Gemini API** (`gemini-3.5-flash-lite`).

Specially engineered for **Wayland compositors** (KDE Plasma 6, Hyprland, Sway) with native layer-shell exclusive keyboard focus, click-outside-to-dismiss behavior, decoupled prompt customization, and a deterministic Bash slash-command router.

---

## ✨ Features

- ⚡ **Ultra-Fast Hybrid Backend:** Primary requests via **Groq Cloud API** (~0.6s sub-second response) with automatic failover to **Google Gemini API**.
- 🚀 **Modular Slash Command Router:** 0ms deterministic Bash regex router supporting `/ask <topic>`, `/eva <sentence>`, and custom user commands.
- 💡 **Built-in `/help` Command:** Type `/help` or `/` alone to view dynamically discovered commands with extracted 1-line descriptions.
- 🎨 **Minimal Glassmorphism UI:** Translucent frosted dark background (`rgba(28, 28, 30, 0.95)`) with crisp typography (`Inter Display`).
- 🔄 **Seamless Continuity & Dynamic Feedback:** Search bar transforms seamlessly into tailored loading labels (`Asking AI [/ask]...`, `Evaluating [/eva]...`, `Analyzing...`) at identical coordinates.
- 📐 **Dynamic Fit-to-Content:** Intelligent soft-wrapping with auto-expansion for response cards from 3 lines to 30+ lines with zero clipping.
- 📝 **Decoupled Markdown Prompts:** System prompts live in standalone markdown files (`prompt.md` and `commands/*.md`)—customize formats and add new personas without writing code.
- ✂️ **Smart Input Limiter:** Enforces a clean 500-character limit, automatically truncating overlength pasted text to prevent API payload overflow.
- 🖱️ **Wayland Click-to-Dismiss:** Fullscreen backdrop on response mode allowing you to dismiss cards with <kbd>Enter</kbd>, <kbd>Esc</kbd>, or by **clicking anywhere outside the card**.

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
- Check all required dependencies.
- Create configuration folder at `~/.config/ctrans/` and `~/.config/ctrans/commands/`.
- Copy template configuration (`config.env`) and link default system prompt (`prompt.md`).
- Symlink default modular commands (`ask.md`, `eva.md`).
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

## 🎮 Workflow & Commands

| Input | Mode | Description |
|---|---|---|
| `<word or sentence>` | **Translator (Default)** | Direct English ↔ Vietnamese translation with IPA, keywords, or definitions. |
| `/help` or `/` | **Command Help** | Displays the interactive catalog of all available commands. |
| `/ask <topic>` | **Bilingual Explainer** | Clear, structured concept explanation in English followed by Vietnamese. |
| `/eva <sentence>` | **Language Coach** | Grammar critique in Vietnamese and 3 native English rephrasing suggestions. |

### Closing Cards:
- Press <kbd>Enter</kbd>
- Press <kbd>Esc</kbd>
- **Click anywhere outside the card** on the dimmed screen backdrop.

---

## 🧩 Adding Custom Slash Commands

You can create new slash commands without touching `Ctrans.sh`:

1. Create a markdown file inside `~/.config/ctrans/commands/`:
   ```bash
   nano ~/.config/ctrans/commands/summary.md
   ```
2. Define the header description on the first line, followed by the system instructions:
   ```markdown
   # /summary - Summarize articles or notes into 3 concise bullet points

   You are an expert executive summarizer.
   When given text, distill the core insights into exactly 3 high-impact bullet points.
   ```
3. Save the file. Your new command is immediately available:
   - Type `/` or `/help` to see `/summary` listed automatically.
   - Run `/summary <paste article>` to execute!

---

## 📁 Project Structure

```
ctrans/
├── .env.example         # Template configuration (Groq + Gemini)
├── .gitignore           # Excludes sensitive keys, logs, and context.md
├── AGENTS.md            # Agent rules & commit guidelines (gitignored)
├── config.env           # Active credentials file (gitignored, chmod 600)
├── context.md           # Technical knowledge base & architecture (gitignored)
├── Ctrans.sh            # Main execution script (Groq/Gemini hybrid + Bash router)
├── install.sh           # Automated installer & desktop integration
├── LICENSE              # MIT Open Source License
├── prompt.md            # Default system prompt (used when no slash command is given)
├── commands/            # Directory containing modular slash command prompts
│   ├── ask.md           # /ask command: bilingual concept explanation
│   └── eva.md           # /eva command: sentence evaluation and phrasing critique
└── README.md            # User guide and documentation
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
