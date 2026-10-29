# 🌐 Ctrans (Universal Quick AI Assistant)

[![Linux](https://img.shields.io/badge/OS-Linux%20%2F%20Wayland-blue?logo=linux&logoColor=white)](#)
[![Qt6](https://img.shields.io/badge/UI-PyQt6%20%2F%20Qt6-41cd52?logo=qt&logoColor=white)](#)
[![Groq](https://img.shields.io/badge/AI-Groq%20Cloud-f55036?logo=groq&logoColor=white)](#)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange?logo=google&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A minimalist, ultra-fast, and aesthetic **Glassmorphism Universal Quick AI Assistant** built with **native PyQt6 (Qt6)** and powered by **Groq Cloud API** (`openai/gpt-oss-120b` or `qwen/qwen3.8-27b`) with automatic failover to **Google Gemini API** (`gemini-3.5-flash-lite`).

Specially engineered for **Wayland compositors** (KDE Plasma 6, Hyprland, Sway, GNOME) with a seamless single-window Raycast/Spotlight experience, native Markdown rendering, command autocomplete, and deep customization. Users can configure both the default assistant behavior (`execution/DEFAULT.md`) and any number of modular slash commands (`execution/commands/*.md`).

---

## ✨ Features

- ⚡ **Ultra-Fast Hybrid Backend:** Primary requests via **Groq Cloud API** (~0.6s sub-second response) with automatic failover to **Google Gemini API**.
- 🪟 **Single-Window Fluid HUD:** Frameless, frosted dark HUD (`rgba(28, 28, 30, 0.95)`, `border-radius: 12px`, 1px subtle 3D glass border) with a deep floating drop-shadow. Smoothly transitions between states with zero window churn or visual flicker.
- 🎯 **Fully Customizable Personas:**
  - **Default Assistant (`execution/DEFAULT.md`):** Customize the AI behavior when no slash command is used (e.g., translator, concise knowledge assistant, summarizer, or coding helper).
  - **Modular Slash Commands (`execution/commands/*.md`):** Add new slash commands anytime (`/ask`, `/eva`, `/summary`, etc.) simply by adding a markdown prompt file.
- 📜 **Native CommonMark & Math Formula Rendering:** Renders headers, lists, code blocks, and AI LaTeX mathematical formulas (`$...$`, `$$...$$`, `\[...\]`, `\(...\)`) automatically converted into clean Unicode mathematical notation.
- ↕️ **Smooth Scrolling & Modern Slim Scrollbar:** Responsive mouse-wheel scrolling with an elegant, visible, slim (5px) modern gray scrollbar.
- ⌨️ **Slash Command Autocomplete:** Type `/` to instantly open an interactive dropdown of all registered commands (`/help`, `/ask`, `/eva`).
- 📋 **1-Click Clipboard Copy:** Instant copy button on every response card with visual `"✓ Copied!"` feedback.
- 🖱️ **Wayland Click-to-Dismiss:** Closes automatically on <kbd>Enter</kbd>, <kbd>Esc</kbd>, or when clicking anywhere outside the HUD window.
- 💻 **Headless CLI Mode:** Run queries directly in the terminal via `ctrans --cli [query]` for shell pipelines and automation.

---

## 🛠️ Prerequisites

| Dependency | Package Name (Fedora) | Package Name (Ubuntu/Debian) | Package Name (Arch) | Purpose |
|------------|----------------------|------------------------------|---------------------|---------|
| `python3` | `python3` | `python3` | `python` | Core Python runtime |
| `PyQt6` | `python3-pyqt6` | `python3-pyqt6` | `python-pyqt6` | Native Qt6 Glassmorphism HUD |

### Installation:
```bash
# Fedora:
sudo dnf install python3-pyqt6

# Ubuntu / Debian:
sudo apt install python3-pyqt6

# Or via pip (user install):
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
- Set up configuration directory at `~/.config/ctrans/execution/` and `~/.config/ctrans/execution/commands/`.
- Copy template configuration (`config.env`).
- Symlink default persona (`execution/DEFAULT.md`) and modular commands (`ask.md`, `eva.md`).
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
Or bind `ctrans` to a global keyboard shortcut in KDE Plasma / GNOME / Hyprland (e.g. `Meta + Space` or `Alt + Space`).

---

## 🎮 Workflow & Commands

| Input | Mode | Description |
|---|---|---|
| `<prompt or text>` | **Default Assistant** | Direct execution with customizable default persona (`execution/DEFAULT.md`). |
| `/help` or `/` | **Command Help** | Displays the interactive catalog of all available commands. |
| `/ask <topic>` | **Bilingual Explainer** | Clear, structured concept explanation in English followed by Vietnamese. |
| `/eva <sentence>` | **Language Coach** | Grammar critique in Vietnamese and 3 native English rephrasing suggestions. |

---

## 🎨 Customizing the Default Assistant

You can define how Ctrans behaves when no slash command is entered:

1. Edit your personal default prompt file:
   ```bash
   nano ~/.config/ctrans/execution/DEFAULT.md
   ```
2. Replace it with any desired AI persona (e.g., concise knowledge assistant, translation engine, terminal command helper, or code explainer).
3. Any plain query typed into Ctrans will now be executed according to your custom default instructions.

---

## 🧩 Adding Custom Slash Commands

You can create new slash commands without touching any application code:

1. Create a markdown file inside `~/.config/ctrans/execution/commands/`:
   ```bash
   nano ~/.config/ctrans/execution/commands/summary.md
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
   - Run `/summary <paste text>` to execute!

---

## 💻 CLI & Headless Usage

You can execute queries directly in your terminal without opening the HUD:

```bash
# Direct default query
ctrans --cli "Explain Dijkstra algorithm in 2 sentences"

# Run a slash command
ctrans --cli /ask "Quantum computing"

# View available commands
ctrans --help
```

---

## 📁 Project Structure

```
ctrans/
├── ctrans.py                  # Main executable entrypoint (PyQt6 HUD / CLI)
├── core/                      # Application core engine
│   ├── __init__.py            # Core exports
│   ├── config.py              # Configuration loader (config.env / .env)
│   ├── router.py              # Slash command parser & deterministic router
│   ├── command_loader.py      # Scans commands/*.md and metadata
│   └── api_client.py          # Asynchronous Groq / Gemini hybrid client
├── ui/                        # PyQt6 Glassmorphism user interface
│   ├── __init__.py            # UI exports
│   ├── app.py                 # QApplication lifecycle & font setup
│   ├── main_window.py         # Frameless single-window container & state machine
│   ├── input_bar.py           # QLineEdit with slash command autocomplete
│   ├── result_view.py         # QTextBrowser with CommonMark & 1-click copy
│   ├── loading_indicator.py   # Subtle animated request indicator
│   └── styles.qss             # Translucent Glassmorphism QSS stylesheet
├── execution/                 # Prompt definitions & command templates
│   ├── DEFAULT.md             # Default assistant prompt (used when no slash command is given)
│   ├── GUIDE.md               # Command authoring specifications
│   └── commands/              # Modular slash command prompts
│       ├── ask.md             # /ask bilingual explanation prompt
│       └── eva.md             # /eva grammar and phrasing critique prompt
├── tests/                     # Automated test suite
│   ├── test_core.py           # Core router and loader unit tests
│   └── test_ui.py             # Headless PyQt6 UI tests
├── install.sh                 # System installer & desktop entry setup
└── README.md                  # Documentation
```

---

## 🧪 Running Tests

Ctrans includes automated unit tests covering both the core engine and the UI components:

```bash
python3 -m unittest discover tests
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
