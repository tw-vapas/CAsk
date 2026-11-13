# CAsk (Universal Quick AI Assistant & Command Runner) - Technical Knowledge Base

This document details the software architecture, design principles, technical solutions, and component specifications for CAsk v2.0.

---

## 1. System Architecture & Workflow

- **Project:** CAsk (Universal Quick AI Assistant & Command Runner)
- **Version:** 2.0.0
- **Runtime:** Python 3.10+
- **UI Framework:** Native PyQt6 (Qt6 Widgets)
- **Target OS:** Linux (Fedora, Arch, Ubuntu/Debian)
- **Display Server:** Wayland (Compositor: KDE Plasma 6 / KWin, Hyprland, Sway, GNOME) & X11 fallback
- **AI Backend (Hybrid Failover):**
  - **Primary:** Groq Cloud API (default model: `openai/gpt-oss-120b` or `qwen/qwen3.8-27b`) for sub-second responses (~0.5s - 0.8s).
  - **Fallback:** Google Gemini API (`gemini-3.5-flash-lite`), automatically triggered if Groq fails, times out, or lacks an API key.
- **Network Layer:** Python standard library `urllib.request` with forced IPv4 resolution (avoiding Wayland/systemd IPv6 DNS lookup latency).
- **Execution Concurrency:** Non-blocking asynchronous Qt worker (`APIWorker` in `QObject` with daemon `threading.Thread`) emitting signals (`finished`, `error`) to preserve 60fps UI responsiveness.
- **Multi-Turn Conversation Engine:**
  - `core/api_client.py`: Request payloads serialize conversational `history` into Groq (OpenAI-compatible) and Gemini (`contents`) schemas.
  - `core/config.py`: Configurable `MAX_FOLLOWUP_TURNS` (default: 3, clamped 1–10).
  - `ui/capsule.py`: Thread state isolation per capsule (`_chat_history`, `_turn_count`).
  - `ui/result_view.py`: Dedicated follow-up input bar (`#FollowUpInput`), turn counter badge (`#TurnBadge`), and shortcut isolation preventing collision between letter typing and action shortcuts.
- **Decoupled System Prompts (`execution/DEFAULT.md` & `execution/commands/*.md`):**
  - All AI personas are externalized markdown files with frontmatter-style metadata.
  - `execution/DEFAULT.md` configures the default behavior when no slash command is used.
  - Modular slash commands (`ask.md`, `eva.md`, `trans.md`) dynamically populate `/help` and autocomplete dropdowns.
- **Configuration & Security:**
  - Lookup order: `~/.config/cask/config.env` -> `config.env` -> `.env`.
  - Permissions: strictly `chmod 600` (read/write by owner only).
  - Excluded from version control via `.gitignore`.

---

## 2. Multi-Window Concurrent Architecture (Up to 3 Windows)

CAsk supports up to **3 concurrent independent capsules** arranged in a horizontal grid. The layout dynamically adapts based on the active window count:

```mermaid
stateDiagram-v2
    [*] --> 1_Window: Launch cask (W1)
    1_Window --> 2_Windows: Hotkey / Terminal Launch (adds W2)
    2_Windows --> 3_Windows: Hotkey / Terminal Launch (adds W3)
    3_Windows --> 3_Windows: Subsequent Launch (focuses active)
    3_Windows --> 2_Windows: Close W3 / W2 / W1
    2_Windows --> 1_Window: Close W2 / W1
    1_Window --> [*]: Close last window
```

### Layout Distribution Rules:

| Active Count | Screen Width Coverage | Slot 0 (Left) | Slot 1 (Center) | Slot 2 (Right) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1 Window** | Standard (600 / 760px) | — | $W_1$ (Centered) | — | Single centered card horizontally & vertically. |
| **2 Windows** | **80% of Screen Width** | $W_1$ (50% of 80%) | — | $W_2$ (50% of 80%) | 2 cards side-by-side with equal width, centered. |
| **3 Windows** | **100% Full Screen Width** | $W_3$ (**30%**) | $W_1$ (**40%**) | $W_2$ (**30%**) | 3 cards with ratio **30 : 40 : 30**. $W_1$ stays in center. |

