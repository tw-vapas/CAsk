# 🌐 CAsk (Universal Quick AI Assistant & Command Runner)

[![Linux](https://img.shields.io/badge/OS-Linux%20%2F%20Wayland-blue?logo=linux&logoColor=white)](#)
[![Qt6](https://img.shields.io/badge/UI-PyQt6%20%2F%20Qt6-41cd52?logo=qt&logoColor=white)](#)
[![Groq](https://img.shields.io/badge/AI-Groq%20Cloud-f55036?logo=groq&logoColor=white)](#)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange?logo=google&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A minimalist, ultra-fast, and aesthetic **Glassmorphism Universal Quick AI Assistant** built with **native PyQt6 (Qt6)** and powered by **Groq Cloud API** (`openai/gpt-oss-120b` or `qwen/qwen3.8-27b`) with automatic failover to **Google Gemini API** (`gemini-3.5-flash-lite`).

Specially engineered for **Wayland compositors** (KDE Plasma 6, Hyprland, Sway, GNOME) with multi-window concurrent layouts (up to 3 concurrent capsules), auto-expanding multiline input, interactive keyboard shortcuts, card pinning, token-based command syntax highlighting, Vietnamese IME support, native Markdown rendering, command autocomplete, and deep customization. Users can configure both the default assistant behavior (`execution/DEFAULT.md`) and any number of modular slash commands (`execution/commands/*.md`).

---

## ✨ Features

- ⚡ **Ultra-Fast Hybrid Backend:** Primary requests via **Groq Cloud API** (~0.6s sub-second response) with automatic failover to **Google Gemini API**.
- 🪟 **Multi-Window Concurrent HUD (Up to 3 Windows):**
  - **1 Window:** Centered on screen.
  - **2 Windows:** Horizontal side-by-side, occupying **80% of screen width** with equal widths ($W_1$ left, $W_2$ right).
  - **3 Windows:** Horizontal side-by-side, occupying **100% full screen width** with ratio **30 : 40 : 30** ($W_3$ left 30%, $W_1$ center 40%, $W_2$ right 30%).
  - **Interactive Window Reordering:** Reorder windows on the fly using <kbd>Shift</kbd> + <kbd>←</kbd> / <kbd>Shift</kbd> + <kbd>→</kbd> or by dragging the header grip handle (`⋮⋮`) with real-time drop target ghost preview while strictly maintaining predefined slot ratios.
  - Smoothly re-centers and rebalances as cards are opened or closed.
- 📏 **Auto-Expanding Dynamic Input Bar:** Height dynamically scales from 50px up to 220px to fit multiple lines and wrapped text naturally. Press <kbd>Shift</kbd>+<kbd>Enter</kbd> to insert newlines without submitting.
- 📌 **Response Card Pinning:** Pin any response card with the **Pin** button or shortcut <kbd>Shift</kbd> + <kbd>P</kbd>. Pinned cards stay permanently visible and cannot be dismissed by outside clicks, <kbd>Esc</kbd>, or <kbd>Enter</kbd>.
- ⌨️ **Interactive Keyboard Shortcuts:**
  - <kbd>Shift</kbd> + <kbd>A</kbd>: **Ask** — Return to input bar to refine or type a new query.
  - <kbd>Shift</kbd> + <kbd>C</kbd>: **Copy** — Instant 1-click clipboard copy with visual confirmation.
  - <kbd>Shift</kbd> + <kbd>P</kbd>: **Pin** — Toggle window pinning on/off.
  - <kbd>Shift</kbd> + <kbd>←</kbd> / <kbd>Shift</kbd> + <kbd>→</kbd>: **Reorder** — Swap active capsule position with left or right neighbor.
  - <kbd>Esc</kbd>: **Exit** — Dismiss the active unpinned card.
- 🎨 **Resolution-Independent SVG Icons:** Crisp vector icons for Ask (magnifying glass), Copy, Pin, Exit, and Drag Grip Handle (`⋮⋮`).
- 🎯 **Fully Customizable Personas:**
  - **Default Assistant (`execution/DEFAULT.md`):** Customize the AI behavior when no slash command is used (e.g., translator, concise knowledge assistant, summarizer, or coding helper).
  - **Modular Slash Commands (`execution/commands/*.md`):** Add new slash commands anytime (`/ask`, `/eva`, `/trans`, `/summary`, etc.) simply by adding a markdown prompt file.
- 📜 **Native CommonMark & Math Formula Rendering:** Renders headers, lists, code blocks, and AI LaTeX mathematical formulas (`$...$`, `$$...$$`, `\[...\]`, `\(...\)`) automatically converted into clean Unicode mathematical notation.
- 🇻🇳 **Vietnamese IME Support:** Full integration with Fcitx5 / IBus across Wayland (`zwp_text_input_v3`) and X11 sessions.
- 🎨 **Token-Only Command Highlighting:** Formats strictly the slash command token (`/ask`) in bold yellow (`#f9e2af`), leaving your prompt query in clear, clean typography.
- 🖱️ **Wayland Click-Through Masking:** Transparent spaces between and around cards allow clicking and interacting directly with background desktop applications.
- 💻 **Headless CLI Mode:** Run queries directly in the terminal via `cask --cli [query]` for shell pipelines and automation.

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
git clone https://github.com/tw-vapas/Ctrans.git ~/.local/bin/cask_project
cd ~/.local/bin/cask_project
```

### 2. Run the Installer
```bash
chmod +x install.sh
./install.sh
```
This script will:
- Verify Python 3 and PyQt6.
- Set up configuration directory at `~/.config/cask/execution/` and `~/.config/cask/execution/commands/`.
- Copy template configuration (`config.env`).
- Symlink default persona (`execution/DEFAULT.md`) and modular commands (`ask.md`, `eva.md`, `trans.md`).
- Symlink `cask.py` to `~/.local/bin/cask` and `~/.local/bin/CAsk`.
- Register `cask.desktop` for system-wide shortcut binding.

### 3. Add your API Keys
Get your API keys:
- **Groq API Key (Recommended for ~0.6s speed):** Free at [console.groq.com](https://console.groq.com/keys)
- **Gemini API Key (Fallback):** Free at [Google AI Studio](https://aistudio.google.com/)

Edit your configuration:
```bash
nano ~/.config/cask/config.env
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

### 4. Run CAsk
Run it directly from your terminal:
```bash
cask
```
Or bind `cask` to a global keyboard shortcut in KDE Plasma / GNOME / Hyprland (e.g. `Meta + Space` or `Alt + Space`).
Pressing the shortcut multiple times can open up to **3 concurrent side-by-side windows**.

---

## 🎮 Workflow & Commands

| Input | Mode | Description |
|---|---|---|
| `<prompt or text>` | **Default Assistant** | Direct execution with customizable default persona (`execution/DEFAULT.md`). |
| `/help` or `/` | **Command Help** | Displays the interactive catalog of all available commands and their line 1 metadata. |
| `/ask <topic>` | **Concept Explainer** | Clear, concise concept explanation with core intuition and real-world application. |
| `/eva <sentence>` | **Language Coach** | Sentence evaluation, grammar critique, and native rephrasing suggestions. |
| `/trans <sentence>` | **Bilingual Translator** | High-density bidirectional translation (English <-> Vietnamese). |

### Keyboard Shortcuts in Response Box:

| Key | Action | Description |
|---|---|---|
| <kbd>Shift</kbd> + <kbd>A</kbd> | **Ask** | Return to the input bar to refine query or enter a new prompt. |
| <kbd>Shift</kbd> + <kbd>C</kbd> | **Copy** | Copy response markdown to clipboard. |
| <kbd>Shift</kbd> + <kbd>P</kbd> | **Pin** | Pin window permanently; suppresses Esc, Enter, and outside-click dismissal. |
| <kbd>Shift</kbd> + <kbd>←</kbd> | **Move Left** | Swap active capsule with adjacent left slot (preserving layout slot ratios). |
| <kbd>Shift</kbd> + <kbd>→</kbd> | **Move Right** | Swap active capsule with adjacent right slot (preserving layout slot ratios). |
| <kbd>Esc</kbd> | **Exit** | Close the card (if unpinned). |

> **Tip:** You can also drag the grip handle `⋮⋮` in the capsule header to reorder windows interactively with live drop preview.

---

## 🎨 Customizing the Default Assistant

You can define how CAsk behaves when no slash command is entered:

1. Edit your personal default prompt file:
   ```bash
   nano ~/.config/cask/execution/DEFAULT.md
   ```
2. Replace it with any desired AI persona (e.g., concise knowledge assistant, translation engine, terminal command helper, or code explainer).
3. Any plain query typed into CAsk will now be executed according to your custom default instructions.

---

## 🧩 Adding Custom Slash Commands

You can create new slash commands without touching any application code:

1. Create a markdown file inside `~/.config/cask/execution/commands/`:
   ```bash
   nano ~/.config/cask/execution/commands/summary.md
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
   - Run `/help` to see `/summary` with its description in the catalog.
   - Run `/summary <paste text>` to execute!

---

## 💻 CLI & Headless Usage

You can execute queries directly in your terminal without opening the HUD:

```bash
# Direct default query
cask --cli "Explain Dijkstra algorithm in 2 sentences"

# Run a slash command
cask --cli /ask "Quantum computing"

# View available commands
cask --help
```

---

## 📁 Project Structure

```
cask/
├── cask.py                    # Main executable entrypoint (PyQt6 HUD / CLI)
├── core/                      # Application core engine
│   ├── __init__.py            # Core exports
│   ├── config.py              # Configuration loader (config.env / .env)
│   ├── router.py              # Slash command parser & deterministic router
│   ├── command_loader.py      # Scans commands/*.md and extracts line 1 metadata
│   ├── math_formatter.py      # LaTeX mathematical formula to Unicode converter
│   └── api_client.py          # Asynchronous Groq / Gemini hybrid client
├── ui/                        # PyQt6 Glassmorphism user interface
│   ├── __init__.py            # UI exports
│   ├── app.py                 # QApplication lifecycle & font setup
│   ├── capsule.py             # Independent CAsk interactive card (Input, Loading, Result)
│   ├── icons.py               # Resolution-independent SVG vector icon generators
│   ├── single_instance.py     # Kernel file lock & QLocalServer IPC manager
│   ├── main_window.py         # Multi-capsule orchestrator, slot layout, setMask
│   ├── input_bar.py           # Auto-expanding dynamic input bar with token highlighting
│   ├── result_view.py         # QTextBrowser with action buttons & keyboard shortcuts
│   ├── loading_indicator.py   # Subtle animated request indicator
│   └── styles.qss             # Translucent Glassmorphism QSS stylesheet
├── execution/                 # Prompt definitions & command templates
│   ├── DEFAULT.md             # Default assistant prompt (used when no slash command is given)
│   ├── GUIDE.md               # Command authoring specifications
│   └── commands/              # Modular slash command prompts
│       ├── ask.md             # /ask concept explanation prompt
│       ├── eva.md             # /eva grammar and phrasing critique prompt
│       └── trans.md           # /trans bilingual translation prompt
├── tests/                     # Automated test suite
│   ├── test_core.py           # Core router and loader unit tests
│   └── test_ui.py             # Headless PyQt6 UI tests
├── install.sh                 # System installer & desktop entry setup
└── README.md                  # Documentation
```

---

## 🧪 Running Tests

CAsk includes automated unit tests covering both the core engine and the UI components:

```bash
python3 -m unittest discover tests
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
