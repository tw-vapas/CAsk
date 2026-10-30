# Agent Rules & Instructions for CAsk

## 1. Language & Communication Standards
- **English-Only Policy:** All project assets—including codebase, comments, documentation (`README.md`, `context.md`), commit messages, command prompts, and technical notes—must be written strictly in **English**.
- **Agent-First Optimization (Machine-Parsable Style):**
  - Prioritize high information density, structural clarity, and unambiguous phrasing.
  - Avoid conversational filler, fluff, and unnecessary pleasantries.
  - Use structured formats (Markdown headers, tables, bulleted lists, and explicit code blocks).
  - Explicitly specify file paths, commands, input/output schemas, and edge-case boundaries.
- **Proactive Clarification Policy:**
  - Whenever requirements, behaviors, edge cases, or design specifications are unclear, underspecified, or ambiguous, you **MUST explicitly ask the user for clarification** before proceeding or building.
  - Never make arbitrary assumptions or implement unverified guesswork on unspecified requirements.

## 2. Git Commit & Push Rules
1. **Auto-commit after changes:** Automatically stage and commit changes to git immediately upon completing code or documentation modifications.
2. **Atomic Commits (Split by logical change):**
   - Never bundle unrelated changes into a single monolithic commit.
   - Split commits logically (e.g., separate commits for router script logic, individual command prompts, and documentation).
3. **Descriptive & Conventional Commit Messages:**
   - Use Conventional Commits format (`feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `chore: ...`).
   - Commit titles must be concise, accurate, and written in English.
   - Clearly convey the intent and scope of each change.
4. **Auto-push after requirement completion:**
   - Automatically execute `git push` to push all committed changes to the remote repository immediately upon completing each user requirement or task session.