- **Opening Flow:** Opening $W_1$ centers it. Opening $W_2$ shifts $W_1$ to the left and adds $W_2$ to the right (80% screen). Opening $W_3$ adds $W_3$ to the far left, placing $W_1$ in the center and $W_2$ on the right (full screen 30:40:30).
- **Closing Flow:** Closing any capsule smoothly shifts remaining capsules to the corresponding $N=2$ or $N=1$ layout. Closing the last capsule exits the application.

---

## 3. Capsule Interaction Lifecycle & State Machine

Each capsule (`CAskCapsule`) operates its own isolated state machine:

```mermaid
stateDiagram-v2
    [*] --> InputState: Launch capsule
    InputState --> LoadingState: Submit query / command
    InputState --> SettingsState: Settings button ⚙ / [Ctrl + ,]
    SettingsState --> InputState: Apply / Close / Esc
    InputState --> ResultState: /help, invalid cmd, missing arg (0ms token-free)
    InputState --> [*]: Escape / Empty input
    LoadingState --> ResultState: API response (Groq / Gemini)
    LoadingState --> ResultState: API error / timeout
    ResultState --> InputState: Ask button / Key [Shift + A]
    ResultState --> [*]: Escape / Enter / Outside click (unpinned)
```

### State Breakdown:

1. **State 0: Input State (`STATE_INPUT`)**
   - **Dynamic Height Auto-Expansion:** Minimum 50px (single line baseline) up to 220px (clamped max height). Automatically resizes to fit multiple lines and wrapped text.
   - **Multiline Editing:** Pressing <kbd>Shift</kbd>+<kbd>Enter</kbd> inserts a newline. Pressing <kbd>Enter</kbd> submits.
   - **Scrollbar Behavior:** Scrollbar is strictly hidden on single lines and empty text (`ScrollBarAlwaysOff`), activating as needed only when reaching 220px.
   - **Autocomplete:** Typing `/` opens a `QCompleter` dropdown displaying registered commands (`/help`, `/ask`, `/check`, `/eva`, `/trans`).
   - **Settings Shortcut & Button:** Integrated gear button `⚙` on the right side and <kbd>Ctrl</kbd> + <kbd>,</kbd> shortcut triggers `STATE_SETTINGS`.
   - **Focus Retention:** Persistent across focus loss; users can click background windows without dismissing the input bar.

2. **State 1: Loading State (`STATE_LOADING`)**
   - **Dimensions:** 54px height.
   - **Styling:** Semi-transparent glass capsule with animated dots and custom loading label.
   - **Focus Retention:** Persistent during background API queries; does not dismiss when user interacts with background windows.

3. **State 2: Result State (`STATE_RESULT`)**
   - **Dimensions:** Elastic height calculated from markdown document geometry (min 190px up to 840px max).
   - **Header Action Bar:**
     - **Drag Handle (`#DragHandle`):** SVG 6-dot grip icon `⋮⋮` allowing drag-and-drop window reordering with live drop preview and tooltip indicating `[Alt + ← / →]`.
     - **Status Badge:** Identifies result type (e.g. `Help`, `/ask`, `/check`, `/eva`, `/trans`, `Assistant`).
     - **Ask (`#AskButton`):** SVG magnifying glass icon + `Ask` (Shortcut: <kbd>Shift</kbd> + <kbd>A</kbd>). Switches back to the input bar to refine or submit a new query.
     - **Copy (`#CopyButton`):** SVG clipboard icon + `Copy` (Shortcut: <kbd>Shift</kbd> + <kbd>C</kbd> / <kbd>Ctrl</kbd> + <kbd>C</kbd>). Copies full markdown to clipboard with temporary `✓ Copied!` confirmation.
     - **Pin (`#PinButton`):** SVG pushpin icon + `Pin` / `Pinned` (Shortcut: <kbd>Shift</kbd> + <kbd>P</kbd>). Toggles window pinning.
     - **Exit (`#ExitButton`):** SVG cross `✕` icon + `Exit` (Shortcut: <kbd>Esc</kbd>). Dismisses the card.
   - **Multi-Turn Follow-Up Footer Bar:**
     - **Follow-up Input (`#FollowUpInput`):** Translucent input bar embedded at the bottom of the card for follow-up questions within the active capsule context.
     - **Turn Counter Badge (`#TurnBadge`):** Real-time indicator displaying `(current_turn / max_turns)`.
     - **Turn Limit Enforcement:** Automatically locks input and displays guidance when reaching `MAX_FOLLOWUP_TURNS` (default 3, clamped 1–10).
     - **Shortcut Guarding:** When focused in the follow-up input bar, typing uppercase letters (<kbd>Shift</kbd> + <kbd>A</kbd>, <kbd>Shift</kbd> + <kbd>P</kbd>, <kbd>Shift</kbd> + <kbd>C</kbd>) is safely preserved without triggering window shortcuts.
   - **Window Reordering Shortcuts:** <kbd>Alt</kbd> + <kbd>←</kbd> and <kbd>Alt</kbd> + <kbd>→</kbd> swap the focused capsule with its adjacent left/right slot while preserving predefined slot geometry ratios (e.g., 30 : 40 : 30). This functions seamlessly in both the **Input Bar** (without conflicting with text selection/highlighting) and the **Result Box**.
   - **Pinning Rules:** When pinned (`is_pinned == True`), the card **cannot** be dismissed by clicking outside, pressing <kbd>Esc</kbd>, or pressing <kbd>Enter</kbd>. It can only be dismissed via the Exit button or by unpinning.

