# Command Development Guide

This guide establishes the specifications, file structure, and best practices for creating modular slash commands in CAsk.

---

## 1. File Location & Naming Conventions

Command files are decoupled markdown files (`.md`) loaded dynamically by the CAsk Router.

### Directory Resolution
Commands are resolved in the following priority order:
1. **User Custom Commands:** `~/.config/cask/execution/commands/{command_name}.md`
2. **Project Default Commands:** `execution/commands/{command_name}.md` (in the repository)

### Naming Rules
- **Filename:** `{command_name}.md` (e.g., `ask.md`, `eva.md`, `code.md`).
- **Trigger:** The command is triggered in the input bar via `/{command_name}`.
- **Allowed characters:** Alphanumeric characters, hyphens, and underscores (`[a-zA-Z0-9_-]+`). Must be lowercase.
- **Reserved filenames:** `GUIDE.md`, `README.md`, `DEFAULT.md`.
  - `GUIDE.md` and `README.md` are documentation files.
  - `DEFAULT.md` (in `execution/DEFAULT.md`) configures the default assistant prompt executed when no slash command is used. It is excluded from the `/help` catalog and autocomplete. Users can edit `~/.config/cask/execution/DEFAULT.md` to customize the default persona (e.g. translator, coding assistant, or executive summarizer).

---

## 2. Required File Structure

Every command file must follow this exact structure:

```markdown
# /{command_name} <argument_hint> - {Concise Description}
<!-- Example: /{command_name} {Sample input} -->

{System Prompt Instructions}

Instructions:
1. {Rule 1}
2. {Rule 2}

Output Structure:
{Expected Output Format}
```

### Component Breakdown:

#### Line 1: Metadata Signature Header (Mandatory)
```markdown
# /{command_name} <argument_hint> - {Concise Description}
```
- **Syntax:** Must start with `# /` followed by the command name, parameter placeholder in `<...>`, hyphen `-`, and a brief summary.
- **Function:** Parsed automatically by `generate_help_text()` to populate `/help` and when user inputs empty arguments.
- **Example:**
  `# /ask <topic> - Bilingual concept explanation (EN + VI)`
  `# /eva <sentence> - Sentence evaluation, grammar critique, and native rephrasing`

#### Line 2: Usage Example Comment (Recommended)
```markdown
<!-- Example: /{command_name} {Sample input} -->
```
- **Syntax:** HTML comment starting with `<!-- Example:` and ending with `-->`.
- **Function:** Displayed in the error card when a user runs the command without any argument.
- **Example:**
  `<!-- Example: /ask Quantum computing -->`
  `<!-- Example: /eva I look forward to hear from you -->`

#### Line 3+: AI System Prompt (Mandatory)
- **Role & Persona:** Clear definition of the assistant's specialty (e.g., `You are an expert English language coach...`).
- **Execution Rules:** Unambiguous constraints (e.g., bilingual sections, strict step-by-step logic, zero pleasantries).
- **Output Format Specification:** Visual layout with explicit placeholders `{...}` and bullet formatting.

---

## 3. Best Practices for Command Output

CAsk renders responses inside a floating Glassmorphism HUD card with native Qt6 CommonMark rendering (`max width 760px`). Format your prompt outputs to ensure optimal readability:

1. **Zero Fluff Policy:**
   - Prohibit conversational filler (e.g., *"Sure, here is your explanation..."*).
   - Demand immediate, structured output.
2. **Bullet Points & Markdown Structure:**
   - Use standard Markdown (`#`, `##`, `-`, `*`) for headers and lists.
   - Code blocks with syntax highlighting (` ```python `) and inline code spans (`` `code` ``) are natively rendered.
   - Bold headers (`**Topic**`, `• Header:`) clearly delineate sections.
3. **Appropriate Length & Scannability:**
   - Aim for digestible responses that can be reviewed in a quick glance.
   - For longer responses, smooth mouse-wheel and touchpad scrolling are natively supported.

---

## 4. Complete Command Template

Copy and modify this template when creating a new command:

```markdown
# /summary <text_or_url> - Summarize text into 3 key takeaways
<!-- Example: /summary Paste article text here -->

You are an expert executive summarizer.
When given text or an article, distill the core insights into exactly 3 high-impact bullet points.

Instructions:
1. Extract the most critical ideas without omitting essential nuance.
2. Provide a 1-sentence bottom-line takeaway at the end.
3. Do not include introductory or concluding pleasantries.

Output Structure:
• Core Takeaways:
  - {Key point 1}
  - {Key point 2}
  - {Key point 3}

• Bottom Line:
{Single sentence actionable summary}
```

---

## 5. Execution Lifecycle

1. User enters: `/{command_name} {payload}` in the CAsk HUD or CLI.
2. CAsk router extracts `command="{command_name}"` and `payload="{payload}"`.
3. CAsk verifies that `{command_name}.md` exists in user config or defaults.
4. CAsk transitions to loading state: `processing /{command_name}...`.
5. The full content of `{command_name}.md` is passed as `system` prompt, and `{payload}` is passed as `user` message.
6. The AI response is streamed/rendered in the Glassmorphism Markdown viewer.
