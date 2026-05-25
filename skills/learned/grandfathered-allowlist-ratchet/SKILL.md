---
name: grandfathered-allowlist-ratchet
description: "Introduce a new code-quality discipline test to a legacy codebase without a flag-day backfill PR — freeze current violations as an allowlist that monotonically shrinks."
user-invocable: false
origin: auto-extracted
---

# Grandfathered Allowlist Ratchet

**Extracted:** 2026-05-25
**Context:** When adding an architecture/lint/style test that would fail loudly against existing code, but a one-shot backfill PR would be prohibitively large or risky.

## Problem

You want to introduce a new discipline (e.g. "every plan doc must have a status marker", "no module may import X", "every public function must have a docstring"). A naïve test fires on every pre-existing violation, producing a 100+ item failure list that contributors cannot tackle in one PR. The realistic options without this pattern are bad:

- **Backfill everything in one PR** — huge diff, scary review, blocks other work
- **Mark the test xfail** — discipline is fictional, new violations slip in unnoticed
- **Skip the test for "old" files via dates/paths** — brittle (date wrong → bypass; rename → bypass)
- **Defer until "later"** — never happens; the floor keeps sinking

## Solution

Pin current state as a frozen allowlist of identifiers (filename stems, module paths, symbol names). The main test exempts the allowlist; **two companion tests force the allowlist to shrink** so it can never grow or stagnate.

### The three tests

```python
# Frozen at the date the discipline was introduced. Intended to SHRINK.
_GRANDFATHERED: Final[frozenset[str]] = frozenset({
    "legacy-item-1",
    "legacy-item-2",
    # ... every pre-existing violation, by stable identifier
})

def test_new_items_obey_the_discipline() -> None:
    """The main rule: every item that is NOT in the allowlist must comply."""
    violations = [item for item in _all_items()
                  if not _complies(item) and item.id not in _GRANDFATHERED]
    assert not violations, _format_with_fix_hint(violations)

def test_allowlist_only_contains_real_items() -> None:
    """When an item is deleted/renamed, its allowlist entry must be pruned.

    Without this, the allowlist would accumulate ghost entries and slowly
    lose its grip on "what we still owe."
    """
    real_ids = {item.id for item in _all_items()}
    ghosts = sorted(_GRANDFATHERED - real_ids)
    assert not ghosts, f"Remove these stale entries:\n  " + "\n  ".join(ghosts)

def test_allowlist_entries_actually_need_grandfathering() -> None:
    """When a legacy item gets backfilled to comply, its allowlist entry
    must be removed so the floor moves up.

    Without this, contributors could fix the underlying issue but leave
    the entry and the discipline floor never tightens.
    """
    redundant = [item.id for item in _all_items()
                 if item.id in _GRANDFATHERED and _complies(item)]
    assert not redundant, (
        "These items now comply — remove from _GRANDFATHERED:\n  "
        + "\n  ".join(redundant)
    )
```

### Failure-message discipline

Every failure must name the **specific** one-line fix, in copy-pastable form:

```
docs/superpowers/plans/foo.md: no inline status marker AND not referenced
from STATUS.md. Add `> **Status:** shipped (PR #N)` near the top, OR add a
STATUS.md entry mentioning 'foo'. Do NOT add this to the grandfathered
allowlist — that set is frozen and intended to shrink.
```

The "do NOT extend the allowlist" warning is load-bearing: without it, contributors will see the allowlist pattern and assume new entries are welcome.

### Why a frozenset over a list

`frozenset` makes the allowlist tamper-evident at compile time: a mutating operation like `_GRANDFATHERED.add(...)` raises immediately rather than silently growing the floor. Pair with `Final[frozenset[str]]` so static type checkers also reject re-binding.

### Choosing the allowlist key

Use the most stable identifier available:

- File-based rules → filename **stem** (not full path; survives moves within the rule's scope)
- Module rules → fully-qualified module name
- Symbol rules → `module:symbol` pair

Avoid line numbers, hashes, or anything that changes when the file is edited.

## When to Use

Trigger conditions:

- Adding a `test_*_truth.py`-style architecture test that codifies a previously-uncodified rule
- Introducing a new lint rule that would fail on 10+ existing files
- Tightening a Protocol surface, type-hint requirement, or naming convention
- Anywhere "we will fix it later" is the realistic answer to a clean-slate test

Do NOT use when:

- The violation set is small (≤ 5) — just fix them inline
- The discipline is brand-new and the rule itself may change — wait for it to settle before freezing a floor
- The "violations" are intentional and may stay that way forever — use a configured exception/exception_list, not a grandfather set (the difference: grandfather sets are expected to shrink to empty; exception lists are expected to be stable)

## Real-World Example

Introduced in `RytmRandomizer/tests/architecture/test_plan_doc_status_truth.py` (2026-05-24, PR #107) to enforce that every plan document declares its lifecycle status. The codebase had 77 pre-existing plans; mass-backfilling in one PR would have ballooned scope.

The ratchet caught two legitimate violations on its first run — plans that WERE already in STATUS.md but had been added to the allowlist anyway. The companion test `test_grandfathered_set_entries_actually_need_grandfathering` flagged them and forced their removal, so the ratchet started at 75 entries instead of 77 on day one.

## Pitfalls

1. **Forgetting the second companion test.** Without `test_*_actually_need_grandfathering`, contributors can backfill a legacy item but never remove it from the allowlist; the floor stops moving.
2. **Using a `list` or `set` instead of `frozenset`.** Mutable allowlists drift.
3. **No explanatory comment on the allowlist.** Future contributors will assume new entries are fine. The comment must explicitly say "NEVER add a new entry."
4. **Allowlist by absolute path or path-with-extension.** Renames and moves invisibly invalidate entries. Use stable stems.
5. **No documented removal path.** The failure message of the main test must tell contributors what backfilling looks like, otherwise the discipline never gains adherents.