4. **State 3: Settings State (`STATE_SETTINGS`)**
   - **Dimensions:** Smooth 460px height.
   - **Model Pipeline Cards:** Modular cards representing Groq Cloud, Google Gemini, and 9Router / Custom OpenAI.
   - **Reordering & Priority:** Interactive Up/Down buttons (`▲` `▼`) configure primary and fallback fallback ranking.
   - **Live Connectivity Test:** `⚡ Test` button pings the provider asynchronously and reports latency without blocking the UI.
   - **Hot-Reloading:** Saving writes atomically to `~/.config/cask/config.env` and instantly updates runtime configuration across active capsules.

---

## 4. Technical Solutions & Wayland Optimizations

### 📌 Solution 1: Unified Window Masking for Multi-Window Precision
- **Challenge:** Under Wayland (`xdg_shell`), client applications cannot programmatically set window coordinates (`move()` / `setGeometry()` are ignored by KWin). Creating 3 separate OS-level windows causes KWin to cascade them unpredictably.
- **Solution:** A single screen-covering frameless transparent `MainWindow` orchestrates child `CAskCapsule` widgets with pixel-perfect coordinates. Using `setMask(QRegion)`, transparent spaces between and around cards are excluded from input regions, allowing clicks to pass through directly to background applications.

### 📌 Solution 2: Resolution-Independent SVG Vector Icons
- **Challenge:** Emoji characters (e.g. 📌, 🔍) frequently fail to render or show as missing glyph boxes on Linux distributions lacking emoji fonts or using monospace fonts (`JetBrains Mono`).
- **Solution:** Integrated `ui/icons.py` using `QSvgRenderer` to render crisp vector icons directly into `QIcon` objects with exact Catppuccin-inspired theme colors (`#e6ebf5`, `#f9e2af`, `#89b4fa`).

### 📌 Solution 3: Keyboard Shortcut Interception via Event Filter & Dynamic Reordering
- **Challenge:** `QTextBrowser` absorbs focus in the result view; default key handlers in parent frames would not fire for unhandled keys. Additionally, using Shift+Arrow inside `QTextEdit` triggered text highlighting instead of swapping windows, and users required the ability to swap window positions dynamically without losing predetermined geometry ratios.
- **Solution:** Installed an event filter on `QTextBrowser` and child controls in `ResultView`, `InputBar`, and `MainWindow` that intercepts:
  - <kbd>Shift</kbd> + <kbd>A</kbd>: Return to input bar.
  - <kbd>Shift</kbd> + <kbd>P</kbd>: Toggle pin status.
  - <kbd>Shift</kbd> + <kbd>C</kbd> / <kbd>Ctrl</kbd> + <kbd>C</kbd>: Copy markdown output.
  - <kbd>Alt</kbd> + <kbd>←</kbd> / <kbd>Alt</kbd> + <kbd>→</kbd>: Move/swap active capsule slot left or right (operates in both InputBar and ResultView without conflicting with text selection).
  - <kbd>Alt</kbd> + <kbd>H</kbd>: Toggle Always-on-Top / window stacking (unhide / hide from top layer across both InputBar and ResultView).
  - Interactive mouse dragging on `#DragHandle` (`⋮⋮`) with `DropGhostIndicator` providing live visual target slot feedback and ratio recomputation.
  - <kbd>Esc</kbd> / <kbd>Enter</kbd>: Dismiss unpinned cards.

