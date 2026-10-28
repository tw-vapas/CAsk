# Command Development Guide

This guide establishes the specifications, file structure, and best practices for creating modular slash commands in Ctrans.

---

## 1. File Location & Naming Conventions

Command files are decoupled markdown files (`.md`) loaded dynamically by the Ctrans Bash Router.

### Directory Resolution
Commands are resolved in the following priority order:
1. **User Custom Commands:** `~/.config/ctrans/commands/{command_name}.md`
2. **Project Default Commands:** `commands/{command_name}.md` (in the repository)

### Naming Rules
- **Filename:** `{command_name}.md` (e.g., `ask.md`, `eva.md`, `code.md`).
- **Trigger:** The command is triggered in the input bar via `/{command_name}`.
- **Allowed characters:** Alphanumeric characters, hyphens, and underscores (`[a-zA-Z0-9_-]+`). Must be lowercase.
- **Reserved filenames:** `GUIDE.md`, `README.md` (these are ignored by the router and help catalog).

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

Ctrans renders responses inside a floating Rofi card (`THEME_RESULT`, max width 760px). Format your prompt outputs to ensure optimal readability:

1. **Zero Fluff Policy:**
   - Prohibit conversational filler (e.g., *"Sure, here is your explanation..."*).
   - Demand immediate, structured output.
2. **Bullet Points & Scannability:**
   - Use standard text bullets (`-` or `•`) for lists.
   - Use bold headers (`[Topic]`, `• Header:`) to delineate sections.
3. **Avoid Unsupported Elements:**
   - Do not request HTML tags or markdown tables (they do not render well in terminal-based Rofi textboxes).
   - Keep line length reasonable; auto soft-wrap breaks at 78 characters.
4. **Appropriate Length:**
   - Aim for 5–25 lines of response. Responses should be digestible in a 5-second popup glance.

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

1. User enters: `/{command_name} {payload}` in Rofi.
2. Ctrans regex extracts `COMMAND="{command_name}"` and `PAYLOAD="{payload}"`.
3. Ctrans verifies that `{command_name}.md` exists (excluding `GUIDE.md`).
4. Ctrans sets loading state to: `processing /{command_name}...`.
5. The full content of `{command_name}.md` is passed as `system` prompt, and `{payload}` is passed as `user` message.
6. The AI response is formatted and presented in the glassmorphism Rofi result modal.
