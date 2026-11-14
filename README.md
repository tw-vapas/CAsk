# 🌐 CAsk (Universal Quick AI Assistant & Command Runner)

[![Linux](https://img.shields.io/badge/OS-Linux%20%2F%20Wayland-blue?logo=linux&logoColor=white)](#)
[![Qt6](https://img.shields.io/badge/UI-PyQt6%20%2F%20Qt6-41cd52?logo=qt&logoColor=white)](#)
[![Groq](https://img.shields.io/badge/AI-Groq%20Cloud-f55036?logo=groq&logoColor=white)](#)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange?logo=google&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A **Glassmorphism Universal Quick AI Assistant** built with **native PyQt6 (Qt6)**. Connect OpenAI, Groq, Google Gemini, DeepSeek, Ollama, or a custom API, save multiple model configurations per provider, and switch models inside the input bar.

Specially engineered for **Wayland compositors** (KDE Plasma 6, Hyprland, Sway, GNOME) with multi-window concurrent layouts (up to 3 concurrent capsules), auto-expanding multiline input, interactive keyboard shortcuts, card pinning, token-based command syntax highlighting, Vietnamese IME support, native Markdown rendering, command autocomplete, and deep customization. Users can configure both the default assistant behavior (`execution/DEFAULT.md`) and any number of modular slash commands (`execution/commands/*.md`).

---

## ✨ Features

- ⚡ **Provider Pipeline:** Select a primary provider and one active model per provider. Failed requests fall back to the active model of the next enabled provider. The result identifies the provider/model that actually answered.
- 🪟 **Multi-Window Concurrent HUD (Up to 3 Windows):**
  - **1 Window:** Centered on screen.
  - **2 Windows:** Horizontal side-by-side, occupying **80% of screen width** with equal widths ($W_1$ left, $W_2$ right).
  - **3 Windows:** Horizontal side-by-side, occupying **100% full screen width** with ratio **30 : 40 : 30** ($W_3$ left 30%, $W_1$ center 40%, $W_2$ right 30%).
  - **Interactive Window Reordering:** Reorder windows on the fly using <kbd>Alt</kbd> + <kbd>←</kbd> / <kbd>Alt</kbd> + <kbd>→</kbd> (supported in both Input Bar and Result Box) or by dragging the header grip handle (`⋮⋮`) with real-time drop target ghost preview while strictly maintaining predefined slot ratios.
  - Smoothly re-centers and rebalances as cards are opened or closed.
- 📏 **Auto-Expanding Dynamic Input Bar:** The input capsule includes provider/model selectors and a gear button below the typing area. Height scales from 96px up to 264px. Press <kbd>Enter</kbd> to submit or <kbd>Shift</kbd>+<kbd>Enter</kbd> for a newline. No send button is added.
- 📌 **Response Card Pinning:** Pin any response card with the **Pin** button or shortcut <kbd>Shift</kbd> + <kbd>P</kbd>. Pinned cards stay permanently visible and cannot be dismissed by outside clicks, <kbd>Esc</kbd>, or <kbd>Enter</kbd>.
- ⌨️ **Interactive Keyboard Shortcuts:**
  - <kbd>Shift</kbd> + <kbd>A</kbd>: **Ask** — Return to input bar to refine or type a new query.
  - <kbd>Shift</kbd> + <kbd>C</kbd>: **Copy** — Instant 1-click clipboard copy with visual confirmation.
  - <kbd>Shift</kbd> + <kbd>P</kbd>: **Pin** — Toggle window pinning on/off.
  - <kbd>Alt</kbd> + <kbd>←</kbd> / <kbd>Alt</kbd> + <kbd>→</kbd>: **Reorder** — Swap active capsule position with left or right neighbor (without conflicting with text highlighting).
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
Configure providers through **Settings → Add Provider**. The OpenAI preset uses the Responses API. Enter your API key, connect to load the model catalog, add a saved model configuration, then click **Apply**. Legacy environment configuration below remains available for initial migration.

Settings uses one expanded provider accordion at a time. Expand **Connection settings** to edit credentials. **Add Model → Continue → Add Model** opens embedded catalog/configuration pages; **Back** preserves the unfinished model configuration. Saved models scroll within each provider, and **···** reveals model/provider actions. Removal requires an inline confirmation. **Apply** saves the provider draft; **Cancel** discards it. The existing multi-capsule workflow remains available outside Settings.

On supported Wayland compositors, CAsk requests native backdrop blur only behind rounded capsule regions. Colors and opacity are preserved, with sharp foreground controls and clear corners/gaps. Missing or disabled blur support falls back to translucency. To verify on KDE/Wayland with Spectacle installed:

```bash
QT_QPA_PLATFORM=wayland python3 resources/verify-desktop-blur.py
```

The verifier uses placeholder data and a generated striped desktop background, captures blur on/off plus capsule lifecycle states, then closes its windows. PNGs and geometry JSON are saved under the ignored `resources/bug_screenshots/blur-verification/` directory.


Legacy provider key links:
- **Groq API Key (Recommended for ~0.6s speed):** Free at [console.groq.com](https://console.groq.com/keys)
- **Gemini API Key (Fallback):** Free at [Google AI Studio](https://aistudio.google.com/)

Edit your configuration:
```bash
nano ~/.config/cask/config.env
```
Legacy configuration example (used before `providers.json` is saved):
```bash
# Groq API Key (Fast ~0.6s)
GROQ_API_KEY="your_groq_api_key_here"
GROQ_MODEL="openai/gpt-oss-120b"

# Gemini API Key (Fallback)
GEMINI_API_KEY="your_gemini_api_key_here"
GEMINI_MODEL="gemini-3.5-flash-lite"

# Multi-turn Follow-up Interaction (1-10 turns, default 3)
MAX_FOLLOWUP_TURNS="3"
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
| `/help` or `/` | **Command Help** | Displays the interactive catalog of all available commands, keyboard shortcuts, and usage guide. |
| `/ask <topic>` | **Concept Explainer** | Clear, concise concept explanation with core intuition and real-world application. |
| `/check <statement>` | **Fact-Checker & Critic** | Objective fact-checking, logical critique, and counter-argument analysis. |
| `/eva <sentence>` | **Language Coach** | Sentence evaluation, grammar critique, and native rephrasing suggestions. |
| `/trans <sentence>` | **Bilingual Translator** | High-density bidirectional translation (English <-> Vietnamese). |

### 💬 Multi-Turn Follow-Up Interaction

Each result capsule features a built-in follow-up input bar and turn counter badge `(X/N)`:
- **Thread Continuity:** Ask clarifying questions or request code refinements directly in the active capsule. The complete conversation thread is serialized to Groq / Gemini.
- **Turn Limits:** Limited to 3 turns by default (configurable from 1 to 10 via `MAX_FOLLOWUP_TURNS`). When the limit is reached, the input bar locks and prompts you to start a new card.
- **Focus Safety:** Typing in the follow-up input bar safely permits uppercase letters (`Shift + A`, `Shift + P`, `Shift + C`) without accidentally triggering window shortcuts.
- **Fresh Threads:** Pressing <kbd>Shift</kbd> + <kbd>A</kbd> returns to the main input bar and resets the capsule's history.

### Keyboard Shortcuts in Response Box:

| Key | Action | Description |
|---|---|---|
| <kbd>Ctrl</kbd> + <kbd>,</kbd> | **Settings** | Open Response Model Settings HUD to configure, test, and reorder AI providers. |
| <kbd>Shift</kbd> + <kbd>A</kbd> | **Ask** | Return to the input bar to refine query or enter a new prompt (clears thread history). |
| <kbd>Shift</kbd> + <kbd>C</kbd> | **Copy** | Copy response markdown to clipboard. |
| <kbd>Shift</kbd> + <kbd>P</kbd> | **Pin** | Pin window permanently; suppresses Esc, Enter, and outside-click dismissal. |
| <kbd>Alt</kbd> + <kbd>←</kbd> | **Move Left** | Swap active capsule with adjacent left slot (works in both Input Bar and Result Box, preserving slot ratios). |
| <kbd>Alt</kbd> + <kbd>→</kbd> | **Move Right** | Swap active capsule with adjacent right slot (works in both Input Bar and Result Box, preserving slot ratios). |
| <kbd>Alt</kbd> + <kbd>H</kbd> | **Toggle On-Top** | Toggle Always-on-Top mode (unhide / hide from top layer across both Input Bar and Result Box). |
| <kbd>Esc</kbd> | **Exit** | Close the card (if unpinned; clears input text if typing in follow-up bar; returns to input if in settings). |

> **Tip:** You can also drag the grip handle `⋮⋮` in the capsule header (tooltip shows `[Alt + ← / →]`) to reorder windows interactively with live drop preview.

---

### ⚙️ Providers & Models (<kbd>Ctrl</kbd> + <kbd>,</kbd>)

1. Open the gear button or press **Ctrl+,**. Choose a preset and click **Add Provider**.
2. Set the connection name, API root URL, protocol, and API key. Localhost connections may omit a key. A connection owns the key once; its saved models reuse it.
3. Click **Connect / Refresh Models**. CAsk calls that provider's model-list API in a background thread. OpenAI-compatible providers use `/models`; Gemini Native uses `/v1beta/models`. Supply the full API root, including version prefixes for custom endpoints.
4. Click **Add Model**, search the cached catalog, select an ID, and set a display name and optional parameters. Manual IDs are supported when listing is unavailable. Known non-text Gemini entries are disabled; unknown capabilities are labeled instead of guessed.
5. Use **Duplicate** to create variants such as Sol Medium/Sol High. Radio buttons select exactly one active model per provider. **Test** sends a real short generation request using that profile, reports latency/errors, and can consume provider usage.
6. Click **Apply** to persist the draft and update all capsules. **Cancel** discards draft edits. Applying is blocked during network work or if another capsule changed the configuration while this draft was open.

The input capsule keeps the current CAsk colors and transparency, with provider left and model/gear right below the typing area. Quick selections apply immediately to subsequent questions and are persisted without clearing typed text. The selected provider is primary; provider-card arrows determine the remaining fallback order. Requests use only one active profile per provider, never all saved models in parallel.

**Catalog behavior:** Refresh failure keeps the previous cached list. A successful refresh never deletes saved models or changes the active selection; missing models are marked. Changing credentials, URL, or protocol invalidates the draft cache and ignores outstanding results from the previous connection. Catalog success does not prove every listed model can generate text. Catalogs/timestamps are saved with **Apply**; there is no background refresh on launch.

**Model compatibility:** Separate adapters handle OpenAI Responses, Chat Completions, and Gemini Native. GPT-6.1 Sol has bundled capability metadata: choose `gpt-6.1-sol`, reasoning `Medium`, and provider-default temperature. Reasoning requests omit temperature. Chat Completions maps its output limit to `max_completion_tokens`; Responses uses `max_output_tokens`. Unknown models omit optional parameters by default; manual overrides and a Chat Completions token-parameter selector remain available. The bundled metadata catalog is deliberately small; this release does not download models.dev or implement ChatGPT/Codex subscription authentication.

**Persistence:** `~/.config/cask/providers.json` (or `$XDG_CONFIG_HOME/cask/providers.json`) is the versioned source of truth, atomically saved with mode `0600`. It contains provider connections, catalogs, saved profiles, and selected IDs. Without this file, CAsk migrates `models.json` or resolved legacy environment settings in memory. Old files are left unchanged. After saving providers, legacy files cannot silently reactivate disabled providers; an empty provider list stays empty, and invalid provider files produce an explicit configuration error.

[Design references](resources/references/README.md) illustrate the agreed layout. The older model-card reference remains available for comparison; it is not the current settings editor.

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
├── assets/                    # Application icons & branding assets
│   └── logo.png               # CAsk official logo (desktop & window icon)
├── cask.py                    # Main executable entrypoint (PyQt6 HUD / CLI)
├── core/                      # Application core engine
│   ├── __init__.py            # Core exports
│   ├── config.py              # Provider config loader and legacy env resolution
│   ├── provider_config.py     # Connections, model profiles, migration, private persistence
│   ├── provider_api.py        # Catalog discovery and request adapters
│   ├── router.py              # Slash command parser & deterministic router
│   ├── command_loader.py      # Scans commands/*.md and extracts line 1 metadata
│   ├── math_formatter.py      # LaTeX mathematical formula to Unicode converter
│   └── api_client.py          # Provider fallback pipeline and asynchronous worker
├── ui/                        # PyQt6 Glassmorphism user interface
│   ├── __init__.py            # UI exports
│   ├── app.py                 # QApplication lifecycle & font setup
│   ├── capsule.py             # Independent CAsk interactive card (Input, Loading, Result)
│   ├── icons.py               # Resolution-independent SVG vector icon generators
│   ├── single_instance.py     # Kernel file lock & QLocalServer IPC manager
│   ├── main_window.py         # Multi-capsule orchestrator, slot layout, setMask
│   ├── input_bar.py           # Auto-expanding dynamic input bar with token highlighting
│   ├── result_view.py         # QTextBrowser with action buttons & keyboard shortcuts
│   ├── settings_view.py       # Current provider settings exports
│   ├── provider_settings.py   # Provider accordions and stacked model configuration pages
│   ├── backdrop.py            # Rounded capsule mask and blur regions
│   ├── wayland_blur.py        # Native Wayland backdrop effect transport
│   ├── legacy_settings_view.py # Former UI retained for historical reference rendering
│   ├── loading_indicator.py   # Subtle animated request indicator
│   └── styles.qss             # Translucent Glassmorphism QSS stylesheet
├── execution/                 # Prompt definitions & command templates
│   ├── DEFAULT.md             # Default assistant prompt (used when no slash command is given)
│   ├── GUIDE.md               # Command authoring specifications
│   └── commands/              # Modular slash command prompts
│       ├── ask.md             # /ask concept explanation prompt
│       ├── check.md           # /check objective critique and counter-argument prompt
│       ├── eva.md             # /eva grammar and phrasing critique prompt
│       └── trans.md           # /trans bilingual translation prompt
├── tests/                     # Automated test suite
│   ├── test_core.py           # Core router and loader unit tests
│   ├── test_providers.py      # Provider migration, fake HTTP integration, Qt workflows
│   ├── test_settings_view.py  # Scrolling, queued results, and transparent rendering
│   ├── test_settings_v2.py    # Settings navigation, inline removal, draft isolation
│   ├── test_backdrop.py       # Native blur geometry and lifecycle regressions
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