### 📌 Solution 4: Elimination of Premature Scrollbar on Line 1
- **Challenge:** `QTextEdit` with `ScrollBarAsNeeded` on small initial heights caused sub-pixel document margins to trigger a vertical scrollbar even on empty or single-line text.
- **Solution:** Configured `setDocumentMargin(2)` and locked `ScrollBarAlwaysOff` while height < 220px. Switched to `ScrollBarAsNeeded` only when reaching maximum clamped height.

### 📌 Solution 5: Single-Instance HUD Enforcement & IPC Launch Routing
- **Implementation:** Implemented `ui/single_instance.py` using kernel file locking (`fcntl.flock`) on `f"{app_name}_{uid}.lock"` and `QLocalServer`. Subsequent invocations transmit `ACTIVATE:<query>` over IPC, invoking `MainWindow.handle_external_launch(query)` to spawn card 2 or 3.

### 📌 Solution 6: Universal Linux Vietnamese IME Compatibility & Instant Composition Expansion
- **Challenge:** Under Wayland, PyQt6 wheels bundled via pip lack `libfcitx5platforminputcontextplugin.so` (present only in system Qt), causing Qt6 to reject `QT_IM_MODULE=fcitx` and fall back to raw Compose (disabling Vietnamese IME such as `fcitx5-bamboo`). Additionally, missing `inputMethodEvent` / `inputMethodQuery` overrides in custom `QTextEdit` subclasses breaks surrounding-text diacritic transformation. Furthermore, during Vietnamese composition (e.g. typing a multisyllabic or accented word before pressing Space), uncommitted characters reside exclusively in IME `preeditString`. Evaluating height based solely on `toPlainText()` caused the input bar to defer line expansion until a space committed the word.
- **Solution:** 
  - Implemented `configure_linux_ime()` in `ui/app.py`: auto-detects running IME daemons (`fcitx5` / `ibus`) and automatically redirects to `ibus` emulation when `fcitx5` plugin is missing in the wheel.
  - Enabled `Qt.WidgetAttribute.WA_InputMethodEnabled` and `Qt.InputMethodHint.ImhNone` on `InputBar`.
  - Implemented explicit `inputMethodEvent` and `inputMethodQuery` delegation on `InputBar` to guarantee smooth accent composing.
  - Integrated real-time preedit string tracking in `InputBar`: cloned document geometry injects active `_preedit_text` at cursor position, causing the input bar to immediately expand the moment the composed word wraps to a new line without requiring a trailing space.

### 📌 Solution 7: Dynamic Compositor Stacking & Flicker-Free Layer Switching (<kbd>Alt</kbd> + <kbd>H</kbd>)
- **Challenge:** On Wayland (KWin / KDE Plasma 6), calling `setWindowFlags()` on a live window recreates the native `wl_surface`, triggering compositor fade animations, destroying `setMask()` bounds, and failing to lower the window due to `xdg_shell` client-lowering restrictions. Furthermore, hardcoded `kwinrulesrc` rules with `aboverule=3` ("Force Keep Above") previously overrode any application-level stacking change. Additionally, under Wayland `xdg_toplevel`, `Qt.WindowType.WindowStaysOnTopHint` is ignored by KWin upon initial window mapping (`initial_keepAbove=false`), and Wayland surface registration in KWin's `workspace.windowList()` occurs asynchronously (~30-50ms after `show()`), causing CAsk to lose always-on-top on launch until explicitly toggled via Alt+H.
- **Solution:** 
  - Purged hardcoded forced `aboverule=3` rules from `install.sh` and user configuration.
  - Implemented dynamic KWin scripting layer switching in `MainWindow`: commands KWin's compositor directly via DBus (`org.kde.KWin /Scripting`) to toggle `keepAbove` and `keepBelow` (`w.keepAbove = false; w.keepBelow = true;`).
  - Proactive Launch-Time Enforcement (`_apply_initial_layer`): Triggered via `showEvent` and `handle_external_launch` with stepped retry backoff (40ms, 80ms, 160ms, 300ms, 500ms) to guarantee that as soon as KWin maps the asynchronous Wayland surface, `w.keepAbove = true` is immediately enforced without requiring manual toggle.
  - Achieves instant, flicker-free window ranking behind all standard application windows without surface destruction or window mask disruption. Cross-platform fallback via `WindowStaysOnBottomHint` handles non-KDE environments.

