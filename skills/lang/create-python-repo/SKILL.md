---
name: create-python-repo
description: |
  Scaffold a new Python repository set up for agentic, spec-driven
  development across models (Claude Code + codex). Use when the user asks
  to "create a python repo", "set up a new python project", "start a
  python repo", "scaffold a python project", or wants the architecture
  tests / parallel pytest / code-review hooks / codex skill discovery on a
  fresh repo from the first commit. Generates the architecture-conformance
  test suite, the plan-requirement gates, parallel pytest, the
  multi-mechanism post-push code review, the .agents/skills codex symlink,
  the learning module, and the agent-facing docs.
---

# Create Python repo

Scaffold a fresh Python repository with the full agentic, spec-driven
development setup — the same architecture-test discipline, parallel
test execution, automatic code review, and cross-model (Claude Code +
codex) tooling, ready on the first commit.

## What this sets up

A repo scaffolded by this skill has, from commit one — **every developer
quality-of-life item, all the bells and whistles**:

**Mechanical architecture enforcement**
- An **architecture-conformance test suite** (`tests/architecture/`) that
  fails CI on a violation: no import-time side effects, frozen DTOs /
  typed public surface / no mutable module globals, no bare `Any`, no
  unreviewed top-level modules, import-direction enforcement, README
  freshness, and "every plan cites the gates".
- **`docs/PLAN_REQUIREMENTS.md`** — the gates every non-trivial PR is
  reviewed against.

**Parallel, fast testing**
- `pytest -n auto` (xdist) is the default; a `fast` marker gives a
  sub-minute inner loop; `-n 0` is documented for single-file runs.
- Branch-coverage with a ratchet floor in `pyproject.toml`.

**Automatic post-push code review — three mechanisms, one shared script**
(`scripts/code_review_gate.py`):
- `.claude/settings.json` — Claude Code `PostToolUse` agent hook.
- `.codex/hooks.json` — codex `PostToolUse` hook (codex runs only
  `type:command` handlers, so it runs the gate script and re-prompts the
  codex model via `additionalContext`).
- `.githooks/pre-push` — a universal git hook for any tool; `.githooks/`
  also holds a versioned `pre-commit` hook running the pre-commit battery.
- The review **fans out to one targeted agent per dimension**.

**GitHub gating**
- `.github/workflows/ci.yml` with a `required-checks` aggregate job (so
  path-filtered jobs never block PRs).
- `scripts/apply-branch-protection.sh` + `docs/BRANCH_PROTECTION.md` —
  gated builds + required `CODEOWNERS` PR review, no force-push.
- `.github/CODEOWNERS`, a PR template, issue templates.

**Cross-model agent setup**
- `.agents/skills` → `.claude/skills/learned` **symlink** so codex
  auto-discovers learned skills (codex scans `.agents/skills/`, Claude
  Code uses `.claude/skills/`).
- **Agent profiles** under `.claude/agents/`: `code-reviewer`,
  `architecture-guardian`, `planner`.
- **Rules** under `.claude/rules/`: `architecture`,
  `maximize-parallelization`, `autonomous-agent-execution` (drive tasks
  end-to-end, no human-in-the-loop on routine steps), `one-bundled-pr`
  (one PR per change, never a stacked cascade), `code-review-fanout`,
  `codex-contribution-guide`, `learning-capture`.
- The **learning module** — `.claude/skills/learned/` + the
  `learning-capture` rule.

**Contribution guides & docs (AI-optimized)**
- `AGENTS.md`, `CONTRIBUTING.md`, `CLAUDE.md` at the root.
- `docs/` with an AI-optimized index (`docs/README.md`),
  `ARCHITECTURE.md`, `PLAN_REQUIREMENTS.md`, `BRANCH_PROTECTION.md`,
  `CODEX.md` (codex-facing guide), `plans/`.

**Editor / commit hygiene**
- The lint trio (ruff + black + isort), `vulture` dead-code gate,
  `.pre-commit-config.yaml`, `.editorconfig`, `.gitattributes`.
- A `Justfile` task runner, a dev container, `LICENSE`, `CHANGELOG.md`.

This is the **generic core**. Domain-specific add-ons (a golden-file
parity harness, a Protocol/Strategy capability seam, a pinned-dependency
policy) are layered on per project — they are NOT scaffolded here.

## How to run it

The skill ships a self-contained generator: `scripts/scaffold.py`. It
embeds every template, so it works offline and writes a complete repo.

```bash
python <skill-dir>/scripts/scaffold.py <target-dir> [--package <name>] [--force]
```

