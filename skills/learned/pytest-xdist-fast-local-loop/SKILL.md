---
name: pytest-xdist-fast-local-loop
description: "Don't suppress pytest-xdist with -o addopts=''. The pyproject default of -n auto gives 3× local speedup; reach for -n 0 only on single-file runs."
user-invocable: false
origin: auto-extracted
---

# pytest-xdist: keep it on for the inner loop

**Extracted:** 2026-05-19
**Context:** Python projects with `addopts = "-n auto"` in `pyproject.toml`. The default works as designed; agents and humans often override it reflexively for the wrong reasons.

## Problem

A project pins parallel test execution in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-n auto --durations=20"
```

But every pytest invocation in agent transcripts and team docs reads:

```bash
python -m pytest tests/ -o addopts=''
```

The `-o addopts=''` clears the project defaults, **including `-n auto`**, dropping the run from parallel to single-process. On a 22-core machine that's a ~3× slowdown (92s vs 30s for a 2370-test suite). On a 4-core CI runner it's still ~2×.

Why the suppression is so common:
1. **Historical worktree workaround.** When dev extras (`pytest-xdist`) weren't installed, `-n auto` failed with `unrecognized arguments: -n`. The suppression became muscle memory.
2. **Parity-fixture TOCTOU concern.** Some projects (RytmRandomizer is one) document a known TOCTOU issue when concurrent xdist workers write the same fixture-capture path. The fix is to only suppress xdist in capture mode (`PARITY_CAPTURE_MODE=1`), not in normal runs.
3. **Easier debugging.** Agents disable xdist to get linear test output. Modern xdist (3.0+) groups output per worker and offers `--dist=loadfile` for serial-ish behavior; full disabling is overkill.

## Solution

Use the right flag at the right stage:

| Stage | Command | Notes |
|---|---|---|
| Full suite | `python -m pytest` | Default `-n auto` parallelizes across all cores |
| Fast subset | `python -m pytest -m fast` | Skip slow markers (parity goldens etc.) |
| One file | `python -m pytest tests/test_foo.py -n 0` | `-n 0` disables xdist when worker-spawn-cost > test-time |
| One test | `python -m pytest tests/test_foo.py::test_bar -n 0` | Same reasoning |
| Coverage | `python -m pytest --cov=PACKAGE --cov-branch` | Coverage adds ~1.4× overhead even with xdist; only when auditing |
| Fixture capture (project-specific) | `PARITY_CAPTURE_MODE=1 python -m pytest tests/test_parity*.py -o addopts=''` | The only legitimate use of `-o addopts=''` for projects with TOCTOU concerns |

### The decision rule

| Test count | Use |
|---|---|
| <20 tests | `-n 0` (xdist worker spawn > test time) |
| 20-200 tests | Either; defaults are fine |
| 200+ tests | `-n auto` (the default) is fastest |

## When to use this knowledge

- A teammate complains "tests are slow locally."
- You're writing a CI config or a CONTRIBUTING.md and need to document the local loop.
- An agent transcript shows `-o addopts=''` on every pytest call — that's a smell.
- You see pytest taking >30s for a single file (xdist overhead on a small selection — drop to `-n 0`).

## When NOT to use this knowledge

- Project doesn't have `pytest-xdist` in dev extras (bare pytest only).
- Project has documented serial-only requirements (rare; usually a sign of a bug in test isolation).
- Test code uses module-level state that breaks under concurrent workers — fix the tests, not the runner.

## Pitfalls

- **`-n auto` is per-pytest-invocation, not per-PR.** A subprocess in a test that itself runs `pytest` doesn't inherit `-n auto` — most projects don't want it to.
- **`pytest --collect-only` ignores `-n auto`.** Collection is always single-process.
- **Coverage adds overhead beyond what xdist can save.** `--cov` instruments every line, so even parallel runs are ~1.4× slower than uninstrumented. Only run coverage when you need the metric.
- **xdist worker startup is amortized.** First run is slower than the second; warm FS cache + warm import cache cut subsequent runs significantly. Don't `pytest --cache-clear` casually.

## Concrete proof from one project

RytmRandomizer (2370 tests, 22 dev cores):

| Invocation | Wall time |
|---|---|
| `python -m pytest -o addopts=''` (suppressed) | 92.7s |
| `python -m pytest` (default `-n auto`) | 29.8s |
| `python -m pytest -m fast` (xdist + marker) | 23.7s |
| `python -m pytest tests/test_one.py -n 0` (one file) | 1.4s |

The 3× speedup is free — it's already configured in `pyproject.toml`; just stop overriding it.