### 📌 Solution 8: Multi-Turn Conversation History Isolation, Thread Safety & Command Routing
- **Challenge:** Lightweight HUD cards risk layout overflow or sluggishness if conversational threads grow without bound. Furthermore, transitioning to a full loading state between follow-up questions collapses and expands window geometry (54px to 800px), causing severe visual jitter. Additionally, calling methods like `isRunning()` on C++ `QThread` wrappers deleted prematurely by Qt's event loop caused fatal SIGABRT crashes (`RuntimeError: wrapped C/C++ object of type APIWorker has been deleted`). Furthermore, pressing <kbd>Enter</kbd> to submit a follow-up query inadvertently bubbled up to `MainWindow.keyPressEvent`, dismissing unpinned cards. Lastly, users required slash command routing and autocomplete within the response box follow-up bar with distinct visual highlighting for their follow-up questions.
- **Solution:** 
  - **Isolated Thread State:** Maintained per-capsule `_chat_history` in `CAskCapsule`. Opening card 2 or 3 retains separate independent contexts.
  - **In-Place Progress State:** During follow-up query execution, the card remains in `STATE_RESULT`, disabling `#FollowUpInput` and setting `#TurnBadge` to `(thinking)`. Previous conversation text remains fully visible and legible, eliminating height collapsing.
  - **Thread Safety & Crash Elimination (QObject Daemon Worker):** Refactored `APIWorker` from a `QThread` subclass to a `QObject` with Qt signals running on a Python daemon `threading.Thread(daemon=True)`. Eliminated Qt C++ fatal crashes (`qFatal("QThread: Destroyed while thread is still running")` / `_ZN10sipQThreadD0Ev` / `SIGABRT`) when workers are overwritten or deallocated during prompt submissions or follow-ups. Added `is_worker_active()` with `sip.isdeleted()` checks and `RuntimeError` guards. Controlled joining (`stop_worker()`) terminates running workers safely on capsule close or query reset.
  - **Enter Key Decoupling & Input Focus:** Completely eradicated <kbd>Enter</kbd> / <kbd>Return</kbd> from closing or dismissing CAsk. Instead, pressing <kbd>Enter</kbd> while viewing responses or when focus is outside editable input fields instantly focuses the input bar (`#FollowUpInput` in `ResultView`, `#InputBar` in input state).
  - **Full Slash Command Support in Follow-Up Bar:** Integrated `CommandCatalog` and `QCompleter` into `ResultView`'s `#FollowUpInput`. Routed follow-up inputs through `route_input`: dynamically adopting command system prompts (e.g. `/trans`, `/eva`), providing instant token-free `/help`, and highlighting active command tokens (`is_command="true"`).
  - **Yellow Follow-up Turn Highlighting:** Formatted user follow-up questions with Catppuccin Yellow `.user-turn` (`#f9e2af`) with left accent border and translucent backdrop, while preserving standard clean markdown formatting when copying to the system clipboard.
  - **Cross-Backend Serialization:** `core/api_client.py` serializes `history` seamlessly into Groq's OpenAI-compatible message list (`[{"role": "user"|"assistant", "content": ...}]`) and Gemini's hierarchical `contents` (`[{"role": "user"|"model", "parts": [...]}]`).
  - **Configurable Clamping:** Bounded by `MAX_FOLLOWUP_TURNS` (default 3, clamped 1–10). Preserves the single-card transient HUD philosophy while enabling multi-turn follow-up workflows.

### 📌 Solution 9: Unified Code Block Rendering & Corner Transparency Artifact Removal
- **Challenge:** 
  1. In `QTextBrowser`, block elements like `<pre>` with `background-color` or `border` are parsed into separate `QTextBlock`s per newline. Because Qt's rich text engine does not support descendant CSS selectors (such as `pre code`), `<code>` styles bled into `<pre>`, rendering code blocks as disconnected, striped individual lines with jarring gaps between lines instead of a single solid block.
  2. All three window capsules (Input bar, Loading bar, Response box) exhibited square gray corners protruding behind the rounded glassmorphic edges.