- `<target-dir>` — the directory to scaffold into (created if absent).
- `--package` — the importable package name. Defaults to a slug derived
  from the directory name (lowercased, non-alphanumerics → `_`).
- `--force` — write into a non-empty directory.

`<skill-dir>` is this skill's own directory — when invoked as a skill,
resolve it from the skill path; when run by hand it is
`~/.claude/skills/create-python-repo`.

### Procedure

1. **Confirm the target directory and package name** with the user if not
   already given. The package name must be a valid Python identifier
   (lowercase, underscores, starts with a letter).

2. **Run the scaffold script.** It writes ~38 files and prints the package
   name, the symlink status, and the remaining manual steps.

3. **Initialize git** if the target is not already a repo:
   ```bash
   cd <target-dir>
   git init
   git add -A
   ```

4. **Materialize the codex symlink correctly.** The scaffold writes
   `.agents/skills` as a real symlink where the OS allows it; on Windows
   without Developer Mode it writes a fallback text file containing
   `../.claude/skills/learned`. Either way, ensure git records a SYMLINK:
   ```bash
   git config core.symlinks true
   # if it came down as a plain file, re-create it as a symlink, or write
   # the git index entry directly:
   #   printf '../.claude/skills/learned' > /tmp/lnk
   #   HASH=$(git hash-object -w /tmp/lnk)
   #   git update-index --add --cacheinfo 120000,$HASH,.agents/skills
   ```
   Verify with `git ls-files -s .agents/skills` — it must show mode
   `120000`. A `100644` entry means git recorded a real file (13 duplicate
   skill files would get committed); fix it with the `update-index`
   command above. The target MUST be forward-slash
   (`../.claude/skills/learned`) — a backslash target will not resolve on
   Linux / macOS / CI.

5. **Install and verify:**
   ```bash
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
   just install        # editable install + git hooks (core.hooksPath) + symlink
   just check          # lint + architecture + tests + coverage — must pass
   ```
   If `just` is not installed: `cargo install just` / `brew install just`
   / `winget install --id Casey.Just`. It is optional — every recipe's
   bare command is in the `Justfile`.

6. **Install the superpowers plugin** (spec-driven workflow commands), if
   the user wants it:
   ```bash
   claude plugin marketplace add obra/superpowers
   claude plugin install superpowers@superpowers
   ```
   If that marketplace is unavailable in the user's environment, say so
   and continue — the scaffold does not depend on it. (`superpowers` adds
   `/brainstorm`, `/plan`, spec-driven slash commands; it is complementary
   to, not required by, the scaffolded setup.)

7. **First commit.** Once `just check` is green:
   ```bash
   git add -A
   git commit -m "chore: scaffold agentic spec-driven Python repo"
   ```

## After scaffolding — what the user does next

The scaffolded repo is a working skeleton, not a finished project. Guide
the user to:

- Replace `<pkg>/example.py` + `tests/test_example.py` with real code.
- Edit `tests/architecture/test_import_direction.py` `_LAYER_RANK` as real
  subpackages are added — this is the dependency-direction contract.
- Tune `docs/PLAN_REQUIREMENTS.md` to the project; add domain-specific
  gates beneath the generic core.
- Raise the `fail_under` coverage floor in `pyproject.toml` as the suite
  grows (the ratchet only moves up).
- Add domain add-ons if relevant — generalize them from a real project
  rather than scaffolding speculative ones.

## Design notes

- **Why one shared `code_review_gate.py`** — three callers (the Justfile
  `review` recipe, the codex hook, the git pre-push hook) run the same
  mechanical gates, so they can never drift.
- **Why the `.agents/skills` symlink** — codex auto-discovers skills from
  `$REPO_ROOT/.agents/skills/`, not `.claude/skills/`. The symlink gives
  one source of truth. It is committed as a git symlink (mode `120000`);
  Windows clones may need `core.symlinks=true`.
- **Why per-dimension review fan-out** — a single agent asked to check
  architecture + house style + tests + abstraction + docs at once does
  each shallowly. One agent per dimension goes deep. The `code-review`
  skill and the `code-reviewer` agent both document this.
- **Generic core only** — the scaffold deliberately omits domain pieces
  (golden-file parity, device/strategy seams, pinned-dependency policy).
  Those are real patterns but they should be generalized from a concrete
  project, not pre-baked into every new repo.

## Cross-references

- `scripts/scaffold.py` — the generator (this skill's payload).
- The scaffolded repo's own `AGENTS.md` / `CONTRIBUTING.md` /
  `docs/ARCHITECTURE.md` document the setup for its contributors.
