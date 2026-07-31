@AGENTS.md

# Claude Code adapter

Claude Code reads this file and imports the root `AGENTS.md` as the only
repository instruction source. Do not duplicate or override those rules here.

- Invoke the project skill as `/fpat-lite <mode> [task]`.
- The skill lives at `.claude/skills/fpat-lite/SKILL.md`.
- Do not treat `.claude/commands/` as required; FPAT Lite uses the current
  skills format.
- Do not add `allowed-tools` to the skill without an explicit repository
  decision. The workflow must not silently grant itself permissions.
- Use `/context` to verify this file loaded if behavior appears inconsistent.
