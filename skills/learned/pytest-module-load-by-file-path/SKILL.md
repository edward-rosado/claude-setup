---
name: pytest-module-load-by-file-path
description: "Load test-helper modules by explicit file path to bypass sys.path namespace-package shadowing that breaks `from tests.helper import x` locally but not on CI."
user-invocable: false
origin: auto-extracted
---

# Pytest: Load Helper Modules by Explicit File Path

**Extracted:** 2026-05-25
**Context:** A test file imports a sibling helper module — e.g. `from tests._parity_worker import _update_index`. The test passes on CI but fails locally with `ModuleNotFoundError: No module named 'tests._parity_worker'` because the developer's machine has a stale `_editable_impl_*.pth` file in user-site-packages pointing at another project whose `tests/__init__.py` shadows this repo's `tests/` namespace package.

## Problem

When `tests/` has no `__init__.py` (PEP 420 implicit namespace package), `import tests` resolves via the first `tests/` directory found on `sys.path`. CI runners have clean environments — sys.path holds only the repo. Developer machines accumulate:

- Stale editable installs (`.pth` files in user-site pointing at deleted/temp projects)
- Conda/virtualenv leaks
- PYTHONPATH exports forgotten in shell rc files

Any of those can put a sibling `tests/` directory ahead of this repo's, and the import silently resolves to the wrong module. Worse: it can resolve PARTIALLY — `import tests` succeeds (some other project's package) but `from tests import _parity_worker` fails because that submodule doesn't exist there.

Bonus failure mode: even when the package-style import works, **monkeypatching module globals breaks** if a fixture and the asserting test code end up with two different module objects in `sys.modules` (one resolved from the bare-name slot, one from the dotted-package slot). `monkeypatch.setattr(pw, "FIXTURE_ROOT", ...)` patches one; assertions read the other; the patch is invisible.

## Solution

Load the helper module by **explicit file path** using `importlib.util.spec_from_file_location`. Cache under a dedicated `sys.modules` key so fixture patches and test reads share ONE module object.

```python
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

_HELPER_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "_parity_worker.py"
)
# Distinct from any name another part of the suite might use to import
# the same file via sys.path. One file, one cached module object.
_HELPER_MODULE_NAME: Final[str] = "_parity_worker_arch_test"


def _load_helper() -> ModuleType:
    """Load the helper module by file path, cached for the session."""
    cached = sys.modules.get(_HELPER_MODULE_NAME)
    if cached is not None:
        return cached

    if not _HELPER_PATH.is_file():
        pytest.fail(f"{_HELPER_PATH} does not exist; check repo layout.")

    spec = importlib.util.spec_from_file_location(
        _HELPER_MODULE_NAME, _HELPER_PATH
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"Could not build import spec for {_HELPER_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_HELPER_MODULE_NAME] = module  # cache BEFORE exec
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def patched_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    pw = _load_helper()  # same cached module the tests see
    fake_root = tmp_path / "fixtures"
    fake_root.mkdir()
    monkeypatch.setattr(pw, "FIXTURE_ROOT", fake_root)
    return fake_root


def test_uses_patched_state(patched_state: Path) -> None:
    pw = _load_helper()  # IDENTICAL module — patch is visible
    assert pw.FIXTURE_ROOT == patched_state
```

## Diagnosis Steps

When `from tests.helper import x` fails locally but passes on CI, run:

```bash
python -c "import sys; [print(p) for p in sys.path]"
```

Look for entries pointing to `Temp/`, dead project directories, or unfamiliar paths. Then:

```bash
ls path/to/user-site-packages/*.pth
cat path/to/user-site-packages/_editable_impl_*.pth
```

If a `.pth` file points at a directory containing `tests/__init__.py`, that's your shadow.

The fix order:

1. **First**: rewrite the affected test to use file-path loading (this skill). This is robust to any future sys.path pollution.
2. **Second** (optional, per-machine hygiene): remove stale `.pth` files. NEVER do this in CI or in shared repos — it's developer-environment cleanup.

## Why Not Just Add `tests/__init__.py`

Tempting but wrong. Adding `__init__.py` to `tests/` converts it from a namespace package to a regular package, which:

- Changes pytest's import-mode behavior (`prepend` vs `importlib` matter differently)
- May cause double-import of test files (collection finds `tests/foo.py` AND `tests.foo`)
- Forces every existing `from helper import x` in sibling test files to become `from tests.helper import x`

The file-path loader fixes the failing test in isolation without touching repo layout.

## When to Use

- Architecture or integration tests that import sibling test-helper modules
- Tests that monkeypatch module globals in a helper (double-instantiation risk)
- "Passes on CI, fails on my machine" `ModuleNotFoundError` from a `from tests.X import Y` pattern
- Tests that must work on developer machines with arbitrary editable installs

Do NOT use when:

- The helper is a real package member (`from rytm_randomizer.utils import ...` for production code — that import path is stable via the editable install)
- You can express the test without the helper at all (often the cleanest fix)

## Real-World Origin

`RytmRandomizer/tests/architecture/test_parity_index_writer.py` (PR #107, 2026-05-25). The test used `from tests._parity_worker import _update_index`, which broke locally because the developer machine had `_editable_impl_sc_bugfix.pth` adding `Temp/sc-bugfix/` to sys.path, and that project's `tests/__init__.py` shadowed the repo's namespace package. CI passed because runners are clean. The rewrite to file-path loading made the test resilient to any sys.path pollution.