- **Solution:**
  - **Solid Code Block Container (`core/markdown_renderer.py`):** Transformed fenced and block code into single-cell `<table class="code-block" ... bgcolor="#11111b">` wrappers containing `<pre>`. Qt renders the table cell as a single cohesive solid background with rounded borders and padding. Converted inline code to `<span class="inline-code">`, keeping inline code backgrounds distinct from block code.
  - **Corner Artifact Elimination (`ui/capsule.py` & `ui/main_window.py`):** Identified `QGraphicsDropShadowEffect(self.container)` as the root cause of the square gray corner protrusion, where Qt computed an offscreen blur convolution against the rectangular bounding frame of `QFrame`. Removed the shadow effect and enforced `WA_TranslucentBackground` on `CAskCapsule` and `CentralContainer`. Tightened `card_rect` mask bounds in `MainWindow._recompute_layout` to produce crisp, anti-aliased rounded corners without rectangular bleeding.

### 📌 Solution 10: Objective Verification & Counter-Argument Command (`/check`)
- **Requirement:** Introduce a dedicated `/check <statement>` command to critically challenge premises, verify factual accuracy, and expose logical fallacies, unstated assumptions, and edge cases.
- **Implementation:**
  - **Template Specification (`execution/commands/check.md`):** Configured modular prompt with dual-language structure (Vietnamese and English) matching the user input language. Instructs the LLM to deliver zero conversational fluff, an objective preliminary verdict, categorized logical flaws/fallacies, empirical counter-examples, and a calibrated refined proposition.
  - **Dynamic Routing & Loading:** Registered seamlessly into `CommandCatalog`, `core/router.py`, and `QCompleter` autocompletion without code modifications to core routing logic.
  - **Symlink Management (`install.sh`):** Added dangling symlink pruning (`find ... -xtype l -delete`) before copying or symlinking execution templates to guarantee idempotent installation across renames or directory changes.

### 📌 Solution 11: In-HUD Model Settings Panel & Provider Pipeline (`STATE_SETTINGS`)
- **Requirement:** Allow users to interactively configure, test, enable/disable, reorder, create, and delete response models via GUI without manually editing `config.env`.
- **Implementation:**
  - **In-Capsule State Transition (`STATE_SETTINGS`):** Flipped active capsule to settings mode upon clicking the input bar gear icon `⚙` or pressing <kbd>Ctrl</kbd> + <kbd>,</kbd>. Preserves single-window geometry and Wayland `setMask` bounds without secondary popup dialog issues.
  - **Dynamic Model Cards (`ui/settings_view.py`):** Each `ModelCardWidget` exposes display name, protocol (`openai_compatible` / `gemini`), base URL, model ID, API key, and enabled toggle. Existing `temperature` and `max_tokens` metadata is preserved on save without GUI editors; request temperature remains fixed at `0.2`. Cards support:
    - **Add:** `Add Model Card` button with a single plus icon creates new cards from preset templates (Groq, 9Router, Gemini, DeepSeek, Ollama, Custom Endpoint).
    - **Delete:** Trash button removes cards (disabled when only 1 card remains).
    - **Reorder:** Up/Down arrow buttons (`▲` `▼`) configure primary and fallback ranking with live priority badge refresh (`[Primary]`, `[Fallback N]`, `[Inactive]`).
    - **Edit:** Inline name editing, protocol selector, editable model combo with preset suggestions, and password reveal toggle (`👁`).
  - **Asynchronous Live Ping Test (`⚡ Test`):** Runs minimal ping prompt in daemon thread to measure roundtrip latency in real-time (`✓ 0.62s`) without blocking the Qt event loop.
  - **Structured Persistence (`core/model_config.py`):**
    - **`models.json`:** Primary configuration file at `~/.config/cask/models.json` storing the full model pipeline as a JSON array of `ModelEntry` objects.
    - **Migration Fallback:** When `models.json` does not exist, entries are auto-synthesized from legacy `config.env` variables (`GROQ_API_KEY`, `GEMINI_API_KEY`, `CUSTOM_OPENAI_*`, `PROVIDER_ORDER`).
    - **Backward Compatibility Sync:** On save, primary keys (`GROQ_MODEL`, `GEMINI_MODEL`, `PROVIDER_ORDER`, etc.) are written back to `config.env` for legacy compatibility.
  - **Hot-Reloading (`core/config.py`):** `save_config_file()` atomically writes key updates to `~/.config/cask/config.env` while preserving comments, immediately hot-reloading runtime `Config` across all active capsules.
  - **Built-in Presets (`core/model_config.py` → `PRESETS`):** Catalog of provider templates (Groq Cloud, 9Router, Google Gemini, DeepSeek API, Ollama Local, Custom) with default URLs, model IDs, and suggested model lists.

