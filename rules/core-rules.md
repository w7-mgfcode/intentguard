# Core rules

**Purpose:** Define the invariants that make FPAT Lite reliable.

**Intended reader:** Every human or agent using the toolkit.

**Consult this when:** Before substantial analysis, planning, implementation,
validation, or handoff.

## Invariants

1. **Read repository instructions before editing.**
2. **Inspect before changing.** Understand current code, tests, configuration,
   Git state, and relevant user changes.
3. **State assumptions when evidence is incomplete.** Do not present inference
   as fact.
4. **Research material uncertainties before implementation.** Prefer official
   documentation and primary sources for current technical behavior.
5. **Prefer the simplest adequate solution.** Complexity must solve an observed
   requirement.
6. **Do not perform unrelated refactoring.**
7. **Define acceptance criteria before substantial implementation.** Criteria
   must be observable or testable.
8. **Never claim that an unexecuted test passed.**
9. **Distinguish local file mutations from remote system mutations.**
10. **Require explicit approval before external GitHub writes** unless the
    user's current request clearly authorizes the exact write.
11. **Review the final diff.**
12. **Create a handoff when work is incomplete, context is becoming large, or
    another session must continue.**
13. **Preserve existing repository conventions unless a change is justified.**
14. **Avoid destructive actions unless explicitly requested and safely scoped.**
15. **Stop and report contradictions rather than silently choosing a risky
    interpretation.**

## Proportionality rule

Use only the ceremony that reduces actual risk:

- Tiny, obvious change: prime briefly → implement → validate.
- Ambiguous change: prime → brainstorm → plan → implement → validate.
- Pause or transfer: add handoff.

Do not create artifacts merely to prove that a process was followed.

## Precedence

System and platform policy outrank repository instructions. Explicit current
user instructions outrank general project preferences when they do not violate
policy or safety. Narrower repository rules may refine broader rules. If two
applicable instructions conflict materially, stop and surface the conflict.

