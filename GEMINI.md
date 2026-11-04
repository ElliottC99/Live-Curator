# Compound Project - Agent Configuration

## Project Overview

This project implements the official **Compound Engineering Plugin** (`EveryInc/compound-engineering-plugin`) for Live Curator - a self-improving knowledge system based on the "Compounding Engineering" philosophy.

## Core Principle

> **Each unit of engineering work should make subsequent units of work easier—not harder.**

## Skills & Workflows Available

> **Full catalog:** Located in `.agent/skills/`.

Use these commands for systematic development:

| Command | When |
|---------|------|
| `/ce-ideate` | Early, expansive design exploration before requirements lock |
| `/ce-brainstorm` | Interactive dialogue to define what to build and capture requirements |
| `/ce-plan` | Architectural and technical implementation plans |
| `/ce-work` | Systematic execution of approved implementation plans |
| `/ce-code-review` | Multi-perspective code review (Security, Architecture, Testing, Performance) |
| `/ce-compound` | After solving problems to capture learnings in `docs/solutions/` |
| `/ce-debug` | Structured root cause analysis and bug investigation |
| `/ce-resolve-pr-feedback` | Address code review and PR feedback systematically |
| `/ce-sweep` | Tech debt and stale reference cleanup |
| `/ce-noslop` / `/ce-optimize` | Codebase simplification, polish, and optimization |

## Knowledge Persistence

Solutions are documented in `docs/solutions/` and explorations in `docs/explorations/` with:
- YAML frontmatter for searchability
- Categorized by problem type
- Schema validated (`schema.yaml`)

**Before solving a problem:** Search `docs/solutions/` and `docs/explorations/` for prior knowledge.

**After solving a problem:** Run `/ce-compound` to document it.

## Compounding Loop

```
/ce-ideate (optional) → /ce-brainstorm → /ce-plan → /ce-work → /ce-code-review → /ce-compound → repeat
```

## Work-surface boundary

The compound system is not a second project-management database.

```text
Git docs/specs/ADRs  = durable truth
GitHub Issues/PRs    = engineering execution + evidence
Linear               = temporary attention, brainstorming, decisions, gates
```

Use `/tracker-routing` before creating or moving work objects.

### Linear

Use Linear for collaborative reasoning, product/strategy questions, architecture alternatives, risk acceptance, go/no-go decisions, and operator/human attention that genuinely needs a shared surface.

Keep Linear thin: title, canonical Git link, short acceptance/decision state. Do not paste plans, specs, research, code-review transcripts, or `NEXT.md` into Linear.

### GitHub

Engineering agents default to GitHub for implementation, bugs, refactors, tests, security remediation, performance, CI/CD, deployment verification, code review, and scanner findings.

If work originated in Linear, link `Linear: SAL-NNN` from the GitHub issue/PR and keep implementation/evidence in GitHub. If engineering discovers a question requiring human/business/architecture/risk adjudication, promote it to a thin Linear decision object.

This is **promotion, not synchronization**. Do not mirror both boards.

## Important Directories

```
.agent/skills/        # Official EveryInc compound skills
docs/solutions/       # Persistent knowledge base
docs/explorations/    # Deep investigations & research
docs/decisions/       # Project-wide ADRs
├── patterns/         # Critical patterns (READ FIRST)
├── schema.yaml       # Validation schema
└── {categories}/     # Categorized solutions
docs/features/        # Feature documentation (New features, READMEs)
plans/                # Implementation plans from /ce-plan
├── archive/          # Completed plans
todos/                # Work items from /ce-code-review
├── archive/          # Completed todos
docs/specs/           # Multi-session specifications
├── archive/          # Completed specs
```

## Agent Behavior

1. **Resume Context** - At the start of EVERY new session, inspect current branch and git status to establish state.
2. **Search before solving** - Check `docs/solutions/` and `docs/explorations/` for prior solutions before designing changes.
3. **Brainstorm & Plan** - Use `/ce-brainstorm` for complex problems and `/ce-plan` before executing significant work.
4. **Document after solving** - Run `/ce-compound` to capture solutions and insights in `docs/solutions/`.
5. **Multi-Perspective Review** - Use `/ce-code-review` before finalizing or merging changes.
6. **Follow patterns** - Reference `patterns/critical-patterns.md`.
7. **Record architectural decisions** - When making major technology or schema choices, create ADRs in `docs/decisions/`.
