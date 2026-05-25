---
name: ast-walked-arch-tests-with-drained-allowlist
description: "Turn advisory architecture rules into mechanical CI gates using AST/text-walk tests + a deferred-migration allowlist drained over time."
user-invocable: false
origin: auto-extracted
---

# AST-walked architecture tests with a drained allowlist

**Extracted:** 2026-05-19
**Context:** When advisory rules in CONTRIBUTING.md / arch docs get ignored — humans read them, agents read them, but new code keeps violating them anyway. The fix is to make the rule mechanical: a CI test that fails on a new violation.

**Related:** [`architecture-test-guards`](../architecture-test-guards.md) — once you've written these tests, protect them from being weakened by agents trying to make their code compile.

## Problem

Architecture rules like:

- "Use the existing `Device` Protocol — don't bypass it with sibling subpackages"
- "No private-API imports across module boundaries"
- "Dispatch on canonical constants, not inline strings"
- "Only one registry per concept"

...get violated repeatedly because:

1. There's no mechanical enforcement — only docs and PR-review attention.
2. A new contributor (or autonomous agent) doesn't read the docs.
3. Even reviewers miss violations buried in a 30k-LOC PR.

The result is architectural drift: 3 parallel device subpackages where 1 Protocol-registered family is supposed to live, 8 near-identical `*_sender.py` files where 2 generic ones suffice.

## Solution

Write a pytest module under `tests/architecture/` that AST-walks (or text-walks) the package and asserts the rule. Use a **`frozenset` allowlist that's drained over time** so the test goes green today against legacy violations, but **rejects every NEW violation**.

### Template

```python
"""Enforce <rule> as a mechanical gate.

Today the allowlist is empty/non-empty (legacy state). Adding a new
entry REQUIRES explicit reviewer approval in the PR body. Long-term
state: empty allowlist.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.fast  # if your suite has a fast marker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "your_package"

# Drained allowlist — empty today; each entry would be a deferred
# migration. Format: "<relpath>:<lineno>:<detail>".
_KNOWN_LEGACY_SITES: Final[frozenset[str]] = frozenset()


def _all_package_files() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def test_rule_holds_or_violations_are_allowlisted() -> None:
    violations: list[str] = []
    for path in _all_package_files():
        rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            # ...check the rule. Example: detect bypass of a Protocol.
            if _node_violates_rule(node, rel):
                key = f"{rel}:{node.lineno}:{_describe(node)}"
                if key in _KNOWN_LEGACY_SITES:
                    continue
                violations.append(key)

    assert not violations, (
        "Rule violations detected:\n  " + "\n  ".join(violations)
        + "\n\nFix: <how to comply>. Adding to _KNOWN_LEGACY_SITES "
        "requires explicit reviewer approval in the PR body."
    )
```

### Variants

**Text-walk** (when AST parsing is overkill — e.g. detecting `register_device(` literal substring):
```python
for path in _all_package_files():
    text = path.read_text(encoding="utf-8")
    if "forbidden_substring" in text and rel not in _ALLOWLIST:
        violations.append(rel)
```

**Import-direction check** (forbid `from ..sibling_family import ...`):
```python
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        if node.module and SIBLING_FAMILY in node.module.split("."):
            violations.append(f"{rel}:{node.lineno}")
```

**Surface stability** (pin Protocol attribute/method names so renames must update the test):
```python
_EXPECTED_ATTRS = ("device_id", "snapshot_decoder", ...)
annotations = getattr(MyProtocol, "__annotations__", {})
missing = [a for a in _EXPECTED_ATTRS if a not in annotations]
assert not missing, f"Protocol shape drifted: {missing}"
```

## Why the drained allowlist matters

Without the allowlist, the test has two unappealing modes:

- **Strict from day 1**: fails on every legacy violation → merge blocked → developers add `# noqa` exceptions everywhere → the rule erodes.
- **Lax forever**: passes by skipping the rule → no mechanical enforcement at all.

The drained allowlist gives a **third mode**:
- Today: tests pass; legacy violations are explicitly enumerated with `# deferred migration target` comments.
- Going forward: any NEW violation fails CI immediately (the offender isn't in the allowlist).
- Eventually: the allowlist shrinks to empty as legacy is migrated; the rule is fully enforced.

Adding to the allowlist is a **PR-review decision**, not a silent change. The PR body must justify each new entry.

## When to use

- When you find yourself repeatedly fixing the same kind of violation in PR review.
- When an existing abstraction (Protocol, base class, registry) is being bypassed because nobody mechanically checks usage.
- When you write a CONTRIBUTING.md rule and want to enforce it without relying on reviewer attention.
- When an autonomous code-gen agent is shipping work that violates a documented rule — the agent doesn't read docs but CI failures it does respond to.

## When NOT to use

- For rules that change weekly (the allowlist churn dominates).
- For semantic correctness (use unit tests, not architecture tests).
- For style preferences with no architectural consequence (use ruff/black config instead).

## Pitfalls

- **Pyflakes-level checks belong in ruff, not arch tests.** Reserve arch tests for cross-module / Protocol / dispatch-pattern checks that linters can't express.
- **Allowlist as `frozenset[str]`, not `dict`** — frozenset can't be mutated at runtime by a test that accidentally writes to it.
- **Format the allowlist key consistently across platforms** — use `str(path.relative_to(root)).replace("\\", "/")` so Windows and Linux developers see the same key.
- **Architecture tests must be in the `fast` subset** so they run on every push, not just nightly. Add `pytestmark = pytest.mark.fast` at the top.
- **Pair with `architecture-test-guards`** to prevent agents from silently widening the allowlist when their code violates a rule.
