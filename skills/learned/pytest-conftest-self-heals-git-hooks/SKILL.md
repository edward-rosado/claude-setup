---
name: pytest-conftest-self-heals-git-hooks
description: "Top-level conftest.py auto-installs core.hooksPath on first pytest run so worktrees never silently skip pre-push gates."
user-invocable: false
origin: auto-extracted
---

# Pytest conftest.py Self-Heals Git Hooks Path

**Extracted:** 2026-05-25
**Context:** A repo ships local pre-commit / pre-push hooks under `.githooks/`, activated by `git config core.hooksPath .githooks`. Hooks are the local backstop against landing lint/test regressions on CI. But `git worktree add` does NOT inherit `core.hooksPath` from the parent repo — each worktree has its own local git config space. Fresh worktrees silently skip every hook.

## Problem

`just install` (or equivalent setup script) sets `core.hooksPath` exactly once per clone, in that clone's local git config. Two real workflows skip that setup entirely:

1. `git worktree add ../feature-branch` — each worktree's `.git` file points to its own per-worktree config slot under `.git/worktrees/<name>/config`. The parent's `core.hooksPath` is NOT visible.
2. Clones into environments where `just` is not installed and the install step is skipped.

Either path leaves the developer believing the local gate is live when it is not. The lint regression on PR #107 happened exactly this way: a single ruff SIM103 violation that the pre-push hook would have caught in 5 seconds escaped to CI and cost a fix-push round trip.

## Solution

A top-level `conftest.py` (above `tests/`) runs once per pytest session via `pytest_configure` and self-installs the hook if missing. Idempotent, respects user overrides, no-ops when git is unavailable.

```python
# conftest.py at repo root (above tests/)
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_HOOKS_DIR = _REPO_ROOT / ".githooks"
_PRE_PUSH = _HOOKS_DIR / "pre-push"


def _self_heal_git_hooks_path() -> None:
    if not _PRE_PUSH.is_file():
        return  # repo without hooks, nothing to do

    git = shutil.which("git")
    if git is None:
        return  # tarball install, no git, no-op gracefully

    # Respect any existing value — including a deliberate `/dev/null`
    # opt-out for emergency pushes.
    try:
        existing = subprocess.run(
            [git, "config", "--get", "core.hooksPath"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
            check=False, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return

    if existing.returncode == 0 and existing.stdout.strip():
        return  # already configured (silent path)

    try:
        result = subprocess.run(
            [git, "config", "core.hooksPath", ".githooks"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
            check=False, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return

    if result.returncode == 0:
        print(
            "[conftest] activated .githooks/pre-push for this worktree "
            "(was unset). The pre-push hook now runs lint + architecture "
            "tests before every push."
        )


def pytest_configure(config: object) -> None:
    _self_heal_git_hooks_path()
```

## Layered Defense

The self-heal is layer one. Layer two is an architecture test that asserts the config IS set — so if the self-heal fails on some exotic OS, the developer sees a loud test failure locally instead of a silent CI break:

```python
# tests/architecture/test_pre_push_hook_installed.py
def test_core_hookspath_is_configured() -> None:
    value = _git_config_get("core.hooksPath")
    assert value is not None, (
        "core.hooksPath is not set. Run from the worktree root:\n"
        "  git config core.hooksPath .githooks\n\n"
        "The top-level conftest.py should do this for you on the first "
        "pytest run; if you see this message the self-heal failed."
    )
```

Accept any non-empty value (don't require literally `.githooks`) so a deliberate `/dev/null` opt-out works for emergency pushes. CI's mirror of the same gates still rejects the push server-side, so the opt-out can never accidentally land broken code.

## Why pytest_configure

`pytest_configure` runs ONCE per session, before any collection or test code. Developers run pytest constantly during development, so this is the natural place to self-heal. Alternatives evaluated:

- `pytest_sessionstart`: also works, fires slightly later — `pytest_configure` is canonical for "set up the world before tests load."
- `pytest_collection_modifyitems`: too late, runs after collection.
- `conftest.py` module-level code: runs on every collection of every test file, not just once.

## Linter Considerations

`subprocess.run(...)` with a static argv may trigger bandit `S603` ("subprocess call: check for execution of untrusted input"). Add a per-file ignore:

```toml
# pyproject.toml
[tool.ruff.lint.per-file-ignores]
"conftest.py" = ["S603"]
```

## When to Use

- Any repo with a `.githooks/` directory that requires `git config core.hooksPath` to activate
- Any repo where contributors use git worktrees regularly
- Any repo where "pass locally / fail on CI" lint regressions are costly

Do NOT use when:

- Hooks live in `.git/hooks/` directly (the git default — symlinks/copy-on-install patterns; no `core.hooksPath` involvement)
- Tooling already self-installs hooks on `pip install` or `poetry install` (some projects use `pre-commit install` in a `post_install` hook)

## Real-World Origin

`RytmRandomizer/conftest.py` (PR #107, 2026-05-25). Companion architecture test at `tests/architecture/test_pre_push_hook_installed.py` (3 tests pinning the gate). User feedback that prompted this: "update our local workflow to prevent lint fails in the future. this is costly."