### Solution 12: Model Settings Interaction Fixes (2026-11-13)
- **Scope:** Prevent accidental dropdown changes, simplify action labels, and resolve connection tests remaining at `Testing...`.
- **Implementation (`ui/settings_view.py`):**
  - `WheelSafeComboBox` handles protocol, model ID, and preset dropdowns. Wheel events over closed controls, including the editable model field, are forwarded to the nearest `QScrollArea`; selection requires explicit keyboard or popup interaction.
  - The apply button reads `Apply`. `Add Model Card` retains its plus icon and omits the redundant plus in its text.
  - Connection tests retain the background daemon thread and the existing eight-second network timeout. `connection_test_finished` uses a queued Qt signal to deliver results to `_apply_test_result` on the GUI thread, replacing the worker-thread `QTimer.singleShot` callback that could remain undelivered.
  - Provider failures and unexpected exceptions update the result label and re-enable testing. Tooltips expose full error text. Results emitted after card deletion are safely discarded.
  - Removed the duplicate `ModelCardWidget` constructor and signal declarations.
- **Verification:** All 58 core/UI tests passed headlessly with a temporary `XDG_RUNTIME_DIR`. `tests/test_settings_view.py` covers focused/unfocused wheel input, editable fields, panel scrolling, popup/keyboard selection, queued results, success/failure/timeout/retry, and deletion during a request. The existing reorder test now supplies its own three-model fixture instead of depending on personal configuration. Connection responses were mocked; live provider credentials were not exercised.
- **UI Review:** The original stylesheet kept `#SettingsView` transparent while cards had their own backgrounds, leaving outer text dependent on the desktop behind it. The user approved a continuous dark panel (`#1b1f26`), lighter cards (`#262d38`), darker inputs, and brighter secondary labels. Solution 13 applies this theme.
- **Resource Organization (2026-11-13):** Bug screenshots were moved from `bug_screenshots/` to `resources/bug_screenshots/` and remain ignored by Git. The proposed UI preview is tracked at `resources/references/model-settings-proposed.png` and linked from `README.md`, replacing reliance on a temporary preview path.

### Solution 13: Approved Settings Theme and Transparent Rounded Corners (2026-11-13)
- **Theme (`ui/styles.qss`):** `#SettingsView` paints an opaque `#1b1f26` surface with a `#454b56` border and 14px radius. Cards use `#262d38` with 10px corners. Subtitle and field labels use `#bbc4d6`. Existing input styling, layout, and settings height remain unchanged.
- **Painting (`ui/settings_view.py`):** `SettingsView` explicitly enables `WA_StyledBackground` and disables automatic palette filling. Its rounded QSS surface is painted inside the existing translucent `MainWindow`, `CAskCapsule`, and `CentralContainer` hosts. Do not add a rectangular background to those hosts or set `WA_TranslucentBackground` on the styled child panel; the latter suppresses its background painting in the tested Qt setup.
- **Reference Capture:** A normal top-level Qt frame fills its rectangular window background behind rounded QSS borders. The original reference had alpha 255 at all four outer corners. The updated `resources/references/model-settings-proposed.png` is rendered with the application stylesheet inside a frameless translucent host and has alpha 0 at all four corners, while the panel interior remains opaque. It uses an 800x620 preview size and placeholder endpoints without credentials.
- **Verification:** All 59 tests passed headlessly with a temporary `XDG_RUNTIME_DIR`. The rendering regression test samples all four outer corners and header/footer background pixels in `MainWindow` across two Settings/Input cycles. It also passed with `QT_SCALE_FACTOR=2`. Native compositor appearance was not exercised by these offscreen tests.

