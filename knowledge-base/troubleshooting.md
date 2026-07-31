# Troubleshooting

**Purpose:** Recover from discovery, instruction, validation, and handoff
problems without widening scope.

**Intended reader:** Users and coding agents.

**Consult this when:** FPAT Lite is ignored, conflicts appear, or a command
cannot complete safely.

## Codex does not show `$fpat-lite`

1. Confirm the repository contains
   `.agents/skills/fpat-lite/SKILL.md`.
2. Start Codex in the repository or a descendant directory.
3. Inspect the current skill list or mention `$fpat-lite` explicitly.
4. Restart the session if a recently added skill is not visible.
5. Use the portable fallback: read `AGENTS.md`, then the desired command file.

Do not copy the skill into an undocumented `.codex/` path.

## Claude Code does not show `/fpat-lite`

1. Confirm `.claude/skills/fpat-lite/SKILL.md` exists.
2. Start Claude Code inside the repository.
3. Use `/context` to confirm `CLAUDE.md` loaded.
4. Check that `CLAUDE.md` imports `@AGENTS.md`.
5. Invoke `/fpat-lite prime` directly or restart if discovery is stale.

## Shared instructions conflict

1. Run `prime` and list every active instruction source.
2. Identify the exact conflicting statements and their scope.
3. Apply platform/system precedence first.
4. Prefer the narrower repository rule only when it does not weaken safety.
5. Stop and ask when the conflict changes public behavior or mutation authority.
6. Remove duplication instead of adding a third interpretation.

## Prime cannot access GitHub

Continue with local instructions, Git state, code, and existing handoffs.
Classify GitHub state as unavailable. Do not authenticate, install a token, or
claim live issue/PR state unless the user asks and authority permits it.

## A validation command is missing

- Search the repository README, build metadata, CI, and existing scripts.
- Mark the check unavailable if the tool or service is absent.
- Do not install a new framework merely to validate a small change.
- Use a smaller direct smoke test only when it proves the same criterion.

## Tests fail outside the changed area

Record the exact command and concise evidence. Check whether the failure is
reproducible on the unchanged baseline when that can be done safely. Do not fix
unrelated failures without expanding scope explicitly.

## The plan is too long

Return to the acceptance criteria. Merge steps that touch the same boundary and
share one validation result. Remove architecture, service, or documentation
work that does not affect the requested outcome. A two-file change usually
needs only a few steps.

## The handoff is stale

Do not execute its next action immediately. Run `prime`, compare live branch,
diff, files, validation, and remote state, then update the checkpoint. Reconfirm
remote approval if the target or consequences changed.

## Markdown links fail validation

Use paths relative to the document containing the link. Exclude web URLs and
same-document anchors from local path repair. Run:

```sh
sh scripts/validate-content.sh
```

The output names the source file and missing target.

## Bootstrap reports collisions

This is a safety feature. No file was copied. Review the listed target paths and
merge `AGENTS.md` or `CLAUDE.md` manually. Do not rename existing instruction
files solely to bypass the collision gate.