---

### Solution 14: Provider-First UI Mockups (2026-11-13)
- **Accepted Design Direction:** Provider cards own connection details and multiple saved model configurations. Exactly one model configuration is active per provider, with quick switching between saved configurations. The user requested mockups before implementation.
- **Artifacts (`resources/references/`):** `provider-settings-mockup.png` shows an expanded OpenAI provider with Sol Medium/Sol High configurations and a collapsed Groq provider. `provider-model-picker-mockup.png` shows catalog search and configuration fields. `provider-quick-switch-mockup.png` places provider/model selection buttons and a gear settings button below query input; the send button uses a right-arrow icon. This revised layout follows the user's requested mockup correction. `README.md` links and explains all references.
- **Reproducibility:** Run `QT_QPA_PLATFORM=offscreen python3 resources/references/generate-provider-mockups.py`. The renderer uses only placeholder data, does not load credentials, and checks transparent outer corner pixels. All three views were rendered and visually inspected.
- **Implementation Boundary:** These are presentation-only references; the application's model-entry schema, settings controls, routing, and discovery behavior have not changed. Provider fallback order is illustrated as a proposal. Catalog integrations, parameter compatibility, persistence, and final HUD scrolling still require implementation and review.

## 5. Project Directory Layout

```
cask/
├── assets/                    # Project visual assets & branding
│   └── logo.png               # Official CAsk application logo
├── resources/                 # Bug screenshots and design references
│   ├── bug_screenshots/       # Local bug screenshots (ignored by Git)
│   └── references/            # Tracked UI design references
│       └── model-settings-proposed.png
├── cask.py                    # Main executable entrypoint (CLI & PyQt6 HUD)
├── core/                      # Application core logic & network engine
│   ├── __init__.py            # Core package exports
│   ├── config.py              # Environment configuration loader & atomic env writer
│   ├── model_config.py        # Dynamic ModelEntry dataclass, presets, JSON persistence & migration
│   ├── command_loader.py      # Modular slash command scanner & parser
│   ├── router.py              # Deterministic regex router & argument validator
│   ├── math_formatter.py      # LaTeX mathematical formula to Unicode converter
│   └── api_client.py          # Groq, Gemini & Custom OpenAI client with pipeline fallback
├── ui/                        # PyQt6 user interface layer
│   ├── __init__.py            # UI package exports
│   ├── app.py                 # QApplication lifecycle, fonts, stylesheet loader
│   ├── capsule.py             # Independent CAsk interactive card (Input, Loading, Result, Settings)
│   ├── icons.py               # SVG vector icon generators (Ask, Copy, Pin, Exit, Gear, Arrows, Test)
│   ├── single_instance.py     # Kernel file lock & QLocalServer IPC manager
│   ├── main_window.py         # Multi-capsule orchestrator, slot layout, setMask
│   ├── input_bar.py           # Auto-expanding dynamic input bar with settings button & token highlighting
│   ├── loading_indicator.py   # Animated request indicator
│   ├── result_view.py         # Markdown browser with action buttons & keyboard shortcuts
│   ├── settings_view.py       # Model pipeline settings HUD with live ping test & reordering
│   └── styles.qss             # Glassmorphism dark stylesheet
├── execution/                 # Prompt definitions & command templates
│   ├── DEFAULT.md             # Customizable default prompt (used when no slash command is given)
│   ├── GUIDE.md               # Command authoring guide and best practices
│   └── commands/              # Modular slash command prompts
│       ├── ask.md             # /ask bilingual explanation prompt
│       ├── check.md           # /check objective critique and counter-argument prompt
│       ├── eva.md             # /eva grammar and phrasing critique prompt
│       └── trans.md           # /trans English/Vietnamese translation prompt
├── tests/                     # Automated test suite
│   ├── test_core.py           # Unit tests for core router, loader, config
│   └── test_ui.py             # Headless offscreen PyQt6 UI tests
├── install.sh                 # System installer & desktop entry setup
└── README.md                  # User documentation
```

---

## 6. Verification & Testing

The test suite validates core router logic, multi-capsule layout geometry, dynamic height calculations, pinning, and UI shortcuts:

```bash
python3 -m unittest discover tests
```
