#!/usr/bin/env python3
"""Scaffold an agentic, spec-driven Python repository.

Generates the full RytmRandomizer-derived setup for a fresh Python repo:
parallel pytest (xdist), the architecture-conformance test suite, the 18
plan-requirement gates, the lint trio, the multi-mechanism post-push code
review (Claude Code hook + codex hook + git pre-push hook, all calling one
shared gate script), the `.agents/skills` symlink so codex auto-discovers
learned skills, the learning module, AGENTS.md / CONTRIBUTING.md / CLAUDE.md,
a Justfile, and a dev container.

This is the GENERIC CORE only — no domain-specific pieces (no golden-file
parity harness, no device/strategy seam, no pinned-dependency policy). Those
are added per-project on top.

Usage:
    python scaffold.py <target-dir> [--package <name>] [--force]

    <target-dir>   directory to scaffold into (created if absent)
    --package      importable package name (default: derived from dir name)
    --force        write into a non-empty directory (skips the empty check)

After scaffolding, the script prints the remaining manual steps (git init if
needed, `just install`, optional `superpowers` plugin install).
"""

from __future__ import annotations

import argparse
import datetime
import re
import stat
from pathlib import Path

# ===========================================================================
# Templates. {pkg} = package name, {repo} = repo/dir name. `.format()` is fed
# only those two keys; every literal brace in a template is doubled.
# ===========================================================================

PYPROJECT = '''\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{repo}"
version = "0.1.0"
description = "A Python project."
readme = "README.md"
requires-python = ">=3.11"
license = {{ text = "MIT" }}
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8,<9",
    "pytest-xdist>=3,<4",
    "pytest-cov>=5",
    "ruff>=0.6",
    "black>=24",
    "isort>=5",
    "vulture>=2",
    "pre-commit>=3",
]

[tool.hatch.build.targets.wheel]
packages = ["{pkg}"]

[tool.pytest.ini_options]
testpaths = ["tests"]
# -n auto fans the suite across every core. Architecture tests and unit
# tests are process-safe, so parallel is the default. The only time you
# disable it is a single-file selection (`-n 0`) where worker spawn costs
# more than the tests, or a capture mode with a shared-file writer.
addopts = "-n auto --durations=20"
# The `fast` marker tags lightweight in-process tests. `pytest -m fast` is
# the sub-minute inner loop; `pytest -m "not fast"` runs the slow suite
# (integration / golden-file / cross-process). Tag a module at scope with
# `pytestmark = pytest.mark.fast`.
markers = [
    "fast: lightweight in-process test, safe for the fast inner loop.",
]

[tool.coverage.run]
branch = true
source = ["{pkg}"]

[tool.coverage.report]
# Pure-branch coverage floor. Raise it as the suite grows (the ratchet
# only moves up). Touched files in a PR should be at 100%.
fail_under = 90
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "@(abc\\\\.)?abstractmethod",
]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.isort]
profile = "black"
line_length = 100

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
# E501 (line length) is left to black. Add rules as the project matures.
select = ["E", "F", "W", "I", "UP", "B"]
ignore = ["E501"]
'''

PYTHON_VERSION = "3.11\n"

GITIGNORE = '''\
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
build/
dist/
.venv/
venv/
.pytest_cache/
.ruff_cache/
.coverage
.coverage.*
htmlcov/
.mypy_cache/
.idea/
.vscode/
*.swp
.DS_Store
# Agent scratch — never let process artifacts re-enter the repo.
.claude/settings.local.json
'''

GITATTRIBUTES = '''\
* text=auto eol=lf
*.py    text eol=lf diff=python
*.pyi   text eol=lf diff=python
*.toml  text eol=lf
*.yml   text eol=lf
*.yaml  text eol=lf
*.json  text eol=lf
*.md    text eol=lf
*.cfg   text eol=lf
*.ini   text eol=lf
*.sh    text eol=lf
'''

PKG_INIT = '"""The {pkg} package."""\n'

# --- the package's first real module: a trivial, tested example -----------
PKG_EXAMPLE = '''\
"""Example module — replace with real code.

Demonstrates the house style the architecture tests enforce: a typed
public function, no module-level mutable globals, no import-time I/O.
"""

from __future__ import annotations

from typing import Final

GREETING: Final[str] = "hello"


def greet(name: str) -> str:
    """Return a greeting for ``name``."""

    return f"{{GREETING}}, {{name}}"
'''

TEST_EXAMPLE = '''\
"""Tests for the example module."""

from __future__ import annotations

import pytest

from {pkg}.example import GREETING, greet

pytestmark = pytest.mark.fast


def test_greet_returns_greeting_when_given_a_name() -> None:
    assert greet("world") == f"{{GREETING}}, world"


def test_greet_uses_the_greeting_constant() -> None:
    assert greet("x").startswith(GREETING)
'''

CONFTEST = '''\
"""Shared pytest fixtures.

Canonical home for fixtures used by more than one test module (the
"shared fixtures" gate). Define a fixture here once instead of copying it.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:  # pragma: no cover - placeholder fixture
    """Placeholder shared fixture. Replace with real shared fixtures."""

    return "asyncio"
'''

# ===========================================================================
# Architecture-conformance tests. The generic core: import-direction,
# house-style, no-side-effects, no-Any, no-new-top-level-modules,
# plan-requirements-referenced. Each is AST/filesystem-driven and runs fast.
# ===========================================================================

ARCH_INIT = '"""Architecture-conformance tests — mechanical guardrails."""\n'

ARCH_NO_SIDE_EFFECTS = '''\
"""Enforce no I/O at module import time across the package.

Importing any ``{pkg}.*`` submodule must produce no stdout, no stderr, open
no network/file handle, and not call ``input()``. Construction of any
runtime stack must be explicit, not an import side effect.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "{pkg}"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _all_package_modules() -> list[str]:
    """Every fully-qualified module name under the package."""

    out: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        rel = path.relative_to(PROJECT_ROOT).with_suffix("")
        parts = rel.parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out.append(".".join(parts))
    return sorted(set(out))


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_importing_every_package_module_is_silent() -> None:
    """No stdout / stderr / exit-code drift from importing any module."""

    imports = "\\n".join(f"import {{m}}" for m in _all_package_modules())
    result = _run_python(imports)
    assert result.returncode == 0, (
        f"Importing the package produced a non-zero exit code:\\n"
        f"stdout={{result.stdout!r}}\\nstderr={{result.stderr!r}}"
    )
    assert result.stdout == "", "Import must produce no stdout. Got:\\n" + result.stdout
    assert result.stderr == "", "Import must produce no stderr. Got:\\n" + result.stderr


def test_importing_every_package_module_does_not_call_input() -> None:
    """An import-time ``input()`` would block a subprocess forever."""

    imports = "\\n".join(f"import {{m}}" for m in _all_package_modules())
    code = (
        "import builtins\\n"
        "def _no_input(prompt=''):\\n"
        "    raise AssertionError('input() must not be called at import time')\\n"
        "builtins.input = _no_input\\n"
        f"{{imports}}\\n"
        "print('ok')\\n"
    )
    result = _run_python(code)
    assert result.returncode == 0, (
        f"input() was called at import time (or another import-time error fired):\\n"
        f"stdout={{result.stdout!r}}\\nstderr={{result.stderr!r}}"
    )
    assert result.stdout.strip() == "ok"


@pytest.mark.parametrize("module_name", _all_package_modules())
def test_each_module_imports_cleanly_in_isolation(module_name: str) -> None:
    """Each module imports in a fresh Python without stdout / stderr."""

    result = _run_python(f"import {{module_name}}")
    assert result.returncode == 0, (
        f"Importing {{module_name}} failed:\\n" f"stdout={{result.stdout!r}}\\nstderr={{result.stderr!r}}"
    )
    assert result.stdout == "", f"{{module_name}} produced stdout: {{result.stdout!r}}"
    assert result.stderr == "", f"{{module_name}} produced stderr: {{result.stderr!r}}"
'''

ARCH_HOUSE_STYLE = '''\
"""Enforce house-style rules by walking the AST of every package module.

* every ``@dataclass`` is ``frozen=True`` (DTOs are immutable);
* every public (non-underscore) function/method has a return annotation;
* no module-level mutable global (bare ``dict`` / ``list`` / ``set``
  assignment) — constant tables must be a frozen/immutable shape.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "{pkg}"


def _package_files() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def test_every_dataclass_is_frozen() -> None:
    """A mutable DTO is a footgun — every ``@dataclass`` must be frozen."""

    offenders: list[str] = []
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for deco in node.decorator_list:
                func = deco.func if isinstance(deco, ast.Call) else deco
                name = getattr(func, "attr", getattr(func, "id", ""))
                if name != "dataclass":
                    continue
                frozen = False
                if isinstance(deco, ast.Call):
                    for kw in deco.keywords:
                        if kw.arg == "frozen" and isinstance(kw.value, ast.Constant):
                            frozen = bool(kw.value.value)
                if not frozen:
                    offenders.append(f"{{_rel(path)}}:{{node.lineno}} {{node.name}}")
    assert not offenders, "Non-frozen @dataclass found:\\n  " + "\\n  ".join(offenders)


def test_public_functions_have_return_annotations() -> None:
    """Every public function/method declares a return type."""

    offenders: list[str] = []
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            if node.returns is None:
                offenders.append(f"{{_rel(path)}}:{{node.lineno}} {{node.name}}")
    assert not offenders, "Public function missing a return annotation:\\n  " + "\\n  ".join(
        offenders
    )


def test_no_module_level_mutable_globals() -> None:
    """No bare ``dict`` / ``list`` / ``set`` literal assigned at module scope."""

    offenders: list[str] = []
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if isinstance(value, (ast.Dict, ast.List, ast.Set)):
                offenders.append(f"{{_rel(path)}}:{{node.lineno}}")
    assert not offenders, (
        "Module-level mutable global. Wrap constant tables in "
        "MappingProxyType / a frozen dataclass / a tuple:\\n  " + "\\n  ".join(offenders)
    )
'''

ARCH_NO_ANY = '''\
"""Type-system hygiene: no bare ``X = Any`` escape hatches.

A ``SomeAlias = Any`` assignment defeats the type checker silently. Use a
``Protocol``, a generic, or an explicit type instead. New escape hatches
must be justified; this test keeps the count at zero.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "{pkg}"


def test_no_bare_any_aliases() -> None:
    offenders: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            target_is_any = False
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
                target_is_any = node.value.id == "Any"
            elif (
                isinstance(node, ast.AnnAssign)
                and node.value is not None
                and isinstance(node.value, ast.Name)
            ):
                target_is_any = node.value.id == "Any"
            if target_is_any:
                rel = path.relative_to(PROJECT_ROOT)
                offenders.append(f"{{rel}}:{{node.lineno}}")
    assert not offenders, (
        "Bare ``X = Any`` escape hatch found. Use a Protocol / generic / "
        "explicit type:\\n  " + "\\n  ".join(offenders)
    )
'''

ARCH_NO_NEW_TOP_LEVEL = '''\
"""Module-organization hygiene: no unreviewed top-level modules.

The default home for a new concept is a SUBPACKAGE. A flat top-level
module needs sign-off and an explicit allowlist entry. Subpackages keep
the import-direction test enforceable; an unchecked flat top-level erodes
it. The allowlist below is the approved baseline — add to it deliberately,
in the same PR that adds the file, and prune it when a file is deleted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.fast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "{pkg}"

# Approved top-level ``{pkg}/*.py`` files. Adding an entry requires
# sign-off; the default home for new code is a subpackage.
_ALLOWED_TOP_LEVEL: Final[frozenset[str]] = frozenset(
    {{
        "__init__.py",
        "example.py",
    }}
)


def _top_level_python_files() -> list[str]:
    return sorted(p.name for p in PACKAGE_ROOT.glob("*.py"))


def test_no_unallowlisted_top_level_modules() -> None:
    present = set(_top_level_python_files())
    unexpected = sorted(present - _ALLOWED_TOP_LEVEL)
    assert not unexpected, (
        "New top-level module(s) detected. Default home for new code is a "
        "subpackage; a flat top-level addition needs sign-off AND an "
        "``_ALLOWED_TOP_LEVEL`` entry in the same PR.\\n  " + "\\n  ".join(unexpected)
    )


def test_allowlist_does_not_include_deleted_files() -> None:
    present = set(_top_level_python_files())
    missing = sorted(_ALLOWED_TOP_LEVEL - present)
    assert not missing, (
        "``_ALLOWED_TOP_LEVEL`` lists files that no longer exist. Prune the "
        "stale entries in the same PR that deleted them.\\n  " + "\\n  ".join(missing)
    )
'''

ARCH_IMPORT_DIRECTION = '''\
"""Dependency-direction enforcement.

The architecture has a layer order; imports must point only DOWN it.
Edit ``_LAYER_RANK`` to match the package's real subpackages, then this
test fails on any cross-layer import that points up. The starter ranking
below treats ``data`` and ``state`` as the lowest layers (pure, no
intra-package imports) — adjust as the package grows.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.fast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "{pkg}"
PACKAGE_NAME = "{pkg}"

# Lower rank = lower layer. A module may import only from STRICTLY LOWER
# ranks (and stdlib / third-party). Subpackages not listed are unranked
# and unconstrained — add them here as the architecture solidifies.
_LAYER_RANK: Final[dict[str, int]] = {{
    "data": 0,
    "state": 0,
}}


def _subpackage_of(rel_parts: tuple[str, ...]) -> str | None:
    """The immediate subpackage a module lives in, or None for top-level."""

    if len(rel_parts) >= 2:
        return rel_parts[1]
    return None


def test_imports_point_down_the_layer_stack() -> None:
    violations: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        rel_parts = path.relative_to(PROJECT_ROOT).with_suffix("").parts
        here = _subpackage_of(rel_parts)
        here_rank = _LAYER_RANK.get(here) if here else None
        if here_rank is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            for mod in imported:
                parts = mod.split(".")
                if parts[0] != PACKAGE_NAME or len(parts) < 2:
                    continue
                there_rank = _LAYER_RANK.get(parts[1])
                if there_rank is not None and there_rank >= here_rank:
                    rel = path.relative_to(PROJECT_ROOT)
                    violations.append(
                        f"{{rel}}:{{node.lineno}} ({{here}}, rank {{here_rank}}) "
                        f"imports {{mod}} (rank {{there_rank}})"
                    )
    assert (
        not violations
    ), "Import points UP the layer stack (or sideways within a layer):\\n  " + "\\n  ".join(
        violations
    )
'''

ARCH_README_FRESHNESS = '''\
"""README freshness: the README must not rot relative to the repo.

Catches the cheap, mechanical ways a README goes stale:
* a placeholder token (TODO / FIXME / TKTK / lorem ipsum) left in;
* a relative Markdown link pointing at a file that does not exist;
* the README failing to reference the core agent / contributor docs.

Deeper "is the README accurate?" judgement is a code-review concern; this
test is the mechanical backstop.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
README = PROJECT_ROOT / "README.md"

_PLACEHOLDER_TOKENS = ("TODO", "FIXME", "TKTK", "XXX", "lorem ipsum", "PLACEHOLDER")
_EXPECTED_REFERENCES = ("AGENTS.md", "CONTRIBUTING.md")


def test_readme_exists() -> None:
    assert README.is_file(), "README.md is missing from the repo root."


def test_readme_has_no_placeholder_tokens() -> None:
    text = README.read_text(encoding="utf-8")
    found = [tok for tok in _PLACEHOLDER_TOKENS if tok.lower() in text.lower()]
    assert not found, f"README.md still contains placeholder token(s): {{found}}"


def test_readme_internal_links_resolve() -> None:
    """Every relative Markdown link in the README points at a real file."""

    text = README.read_text(encoding="utf-8")
    broken: list[str] = []
    for match in re.finditer(r"\\]\\(([^)]+)\\)", text):
        target = match.group(1).split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        if not (PROJECT_ROOT / target).exists():
            broken.append(target)
    assert not broken, "README.md has broken relative link(s):\\n  " + "\\n  ".join(broken)


def test_readme_references_the_agent_and_contributor_docs() -> None:
    """The README must point a reader at AGENTS.md and CONTRIBUTING.md."""

    text = README.read_text(encoding="utf-8")
    missing = [ref for ref in _EXPECTED_REFERENCES if ref not in text]
    assert (
        not missing
    ), "README.md should reference the core docs but does not mention: " + ", ".join(missing)
'''

ARCH_PLAN_REQS = '''\
"""Every plan document cites ``docs/PLAN_REQUIREMENTS.md``.

A plan under ``docs/plans/`` that does not reference the gates is a plan
written without them in mind. This is the cheap mechanical backstop for
the learning/planning discipline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLANS_DIR = PROJECT_ROOT / "docs" / "plans"


def test_every_plan_references_plan_requirements() -> None:
    if not PLANS_DIR.is_dir():
        pytest.skip("no docs/plans/ directory yet")
    offenders: list[str] = []
    for path in sorted(PLANS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "PLAN_REQUIREMENTS" not in text:
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert (
        not offenders
    ), "Plan document(s) do not cite docs/PLAN_REQUIREMENTS.md:\\n  " + "\\n  ".join(offenders)
'''

# ===========================================================================
# The shared code-review gate script (cli / hook modes). Generic version of
# RytmRandomizer's scripts/code_review_gate.py.
# ===========================================================================

CODE_REVIEW_GATE = '''\
#!/usr/bin/env python3
"""Shared code-review gate.

ONE script, three callers — so the review behaves identically no matter
who triggers it (Claude Code, codex, a human, or plain ``git``):

  * ``--mode cli``       ``just review`` runs this directly.
  * ``--mode codex-hook`` the codex ``PostToolUse`` hook runs this; it reads
                         the hook JSON on stdin, no-ops unless the tool call
                         was a ``git push``, runs the gates, and writes a
                         JSON response (``additionalContext`` on success to
                         re-prompt the codex model for the per-dimension
                         review, ``decision: block`` on failure).
  * ``--mode git-hook``  the ``.githooks/pre-push`` hook runs this; non-zero
                         exit aborts the push. Works for ANY tool.

The "mechanical gates" are lint (ruff + black + isort) + the architecture
suite. The judgement half of the review (deeper design + docs analysis) is
not mechanical — hand it off to a per-dimension agent fan-out afterward.

Usage:
    python scripts/code_review_gate.py --mode cli
    python scripts/code_review_gate.py --mode codex-hook   # stdin = hook JSON
    python scripts/code_review_gate.py --mode git-hook
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_GIT_PUSH_RE = re.compile(r"^\\\\s*git\\\\s+push(\\\\s|$)")

_HANDOFF = (
    "A `git push` just completed. The mechanical code-review gates (lint + "
    "architecture) PASSED. Now complete the code review of the pushed "
    "commits by following .claude/skills/code-review/SKILL.md. Run it as "
    "ONE TARGETED AGENT PER REVIEW DIMENSION, in parallel — not one wide "
    "agent. The skill's 'Execution model' table is the authoritative "
    "dimension list; spawn one agent per row: architecture / "
    "import-direction, house style / type hygiene, tests + coverage, side "
    "effects, abstraction reuse, docs freshness, and execution shape + "
    "learning capture. Then synthesize the per-dimension findings into ONE "
    "structured Critical/Important/Minor verdict and post it as a single "
    "PR comment."
)

_GATES: tuple[tuple[str, list[str]], ...] = (
    ("Lint: ruff", [sys.executable, "-m", "ruff", "check", "."]),
    (
        "Lint: black --check",
        [sys.executable, "-m", "black", "--check", "--target-version=py311", "."],
    ),
    (
        "Lint: isort --check-only",
        [sys.executable, "-m", "isort", "--profile", "black", "--check-only", "."],
    ),
    ("Architecture tests", [sys.executable, "-m", "pytest", "tests/architecture/", "-q"]),
)


def _run_gate(label: str, argv: list[str], *, quiet: bool) -> tuple[bool, str]:
    if quiet:
        proc = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    print(f"=== {{label}} ===", flush=True)
    proc = subprocess.run(argv, cwd=REPO_ROOT)
    ok = proc.returncode == 0
    print(
        f"--- {{label}}: {{'PASSED' if ok else f'FAILED (exit {{proc.returncode}})'}} ---\\n",
        flush=True,
    )
    return ok, ""


def run_mechanical_gates(*, quiet: bool) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for label, argv in _GATES:
        passed, output = _run_gate(label, argv, quiet=quiet)
        if not passed:
            failures.append(label)
            if quiet and output:
                print(f"--- {{label}} FAILED ---\\n{{output}}", file=sys.stderr)
    return not failures, failures


def _mode_cli() -> int:
    passed, failures = run_mechanical_gates(quiet=False)
    if not passed:
        print(
            f"Mechanical review gates FAILED: {{', '.join(failures)}}.\\n"
            "Fix the cause before pushing — do not bypass the gate.",
            flush=True,
        )
        return 1
    print("Mechanical review gates passed (lint + architecture).")
    return 0


def _read_codex_hook_command() -> str | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("tool_name") not in {{"Bash", "shell", "local_shell"}}:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    return command if isinstance(command, str) else None


def _mode_codex_hook() -> int:
    command = _read_codex_hook_command()
    if command is None or not _GIT_PUSH_RE.search(command):
        return 0
    passed, failures = run_mechanical_gates(quiet=True)
    if passed:
        response = {{
            "hookSpecificOutput": {{
                "hookEventName": "PostToolUse",
                "additionalContext": _HANDOFF,
            }}
        }}
    else:
        response = {{
            "decision": "block",
            "reason": (
                "Code-review mechanical gates FAILED after `git push`: "
                f"{{', '.join(failures)}}. Fix the cause and do not bypass "
                "the gate, then complete the code review in "
                ".claude/skills/code-review/SKILL.md."
            ),
        }}
    json.dump(response, sys.stdout)
    sys.stdout.write("\\n")
    return 0


def _mode_git_hook() -> int:
    print("[pre-push] Running mechanical code-review gates...", flush=True)
    passed, failures = run_mechanical_gates(quiet=False)
    if not passed:
        print(
            f"[pre-push] BLOCKED - gates failed: {{', '.join(failures)}}.\\n"
            "[pre-push] Fix the cause and push again.",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(
        "[pre-push] Mechanical gates passed. Complete the per-dimension "
        "code review (see .claude/skills/code-review/SKILL.md).",
        flush=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shared code-review gate.")
    parser.add_argument("--mode", required=True, choices=("cli", "codex-hook", "git-hook"))
    args = parser.parse_args(argv)
    if args.mode == "cli":
        return _mode_cli()
    if args.mode == "codex-hook":
        return _mode_codex_hook()
    return _mode_git_hook()


if __name__ == "__main__":
    raise SystemExit(main())
'''

# ===========================================================================
# Hook configs + the pre-push hook.
# ===========================================================================

CLAUDE_SETTINGS = '''\
{{
  "_doc": [
    "Repo-local Claude Code settings. The PostToolUse hook fires the",
    "code-reviewer agent after a `git push`. No setup — Claude Code reads",
    "this file automatically. Codex has .codex/hooks.json; a universal git",
    "pre-push hook at .githooks/pre-push runs the mechanical gates for any",
    "tool once core.hooksPath is set (`just install` does this)."
  ],
  "hooks": {{
    "PostToolUse": [
      {{
        "matcher": {{ "tool": "Bash", "command_regex": "^\\\\s*git\\\\s+push(\\\\s|$)" }},
        "action": {{
          "type": "Agent",
          "agent": "code-reviewer",
          "prompt": "A `git push` just completed. Execute the code-review skill (.claude/skills/code-review/SKILL.md) against the pushed commits. Run it as ONE TARGETED AGENT PER DIMENSION, in parallel - not one wide agent. The skill's 'Execution model' table is the authoritative dimension list; spawn one agent per row: architecture/import-direction, house style/type hygiene, tests + coverage, side effects, abstraction reuse, docs freshness, and execution shape + learning capture. Then synthesize the per-dimension findings into ONE structured Critical/Important/Minor verdict."
        }}
      }}
    ]
  }}
}}
'''

CODEX_HOOKS = '''\
{{
  "//": [
    "Repo-local Codex CLI hooks - the codex analogue of .claude/settings.json.",
    "Codex discovers this at <repo>/.codex/hooks.json automatically (zero",
    "setup). The PostToolUse hook runs scripts/code_review_gate.py in",
    "codex-hook mode: it no-ops unless the tool call was a `git push`, then",
    "runs the mechanical gates and writes a JSON response - additionalContext",
    "to re-prompt codex for the per-dimension review on success, or",
    "decision:block on failure. Codex runs only type:command handlers",
    "(agent/prompt are skipped), hence the command-hook + additionalContext",
    "re-prompt pattern."
  ],
  "hooks": {{
    "PostToolUse": [
      {{
        "matcher": "^(Bash|shell|local_shell)$",
        "hooks": [
          {{
            "type": "command",
            "command": "python3 \\"$(git rev-parse --show-toplevel)/scripts/code_review_gate.py\\" --mode codex-hook",
            "timeout": 240,
            "statusMessage": "Running the post-push code-review gate"
          }}
        ]
      }}
    ]
  }}
}}
'''

PRE_COMMIT_HOOK = '''\
#!/usr/bin/env bash
# Versioned pre-commit hook. Runs the pre-commit framework's hook battery
# (.pre-commit-config.yaml) on the staged files.
#
# This file lives in .githooks/ so the whole git-hooks setup is ONE
# versioned directory (`git config core.hooksPath .githooks` - which is
# incompatible with pre-commit's own `pre-commit install` into
# .git/hooks/). `just install` sets core.hooksPath; this hook is then
# live with no separate `pre-commit install` step.
#
# If pre-commit is not installed, the hook is a no-op (the lint trio still
# runs in CI). Install it via the dev extra: pip install -e ".[dev]".
set -euo pipefail

if command -v pre-commit >/dev/null 2>&1; then
    exec pre-commit run
elif python -m pre_commit --version >/dev/null 2>&1; then
    exec python -m pre_commit run
else
    echo "[pre-commit] pre-commit not installed - skipping (CI still lints)." >&2
    exit 0
fi
'''

PRE_PUSH_HOOK = '''\
#!/usr/bin/env bash
# Universal pre-push code-review backstop. Fires on EVERY `git push`, any
# tool (Claude Code, codex, a human, an IDE). Runs the mechanical gates via
# the shared scripts/code_review_gate.py and aborts the push if they fail.
#
# Versioned in .githooks/; activate with `git config core.hooksPath .githooks`
# (`just install` does this). Emergency bypass only: `git push --no-verify`.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[pre-push] python not found - skipping local gate; CI must enforce it." >&2
    exit 0
fi

exec "$PY" "$REPO_ROOT/scripts/code_review_gate.py" --mode git-hook
'''

# ===========================================================================
# Justfile.
# ===========================================================================

JUSTFILE = '''\
# Justfile - task runner. Every recipe's bare command is shown, so `just`
# is convenience, not a hard dependency.
#   Install just: cargo install just / brew install just / winget install Casey.Just

default:
    @just --list

# --- tests ---------------------------------------------------------------

# Full suite (xdist-parallelized by the pyproject default).
test:
    python -m pytest

# Fast inner loop - only @pytest.mark.fast tests.
fast:
    python -m pytest -m fast

# Architecture-conformance subset only (preflight before push).
arch:
    python -m pytest tests/architecture/ -q

# Branch coverage + ratchet.
cov:
    python -m pytest --cov={pkg} --cov-branch --cov-report=term-missing

# One file, single-process (worker spawn > test time for small selections).
test-file FILE:
    python -m pytest {{{{FILE}}}} -n 0

# --- lint ----------------------------------------------------------------

lint:
    python -m ruff check .
    python -m black --check --target-version=py311 .
    python -m isort --profile black --check-only .

fmt:
    python -m ruff check . --fix
    python -m black --target-version=py311 .
    python -m isort --profile black .

# Dead-code scan (plan-requirement gate). Tune --min-confidence as needed.
vulture:
    python -m vulture {pkg}/ tests/ --min-confidence 80

# Run the full pre-commit hook battery on all files.
pre-commit-all:
    pre-commit run --all-files

# --- code review ---------------------------------------------------------

# Mechanical review gates only (lint + architecture). Shared with the
# git pre-push hook and the codex hook via scripts/code_review_gate.py.
_review-mechanical:
    python scripts/code_review_gate.py --mode cli

# Full pre-push code review: mechanical gates, then the per-dimension
# agent review (see .claude/skills/code-review/SKILL.md).
review: _review-mechanical
    #!/usr/bin/env bash
    set -euo pipefail
    echo ""
    if [ -n "${{CLAUDE_CODE_EXECPATH:-}}" ]; then
        echo "-> Claude Code detected - dispatching the per-dimension code review..."
        "$CLAUDE_CODE_EXECPATH" -p "Execute the code-review skill (.claude/skills/code-review/SKILL.md) against the about-to-be-pushed commits. Run it as one targeted agent per dimension, in parallel; synthesize into one Critical/Important/Minor verdict." --agent code-reviewer
    elif [ -n "${{CODEX_HOME:-}}" ] || [ "${{CODEX:-}}" = "1" ]; then
        echo "-> codex detected. .codex/hooks.json runs the review on 'git push' automatically."
    else
        echo "Mechanical gates passed. Run the per-dimension review (.claude/skills/code-review/SKILL.md)." >&2
    fi

check: lint arch test cov
    @echo "All checks passed. Ready to push."

# --- dev env -------------------------------------------------------------

# Editable install + activate the versioned git hooks + the codex symlink.
# core.hooksPath makes .githooks/ the single hooks dir - it holds both
# pre-commit (runs the pre-commit framework) and pre-push (the review
# gate). No separate `pre-commit install` (that targets .git/hooks/,
# which core.hooksPath overrides).
install:
    pip install -e ".[dev]"
    git config core.hooksPath .githooks
    git config core.symlinks true
    git checkout -- .agents/skills
    @echo "Installed. git hooks active (.githooks: pre-commit + pre-push); symlink set."
'''

# ===========================================================================
# Agent-facing docs.
# ===========================================================================

PLAN_REQUIREMENTS = '''\
# Plan requirements - the gates every non-trivial change must satisfy

Every non-trivial PR is reviewed against these gates (see
`.claude/skills/code-review/SKILL.md`). Mark each `[x]` or
`[ ] N/A - <reason>` in the PR body. Tune the list to the project; the
starter set below is the generic core.

- **Gate 1** - coverage: touched files at 100% branch coverage; project
  holds or rises the `fail_under` floor in `pyproject.toml`.
- **Gate 2** - lint clean: ruff + black (`--target-version=py311`) + isort
  (`--profile black`).
- **Gate 3** - no new dead code (`vulture` clean).
- **Gate 4** - docs updated: `README.md`, `AGENTS.md`, `docs/` reflect the
  change.
- **Gate 5** - type hygiene: no bare `Any`; `Protocol` over ABC where it
  fits; `Final` on module-level constants.
- **Gate 6** - test hygiene: intent-named tests
  (`test_<unit>_<behavior>_when_<condition>`); shared fixtures in
  `tests/conftest.py`.
- **Gate 7** - module organization: subpackages over flat top-level; new
  top-level modules need sign-off + an allowlist entry.
- **Gate 8** - import direction: imports point only down the layer stack
  (enforced by `tests/architecture/test_import_direction.py`).
- **Gate 9** - no import-time side effects (enforced by
  `test_no_side_effects.py`).
- **Gate 10** - execution shape: one bundled PR per logical change; no
  stacked PR cascade.
- **Gate 11** - abstraction reuse: every new module/class surveyed against
  the existing abstractions; no reimplementation; net-new shapes justified.
- **Gate 12** - architecture-doc freshness: `docs/ARCHITECTURE.md` and any
  diagrams updated for an architecture-surface change; quoted counts
  re-verified.
- **Gate 13** - learning capture: extract a `.claude/skills/learned/` skill
  or a `.claude/rules/` rule when the work surfaced a reusable pattern.

Add domain-specific gates (golden-file parity, pinned dependencies, ...)
beneath this core as the project needs them.
'''

ARCHITECTURE_DOC = '''\
# Architecture

The standard this project's code is held to. The architecture-conformance
tests under `tests/architecture/` mechanically enforce the parts that can
be enforced; this doc is the human-readable source of truth.

## 1. Layout

```
{repo}/
  {pkg}/            the package - subpackages, not a flat pile of modules
  tests/
    architecture/   mechanical-conformance tests (import direction, ...)
    conftest.py     shared fixtures
  docs/             architecture, plan requirements, plans
  scripts/          cross-platform Python tooling
  .claude/          agent rules, skills, the code-reviewer agent + hook
  .codex/           codex hook config
  .agents/skills    symlink -> .claude/skills/learned (codex discovery)
  .githooks/        versioned git hooks (pre-push review gate)
```

## 2. Layer order and import direction

Code is organized into layers; imports point only DOWN. The lowest layers
(`data/`, `state/`) are pure - stdlib only, no intra-package imports.
`tests/architecture/test_import_direction.py` encodes the ranking in
`_LAYER_RANK`; update it as subpackages are added.

## 3. House style

* DTOs are frozen dataclasses.
* Public functions/methods are fully type-annotated.
* No module-level mutable globals - constant tables are immutable shapes.
* No I/O at import time - importing any module is silent and side-effect
  free.
* Module-level constants carry `Final`.

## 4. Where to put new work

The default home for a new concept is a SUBPACKAGE. A flat top-level
module requires sign-off and an allowlist entry in
`test_no_new_top_level_modules.py`.

## 5. Enforcement summary

| Rule | Test |
|---|---|
| No import-time side effects | `test_no_side_effects.py` |
| House style (frozen DTOs, annotations, no mutable globals) | `test_house_style.py` |
| No bare `Any` | `test_no_any_escape_hatches.py` |
| No unreviewed top-level modules | `test_no_new_top_level_modules.py` |
| Import direction | `test_import_direction.py` |
| Plans cite the gates | `test_plan_requirements_referenced.py` |
'''

AGENTS_MD = '''\
# AGENTS.md - agent guide for {repo}

One-page entry point for AI agents (Claude Code, codex, ...) working in
this repo. Humans: read `CONTRIBUTING.md`.

## Before you do anything

1. Read `CONTRIBUTING.md` - the developer handbook.
2. Read `docs/ARCHITECTURE.md` - layer order, house style, where to add
   new work.
3. Read `docs/PLAN_REQUIREMENTS.md` - the gates every PR must satisfy.

## What you must know

| Fact | Implication |
|---|---|
| Architecture tests are mechanical. `tests/architecture/` runs in CI. | A red architecture test blocks the PR. Fix the cause; do not weaken the test. |
| The default home for new code is a subpackage. | A flat top-level module needs sign-off + an allowlist entry. |
| Importing any module must be silent. | No I/O, no `print`, no `input()` at import time. |
| Tests run in parallel (`pytest -n auto`). | Tests must be process-safe. For a single-file run use `-n 0`. |
| Gated builds + required PR review. | The default branch requires the `required-checks` CI job green AND a `CODEOWNERS` approval. Nothing merges red or unreviewed. See `docs/BRANCH_PROTECTION.md`. |

## Post-push code review - automatic

An automated review runs after every `git push`:

* **Claude Code** - `.claude/settings.json` fires the `code-reviewer` agent.
* **Codex** - `.codex/hooks.json` runs `scripts/code_review_gate.py`, which
  re-prompts codex for the review via `additionalContext`.
* **Any tool** - `.githooks/pre-push` runs the mechanical gates and blocks
  the push on failure (activate with `git config core.hooksPath .githooks`;
  `just install` does this).

The review fans out to **one targeted agent per dimension** - see
`.claude/skills/code-review/SKILL.md`. Run `just review` on demand.

## Skills - codex auto-discovers them

Learned skills live in `.claude/skills/learned/` (Claude Code's location).
Codex scans `.agents/skills/`, so the repo ships a symlink
**`.agents/skills` -> `.claude/skills/learned`**. Both agents see the same
skills. If the symlink checked out as a plain file (a Windows clone with
`core.symlinks=false`), run `git config core.symlinks true && git checkout
-- .agents/skills`.

## Commands

```bash
just install   # editable install + git hooks + symlink
just test      # full suite (parallel)
just fast      # fast inner loop
just arch      # architecture gate
just lint      # ruff + black + isort
just review    # the per-dimension code review
just check     # lint + arch + test + cov
```
'''

CONTRIBUTING_MD = '''\
# Contributing to {repo}

## Local development setup

```bash
git clone <repo-url> && cd {repo}
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\\\Scripts\\\\Activate.ps1
pip install -e ".[dev]"
just install                       # git hooks + the .agents/skills symlink
```

Install `just` (the task runner) once: `cargo install just` /
`brew install just` / `winget install --id Casey.Just`. It is optional -
every recipe's bare command is in the `Justfile`.

## The workflow

1. Branch off the integration branch.
2. Write tests first where it fits; keep the suite green.
3. Run `just check` before pushing (lint + architecture + tests + coverage).
4. Push - the post-push code review runs automatically (see `AGENTS.md`).
5. Open a PR; the body carries the `docs/PLAN_REQUIREMENTS.md` gate
   checklist.

## Strict rules

* No I/O at module import time.
* Architecture tests are not optional - a red one blocks the PR.
* New top-level modules need sign-off + an allowlist entry.
* Do not bypass hooks (`--no-verify`) - fix the underlying issue.

## Running tests fast

`pytest -n auto` is the default (parallel). `pytest -m fast` is the
sub-minute inner loop. For a single file, `pytest <file> -n 0` (worker
spawn costs more than a small selection).

## Skills

Reusable patterns are captured as skills in `.claude/skills/learned/`.
When you finish work where you wish you'd had a skill at the start,
extract one - that is Gate 13. Codex sees them via the `.agents/skills`
symlink.
'''

CLAUDE_MD = '''\
# CLAUDE.md - per-session guardrails

These apply to every Claude Code session in this repo. They mirror the
hard rules; `AGENTS.md` and `CONTRIBUTING.md` have the depth.

* **Architecture tests are mechanical and required.** `tests/architecture/`
  runs in CI; a red test blocks the PR. Fix the cause, never weaken the
  test to make it pass.
* **No I/O at import time.** Importing any package module must be silent.
* **Subpackages over flat top-level.** A new top-level module needs
  sign-off + an allowlist entry in `test_no_new_top_level_modules.py`.
* **Tests run in parallel.** `pytest -n auto` is the default; tests must be
  process-safe.
* **The post-push code review runs as one agent per dimension.** See
  `.claude/skills/code-review/SKILL.md`.
* **Capture learnings.** When work surfaces a reusable pattern, extract a
  `.claude/skills/learned/` skill (Gate 13).
'''

# --- the code-review skill + code-reviewer agent --------------------------

CODE_REVIEW_SKILL = '''\
---
name: code-review
description: |
  Repo code review. Use whenever asked to review code, review a PR/diff,
  check changes before merge, or "is this ready?". Verifies the
  architecture standard, the plan-requirement gates, coverage, no
  import-time side effects, abstraction reuse, and doc freshness. Outputs
  Critical / Important / Minor + a verdict.
---

# Code review

You are reviewing a change set against this repo's architecture standard
(`docs/ARCHITECTURE.md`) and plan-requirement gates
(`docs/PLAN_REQUIREMENTS.md`). The gates ARE the review dimensions.

## Execution model - one agent per dimension

Do NOT run this as one wide agent. A single agent spread across
architecture + house style + tests + abstraction + docs does each
shallowly. When you have the `Agent` tool, dispatch **one agent per
dimension, in parallel** (a single message, multiple `Agent` calls), each
scoped to its dimension.

The table below is the **authoritative dimension list** - it covers ALL
of the `docs/PLAN_REQUIREMENTS.md` gates between its rows. Spawn one agent
per row; do not drop a row. Any text elsewhere that enumerates dimensions
(the hook prompt, the codex handoff) points back here and is not itself
exhaustive.

| Dimension agent | Checks | Gates |
|---|---|---|
| Architecture / import-direction | layer order, import direction, no new unreviewed top-level module | 7, 8 |
| House style / type hygiene | frozen DTOs, type annotations, no mutable globals, no bare `Any`, `Final` constants | 5 |
| Tests + coverage | suite green, 100% branch on touched files, no new dead code, intent-named tests, shared fixtures, lint clean | 1, 2, 3, 6 |
| Side effects | no I/O / `print` / `input()` at import time | 9 |
| Abstraction reuse | every new module/class surveyed against existing abstractions; no reimplementation | 11 |
| Docs freshness | `docs/ARCHITECTURE.md` + diagrams updated for an architecture-surface change; quoted counts re-verified | 4, 12 |
| Execution shape + learning capture | one bundled PR per logical change (no stacked cascade); a reusable pattern was extracted to `.claude/skills/learned/` or `.claude/rules/` where applicable | 10, 13 |

Every one of the 13 gates appears in exactly one row above. Then
**synthesize** the per-dimension findings into ONE consolidated
Critical / Important / Minor report and post ONE PR comment. If the
`Agent` tool is unavailable, walk every dimension sequentially yourself.

## Procedure (per dimension)

1. Gather the diff: `git status`, `git diff <base-branch>...HEAD`.
2. For the dimension's checks, inspect every changed file.
3. Run the architecture gate: `pytest tests/architecture/ -q`. A red
   architecture test makes the verdict automatically **Not ready**.
4. Run the full suite + coverage if code changed.

## Output

```
## Code review verdict: [Ready to merge | With fixes | Not ready]

### Critical
- (architecture violation, broken test, import-time side effect)

### Important
- (missing type hints, mutable global, reimplemented abstraction, stale
  architecture doc)

### Minor
- (naming, docstrings, could-be-more-generic suggestions)

### Summary
- One paragraph: the verdict and the top reason.
```

Zero Critical + zero Important -> Ready to merge. Zero Critical + some
Important -> With fixes. Any Critical -> Not ready.
'''

CODE_REVIEWER_AGENT = '''\
---
name: code-reviewer
description: |
  Execute the code-review skill against the current change set. Use when
  asked to review code, review a PR/diff, or check changes before merge.
  Auto-invoked by the post-push hook in .claude/settings.json.
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Agent
---

# Code reviewer agent

You execute the `code-review` skill (`.claude/skills/code-review/SKILL.md`).

## Execution model - one agent per dimension

Code review runs as one targeted agent per dimension, in parallel - not
one wide agent. How you act depends on your prompt:

* **As an orchestrator** ("review PR #N"): spawn one `code-reviewer` agent
  per dimension in parallel - one per row of the "Execution model" table
  in `.claude/skills/code-review/SKILL.md` (that table is the authoritative
  dimension list; do not drop a row), each scoped to one dimension. Then
  synthesize the per-dimension findings into ONE Critical/Important/Minor
  verdict and post ONE PR comment.
* **As a single-dimension worker** (your prompt names a dimension): review
  only that dimension; return a scoped finding list; do not post a
  comment (the orchestrator consolidates).

If the `Agent` tool is unavailable, walk all dimensions yourself.

## What you do

1. Read `.claude/skills/code-review/SKILL.md` and `docs/ARCHITECTURE.md`
   and `docs/PLAN_REQUIREMENTS.md`.
2. Gather the diff: `git status`, `git diff <base-branch>...HEAD`.
3. Run the checks for your scope.
4. Run `pytest tests/architecture/ -q`. A red architecture test makes the
   verdict automatically **Not ready**.
5. Produce the structured verdict in the skill's format.

## Hard rules

* Read-only. Do not edit files.
* Do not skip the architecture gate even for a small change.
* Be specific: cite file paths and line numbers.
'''

ARCHITECTURE_GUARDIAN_AGENT = '''\
---
name: architecture-guardian
description: |
  Guards the architecture standard. Use PROACTIVELY when a change adds or
  moves a module, adds a subpackage, introduces a new dependency edge, or
  touches the layer structure. Verifies the change against
  docs/ARCHITECTURE.md and the architecture-conformance tests before it
  goes further.
tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Architecture guardian agent

You guard this repo's architecture standard (`docs/ARCHITECTURE.md`). You
are consulted when a change touches structure - a new module, a new
subpackage, a new import edge, a layer change.

## What you do

1. Read `docs/ARCHITECTURE.md` - the layer order, the house style, the
   "where to put new work" rule.
2. Inspect the change: which subpackage does new code land in? What does
   it import? Does it add a top-level module?
3. Check it against the rules:
   * Imports point only DOWN the layer stack (lowest layers are pure).
   * New code lives in a SUBPACKAGE - a flat top-level module needs
     sign-off + an `_ALLOWED_TOP_LEVEL` entry.
   * No import-time side effects.
   * House style: frozen DTOs, typed public surface, no mutable globals.
4. Run the architecture gate: `pytest tests/architecture/ -q`.
5. Report: does the change respect the architecture, and if not, exactly
   which rule it breaks and how to fix it.

## Hard rules

* Read-only. Do not edit files.
* A red architecture test is a blocker - report it as such.
* Be specific: name the rule, the file, the line.
'''

PLANNER_AGENT = '''\
---
name: planner
description: |
  Implementation planning specialist. Use PROACTIVELY when the user asks
  to implement a feature, do a non-trivial refactor, or take on multi-step
  work. Produces a plan document under docs/plans/ that cites
  docs/PLAN_REQUIREMENTS.md and is structured for maximally-parallel
  execution.
tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Planner agent

You produce implementation plans for non-trivial work in this repo.

## Use the superpowers plugin

If the `superpowers` plugin is installed, USE its spec-driven planning
workflow - its `/brainstorm` and `/plan` commands (or equivalent) are the
intended front door for planning. Check with `claude plugin list`; if it
is present, drive the plan through it rather than free-handing. If it is
not installed, recommend it (`claude plugin marketplace add
obra/superpowers` then `claude plugin install superpowers@superpowers`)
and proceed with the plan structure below.

## Always plan for maximum parallelization

Every plan is structured so the implementation runs with **maximum
parallelization** - this is not optional. Decompose the work into
**workstreams whose file sets are disjoint**, so they can be executed by
parallel agents at the same time. The plan must explicitly state, for
each workstream, which other workstreams it is independent of and can run
concurrently with. Serialize two workstreams ONLY when one genuinely
depends on the other's output; call that dependency out explicitly.
A plan that serializes independent work is a defective plan.

## What you do

1. Read `docs/PLAN_REQUIREMENTS.md` (the gates) and `docs/ARCHITECTURE.md`.
   Read the `maximize-parallelization` and `one-bundled-pr` rules.
2. Explore the relevant code to ground the plan in what exists.
3. Produce a plan that states:
   * **Goal** - what done looks like.
   * **Workstreams** - the independent pieces. For EACH: its disjoint
     file set, and which other workstreams it runs in parallel with.
     Group workstreams into parallel "waves"; a wave is a set of
     workstreams that all run concurrently. A later wave starts only when
     its dependency wave is done.
   * **Files touched** - per workstream (disjoint across a wave).
   * **Risks** - what could go wrong, and the mitigation.
   * **Gate conformance** - how the change satisfies every gate in
     `docs/PLAN_REQUIREMENTS.md` (the plan MUST cite the file and address
     each gate, `[x]` or `N/A - reason`).
   * **Verification** - the commands that prove it works.
4. The plan ships as ONE bundled PR (see the `one-bundled-pr` rule) - the
   parallel workstreams bundle onto one integration branch, not a stacked
   cascade of PRs.

Save the plan to `docs/plans/YYYY-MM-DD-<slug>.md`. The plan is the spec
the implementation is held to.
'''

# --- the rules -----------------------------------------------------------

RULE_ARCHITECTURE = '''\
---
name: architecture
description: The layer order and import-direction rules. Read on every task that adds or moves a module.
---

# Architecture rule

Code is organized into layers; imports point only DOWN the stack. The
lowest layers are pure (stdlib only). The default home for a new concept
is a SUBPACKAGE - a flat top-level module needs sign-off and an allowlist
entry. See `docs/ARCHITECTURE.md` for the full standard; the layer ranking
is encoded in `tests/architecture/test_import_direction.py`.
'''

RULE_MAXIMIZE_PARALLELIZATION = '''\
---
name: maximize-parallelization
description: Dispatch independent work in parallel - parallel tool calls, parallel agents - not serially.
---

# Maximize parallelization

When work items are independent, do them in parallel:

* Independent tool calls -> one message with multiple tool-use blocks.
* Independent research / review dimensions -> multiple agents dispatched
  in a single message.
* Tests run parallel by default (`pytest -n auto`).

Serial execution is for genuinely dependent steps only. Do not make the
user ask for parallelism.
'''

RULE_CODE_REVIEW_FANOUT = '''\
---
name: code-review-fanout
description: Code reviews fan out to one targeted agent per dimension, not one wide agent.
---

# Code-review fan-out

A code review is run as **one targeted agent per dimension**, dispatched
in parallel - not one wide agent covering every dimension. A single agent
spread across architecture + house style + tests + abstraction + docs does
each one shallowly; per-dimension agents go deep.

Spawn one agent per dimension - one per row of the "Execution model"
table in `.claude/skills/code-review/SKILL.md`, which is the authoritative
dimension list and maps every `docs/PLAN_REQUIREMENTS.md` gate to a row.
Do not drop a row. Each agent's prompt is scoped to ONLY its dimension. An
orchestrator synthesizes the per-dimension findings into one
Critical/Important/Minor verdict and posts one PR comment. See
`.claude/skills/code-review/SKILL.md`.
'''

RULE_AUTONOMOUS_EXECUTION = '''\
---
name: autonomous-agent-execution
description: When asked to complete a task, drive it end-to-end with no human intervention on routine steps.
---

# Autonomous agent execution - no human intervention required

When the user asks an agent to **complete a task**, the agent executes it
end-to-end **without pausing for confirmation on routine steps**. Stop
ONLY for:

1. Genuinely irreversible actions - force-push to a protected branch,
   deleting refs, dropping `CODEOWNERS`, anything destructive and
   hard to undo.
2. A contradiction in the user's instructions you cannot resolve.
3. You have genuinely exhausted your options and are stuck.

Pausing after every step ("step 1 done - shall I proceed with step 2?")
when the steps are obviously chained is an anti-pattern. Round-trip
"may I continue?" latency is the biggest cost in agentic workflows.

## What you must do

* **Continue automatically through chained steps.** "lint clean + commit
  + push + open PR" = do all four; report at the end, not at each step.
* **Fix what you find.** A failing test, a lint error, a broken link
  surfaced mid-task is part of the task - fix it and continue.
* **Use the tools.** Run the tests, run the gate, open the PR. Do not
  describe what you would do and wait.
* **Report once, at the end** - what changed, what is verified, what is
  left. Not a play-by-play.

This is the companion to `maximize-parallelization` (which eliminates
within-session latency); this rule eliminates between-step latency.
'''

RULE_ONE_PR = '''\
---
name: one-bundled-pr
description: One PR per logical change. Never a stacked PR cascade - bundle multi-part work into one PR.
---

# One bundled PR per logical change

A logical change ships as **ONE pull request**, not a chain of stacked
PRs (a PR whose base is another open PR's head). Stacked cascades stall
behind each other's reviews and make the diff impossible to reason about.

## The rule

* **One PR per logical change.** Multiple commits in that PR is fine; a
  fan-out of dependent PRs is not.
* **Base every PR on the integration branch** (`main` or the project's
  integration branch), never on another open PR's head.
* **Bundle multi-workstream work.** When a change has several independent
  workstreams:
  1. Implement each workstream (in parallel where the files are disjoint).
  2. Bundle them onto one integration branch via `git merge --no-ff`.
  3. Resolve shared-file conflicts deterministically.
  4. Open ONE PR for the bundle.
* A PR that is genuinely too large to review is a sign the *change* was
  too large - split the work into separately-shippable changes, each its
  own single PR, not a stack.

## Why

Stacked PRs serialize on human review latency - PR 2 cannot merge until
PR 1 does. One bundled PR is reviewed once, merges once. The diff is
self-contained and the CI signal is unambiguous.
'''

RULE_CODEX_CONTRIBUTION = '''\
---
name: codex-contribution-guide
description: Pre-flight checklist for the OpenAI codex agent (or any agent on a codex/* branch). Read before opening a PR.
---

# Codex contribution guide

If you are operating as the OpenAI `codex` agent (or on a `codex/*`
branch), run this checklist before opening a PR. It exists because
codex-style agents historically get a few things wrong on a strict repo.

## Before any work

Read, in order: `AGENTS.md`, `CONTRIBUTING.md`, `docs/ARCHITECTURE.md`,
`docs/PLAN_REQUIREMENTS.md`. The same hard rules apply to every agent.

## You get the post-push review automatically

Codex reads `.codex/hooks.json` from the repo root - the codex analogue
of `.claude/settings.json`. Its `PostToolUse` hook runs
`scripts/code_review_gate.py` after every `git push`: it runs the
mechanical gates and, via `additionalContext`, re-prompts you to perform
the per-dimension code review. When re-prompted, do the review and post
the verdict on the PR. `.githooks/pre-push` is a second backstop (blocks
the push if the mechanical gates fail; activate with `git config
core.hooksPath .githooks`, which `just install` does).

## Skills are auto-discovered

Codex scans `$REPO_ROOT/.agents/skills/`. The repo ships a committed
symlink `.agents/skills` -> `.claude/skills/learned`, so you auto-discover
every learned skill (same `SKILL.md` format as Claude Code). If the
symlink checked out as a plain text file (a Windows clone with
`core.symlinks=false`), run `git config core.symlinks true && git checkout
-- .agents/skills`.

## Pre-PR checklist

- [ ] One PR per logical change. No stacked PR cascade (a PR whose base is
      another open PR's head). Bundle multi-part work via an integration
      branch + `git merge --no-ff`.
- [ ] No new top-level module under the package without sign-off + an
      `_ALLOWED_TOP_LEVEL` entry. Default home for new code is a
      subpackage. (`tests/architecture/test_no_new_top_level_modules.py`.)
- [ ] No reimplementation of an existing abstraction - survey first, reuse
      what fits.
- [ ] `pytest tests/architecture/ -q` passes locally. Fix the cause of any
      failure; do not weaken the test or extend an allowlist without
      sign-off.
- [ ] Lint trio clean (ruff + black + isort).
- [ ] The PR body carries the `docs/PLAN_REQUIREMENTS.md` gate checklist,
      every gate marked `[x]` or `[ ] N/A - <reason>`.
- [ ] You ran the per-dimension code review and posted the verdict.
'''

RULE_LEARNING_CAPTURE = '''\
---
name: learning-capture
description: When work surfaces a reusable pattern, extract a learned skill or a rule.
---

# Learning capture

When you finish work where you wish you'd had a skill or a rule at the
start, extract one (this is a plan-requirement gate):

* A reusable technique / workaround / debugging pattern -> a skill under
  `.claude/skills/learned/<name>/SKILL.md` with `name` + `description`
  frontmatter.
* A standing project policy -> a rule under `.claude/rules/<name>.md`.

Codex auto-discovers learned skills via the `.agents/skills` symlink. Keep
each skill focused on one pattern. Do not extract trivial one-off fixes.
'''

LEARNED_README = '''\
# Learned skills

Reusable patterns extracted from past work. Each subdirectory is a skill:
a `SKILL.md` with `name` + `description` frontmatter, optionally with
`scripts/` / `references/` / `assets/`.

Claude Code discovers these here. **Codex** discovers them via the
`.agents/skills` -> `.claude/skills/learned` symlink at the repo root.
The `SKILL.md` format is identical for both agents, and the model
auto-invokes a skill when a task matches its `description`.

To add one: create `.claude/skills/learned/<kebab-name>/SKILL.md`. See the
`learning-capture` rule.
'''

CI_WORKFLOW = '''\
name: ci

# Gated builds. `required-checks` is the SINGLE aggregate job branch
# protection requires - it depends on every real gate (lint, architecture,
# test) and reports success only when all of them succeeded or were
# correctly skipped. Path-filtered jobs report `skipped` to GitHub, which
# branch protection treats as pending and would block the PR forever; the
# aggregate translates `skipped` -> `success`. Require ONLY `required-checks`
# in branch protection (scripts/apply-branch-protection.sh does this).

on:
  push:
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: pip install -e ".[dev]"
      - name: Lint trio
        run: |
          python -m ruff check .
          python -m black --check --target-version=py311 .
          python -m isort --profile black --check-only .

  architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: pip install -e ".[dev]"
      - name: Architecture gate
        run: python -m pytest tests/architecture/ -q

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: pip install -e ".[dev]"
      - name: Test suite + coverage
        run: python -m pytest --cov={pkg} --cov-branch

  # The aggregate gate. Branch protection requires ONLY this job. It fails
  # if any upstream job failed or was cancelled; a `skipped` upstream job
  # (path-filtered out) counts as success.
  required-checks:
    name: required-checks
    needs: [lint, architecture, test]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Verify every required job succeeded or was skipped
        run: |
          results="${{{{ needs.lint.result }}}} ${{{{ needs.architecture.result }}}} ${{{{ needs.test.result }}}}"
          echo "upstream results: $results"
          for r in $results; do
            if [ "$r" != "success" ] && [ "$r" != "skipped" ]; then
              echo "A required job did not pass (result=$r)."
              exit 1
            fi
          done
          echo "All required jobs passed (or were correctly skipped)."
'''

CODEOWNERS = '''\
# Code owners. A PR automatically requests review from the owner(s) of
# every changed path. Branch protection's "require code owner reviews"
# makes that review mandatory before merge.
#
# Replace @OWNER with the GitHub username/team that owns this repo. Add
# path-specific lines below the default as the repo grows, e.g.:
#   /docs/        @OWNER @docs-team
#   /{pkg}/data/  @OWNER
* @OWNER
'''

BRANCH_PROTECTION_SCRIPT = '''\
#!/usr/bin/env bash
#
# apply-branch-protection.sh
#
# Applies branch protection to the default branch. A repo admin runs this
# ONCE after the repo is on GitHub. NOT run from CI.
#
# Requires: gh CLI authenticated as a repo admin.
# See docs/BRANCH_PROTECTION.md for the human-readable description.
#
# What it enforces:
#   * Required status check: the `required-checks` aggregate job ONLY
#     (see .github/workflows/ci.yml for why one aggregate, not N jobs).
#   * Required PR review: 1 approval, code-owner review required, stale
#     reviews dismissed on a new push.
#   * Required conversation resolution.
#   * No force-pushes, no branch deletion.
#   * Admins are included (enforce_admins).
set -euo pipefail

# Edit these two, or pass them as env vars.
REPO="${{REPO:-OWNER/REPO}}"
BRANCH="${{BRANCH:-main}}"

if [ "$REPO" = "OWNER/REPO" ]; then
    echo "error: set REPO (e.g. REPO=me/my-repo $0), or edit the script." >&2
    exit 2
fi

read -r -d '' PAYLOAD <<'JSON' || true
{{
  "required_status_checks": {{
    "strict": true,
    "checks": [
      {{ "context": "required-checks" }}
    ]
  }},
  "enforce_admins": true,
  "required_pull_request_reviews": {{
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  }},
  "required_conversation_resolution": true,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}}
JSON

echo "Applying branch protection to ${{REPO}}@${{BRANCH}}..."
echo "$PAYLOAD" | gh api \\
  --method PUT \\
  -H "Accept: application/vnd.github+json" \\
  "repos/${{REPO}}/branches/${{BRANCH}}/protection" \\
  --input -

echo "Done. ${{BRANCH}} now requires: the required-checks aggregate job,"
echo "1 code-owner approval, conversation resolution; force-push disabled."
'''

BRANCH_PROTECTION_DOC = '''\
# Branch protection

The default branch is gated. A repo admin applies this ONCE, after the
repo is on GitHub, by running `scripts/apply-branch-protection.sh` (with
`REPO=<owner>/<repo>` set, authenticated as an admin via the `gh` CLI).

## What is enforced

- **Required status check — `required-checks` only.** This is the
  aggregate job in `.github/workflows/ci.yml`. It depends on every real
  gate (lint, architecture, test) and passes only when all of them
  succeeded or were correctly skipped. Branch protection requires ONLY
  this one check, never the individual jobs — see the workflow header for
  why (path-filtered jobs report `skipped`, which would otherwise block
  the PR forever).
- **Required PR review.** One approval, and `CODEOWNERS` review is
  required — the owner of every changed path must approve. A new push
  dismisses stale approvals.
- **Required conversation resolution.** Every review thread must be
  resolved before merge.
- **No force-pushes, no branch deletion** on the protected branch.
- **Admins included** (`enforce_admins`) — the gate applies to everyone.

## Why gated builds + required review

A PR cannot merge until CI is green AND a code owner has approved. The
automatic post-push code review (`AGENTS.md`) produces the review
verdict; the human/code-owner approval is the sign-off. Together: nothing
merges unreviewed, and nothing merges red.

## Adding a status check

If you add a new CI job that must gate merges, add it to the
`required-checks` job's `needs:` list in `.github/workflows/ci.yml` — do
NOT add it to the branch-protection payload. The aggregate job is the
contract; the individual jobs are the implementation detail.
'''

DEVCONTAINER = '''\
{{
  "//": "Dev container for {repo} - used by GitHub Codespaces, VS Code Dev Containers, and cloud-agent runners (Claude Code, codex). It reproduces the exact dev setup a contributor would build by hand: pinned Python, the package installed editable with dev extras, just, and the versioned git hooks activated. Linux checks out symlinks natively, so the .agents/skills -> .claude/skills/learned symlink (codex skill discovery) materializes on clone with no extra step.",

  "name": "{repo}-dev",
  "image": "mcr.microsoft.com/devcontainers/python:1-3.11-bookworm",

  "features": {{
    "ghcr.io/devcontainers/features/github-cli:1": {{}},
    "ghcr.io/devcontainers/features/git:1": {{}}
  }},

  "//postCreate": "Install the package + dev extras, install `just` (cargo, then the prebuilt-binary installer as fallback), and point git at the versioned .githooks/ directory so the pre-commit + pre-push gates are live.",
  "postCreateCommand": "pip install -e '.[dev]' && (command -v just || cargo install just || curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin) && git config core.hooksPath .githooks && git config core.symlinks true",

  "//runtime": "PYTHONDONTWRITEBYTECODE keeps __pycache__ out of the workspace; PYTHONUNBUFFERED streams pytest output live.",
  "containerEnv": {{
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUNBUFFERED": "1"
  }},

  "customizations": {{
    "vscode": {{
      "extensions": [
        "ms-python.python",
        "ms-python.black-formatter",
        "ms-python.isort",
        "charliermarsh.ruff",
        "tamasfe.even-better-toml",
        "editorconfig.editorconfig"
      ],
      "settings": {{
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "python.terminal.activateEnvironment": false,
        "python.testing.pytestEnabled": true,
        "python.testing.unittestEnabled": false,
        "python.testing.pytestArgs": ["tests"],
        "[python]": {{
          "editor.defaultFormatter": "ms-python.black-formatter",
          "editor.formatOnSave": true,
          "editor.codeActionsOnSave": {{
            "source.organizeImports": "explicit",
            "source.fixAll": "explicit"
          }}
        }},
        "black-formatter.args": ["--target-version=py311"],
        "isort.args": ["--profile=black"],
        "files.eol": "\\n",
        "files.insertFinalNewline": true,
        "files.trimTrailingWhitespace": true,
        "[markdown]": {{ "files.trimTrailingWhitespace": false }},
        "search.exclude": {{
          "**/.venv": true,
          "**/__pycache__": true,
          "**/.pytest_cache": true,
          "**/.ruff_cache": true
        }}
      }}
    }}
  }}
}}
'''

PRE_COMMIT_CONFIG = '''\
# Pre-commit hooks. Activated by `just install` (which sets
# core.hooksPath to .githooks/; the versioned .githooks/pre-commit hook
# runs this battery). Runs the lint trio + file checks on every commit, so
# a push never fails CI on something a hook catches.
#
# Run on all files any time with `just pre-commit-all`. Versions are
# pinned in lockstep with pyproject.toml's [dev] extra - bump together.
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        args: [--target-version=py311]
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: [--profile, black]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: check-merge-conflict
      - id: check-added-large-files
      - id: mixed-line-ending
        args: [--fix=lf]
'''

EDITORCONFIG = '''\
# EditorConfig - consistent editor behavior across the team.
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space

[*.py]
indent_size = 4
max_line_length = 100

[*.{{json,yml,yaml,toml,md}}]
indent_size = 2

[Makefile]
indent_style = tab
'''

CHANGELOG_MD = '''\
# Changelog

All notable changes to this project are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/), and this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Initial project scaffold.

## [0.1.0] - {{date}}

### Added
- Project created.
'''

LICENSE_MIT = '''\
MIT License

Copyright (c) {{year}} {{owner}}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

ISSUE_BUG = '''\
---
name: Bug report
about: Something is not working
labels: bug
---

## What happened

<!-- What you observed. -->

## Expected

<!-- What you expected instead. -->

## Reproduce

<!-- Steps / a minimal snippet. -->

## Environment

- OS:
- Python version:
- {repo} version / commit:
'''

ISSUE_FEATURE = '''\
---
name: Feature request
about: Propose a change or addition
labels: enhancement
---

## The problem

<!-- What is hard or missing today. -->

## Proposed solution

<!-- What you would like to happen. -->

## Alternatives considered

<!-- Other approaches, and why this one. -->
'''

README_MD = '''\
# {repo}

A Python project.

## Quick start

```bash
pip install -e ".[dev]"
just install      # git hooks + the codex skills symlink
just test
```

## For contributors and agents

* Humans: `CONTRIBUTING.md`.
* AI agents (Claude Code, codex): `AGENTS.md`.
* Architecture standard: `docs/ARCHITECTURE.md`.
* The gates every change must satisfy: `docs/PLAN_REQUIREMENTS.md`.

This repo is set up for agentic, spec-driven development: a mechanical
architecture-conformance test suite, parallel pytest, an automatic
post-push code review (one agent per dimension), and codex skill discovery
via the `.agents/skills` symlink.
'''

PLANS_README = '''\
# Plans

Spec / plan documents for non-trivial work. Each plan must cite
`docs/PLAN_REQUIREMENTS.md` (enforced by
`tests/architecture/test_plan_requirements_referenced.py`).

Name plans `YYYY-MM-DD-<short-slug>.md`. A plan states: the goal, the
workstreams, the files touched, the risks, and the gate-conformance
intent. It is the spec the implementation is held to.
'''

DOCS_README = '''\
# docs/ - documentation index

This folder is structured for AI agents and humans alike: a small set of
authoritative, in-place-maintained documents, not an append-log. Read the
one you need; do not skim everything.

## Read these first (the contract)

| Doc | What it is | Read when |
|---|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | The architecture standard - layer order, house style, where to add new work. | Before adding or moving any module. |
| [`PLAN_REQUIREMENTS.md`](PLAN_REQUIREMENTS.md) | The gates every non-trivial PR is reviewed against. | Before opening a PR; when writing a plan. |
| [`BRANCH_PROTECTION.md`](BRANCH_PROTECTION.md) | Gated builds + required PR review on the default branch. | When setting up the repo on GitHub; when adding a CI check. |
| [`CODEX.md`](CODEX.md) | Codex-specific contribution guide. | If you are the codex agent or on a `codex/*` branch. |

## Working docs

| Folder | What it holds |
|---|---|
| [`plans/`](plans/) | Spec / plan documents for non-trivial work (`YYYY-MM-DD-<slug>.md`). Each cites `PLAN_REQUIREMENTS.md`. |

## Conventions

- **Maintained in place, never appended.** A doc is a current snapshot.
  When something changes, edit the doc - do not add a dated section to the
  bottom. Stale append-logs are how docs rot.
- **One source of truth per fact.** A number, a path, a rule lives in
  exactly one doc; others link to it.
- **Agent entry points are at the repo root.** `AGENTS.md` (agents),
  `CONTRIBUTING.md` (humans), `CLAUDE.md` (Claude Code session rules).
  This folder is the depth behind those one-pagers.
- **Process exhaust does not live here.** If a document describes a
  process rather than the product (a session log, a checkpoint), it does
  not belong in `docs/`. Plans are the exception - they are the spec.
'''

CODEX_DOC = '''\
# Codex contribution guide

The codex-facing contribution guide for {repo}. If you are the OpenAI
`codex` agent (or any agent on a `codex/*` branch), this is your guide;
the short rule version is `.claude/rules/codex-contribution-guide.md`.

Codex follows the SAME rules as every other contributor - `AGENTS.md`,
`CONTRIBUTING.md`, `docs/ARCHITECTURE.md`, `docs/PLAN_REQUIREMENTS.md`.
This doc only surfaces the codex-specific mechanics.

## Read order

1. `AGENTS.md` - the one-page agent index.
2. `CONTRIBUTING.md` - the developer handbook.
3. `docs/ARCHITECTURE.md` - layer order, house style, where to add work.
4. `docs/PLAN_REQUIREMENTS.md` - the gates every PR must satisfy.
5. `.claude/rules/codex-contribution-guide.md` - the pre-PR checklist.

## The post-push code review is automatic for codex

Codex reads `.codex/hooks.json` from the repo root automatically - the
codex analogue of Claude Code's `.claude/settings.json`. Its `PostToolUse`
hook runs `scripts/code_review_gate.py` in `codex-hook` mode after every
`git push`:

- it no-ops silently unless the tool call was a `git push`;
- on a `git push` it runs the mechanical gates (lint + architecture) and
  writes a JSON response - `additionalContext` on success that re-prompts
  YOU to perform the per-dimension code review, or `decision: block` on
  failure with the reason.

Codex runs only `type: command` hook handlers (`agent` / `prompt`
handlers are parsed but skipped), which is why the hook is a `command`
hook that re-prompts via `additionalContext` rather than dispatching an
agent directly.

A second backstop, `.githooks/pre-push`, runs the mechanical gates on
every `git push` for any tool and blocks the push on failure. Activate it
with `git config core.hooksPath .githooks` (`just install` does this).

## Skills are auto-discovered

Codex scans `$REPO_ROOT/.agents/skills/`, not `.claude/skills/`. The repo
ships a committed symlink `.agents/skills` -> `.claude/skills/learned`, so
codex auto-discovers every learned skill. The `SKILL.md` format is
identical for both agents, and the model auto-invokes a skill when a task
matches its `description`.

If the symlink checked out as a plain text file (a Windows clone with
`core.symlinks=false`), run:

```bash
git config core.symlinks true
git checkout -- .agents/skills
```

## Anti-patterns to avoid

- **A stacked PR cascade** - a PR whose base is another open PR's head.
  Bundle multi-part work into one PR via an integration branch.
- **A new top-level module** under the package without sign-off + an
  `_ALLOWED_TOP_LEVEL` entry. The default home for new code is a
  subpackage.
- **Reimplementing an existing abstraction** instead of reusing it -
  survey first.
- **Weakening an architecture test** or extending an allowlist to make a
  red test green. Fix the cause.
- **Omitting the gate checklist** from the PR body.

## Before opening a PR

Run the `.claude/rules/codex-contribution-guide.md` pre-PR checklist:
`pytest tests/architecture/ -q` green, lint trio clean, the
`docs/PLAN_REQUIREMENTS.md` gate checklist in the PR body, and the
per-dimension code review performed with the verdict posted.
'''

PR_TEMPLATE = '''\
# Summary

<!-- What does this PR do and why? -->

## What changed

-

## Test plan

```bash
just check
```

## Plan-requirements conformance

<!-- Per docs/PLAN_REQUIREMENTS.md - mark each [x] or [ ] N/A - <reason>. -->

- [ ] Gate 1 - coverage (100% branch on touched files; project floor held)
- [ ] Gate 2 - lint clean (ruff + black + isort)
- [ ] Gate 3 - no new dead code (vulture)
- [ ] Gate 4 - docs updated
- [ ] Gate 5 - type hygiene (no bare Any; Final constants)
- [ ] Gate 6 - test hygiene (intent-named tests; shared fixtures)
- [ ] Gate 7 - module organization (subpackages over flat top-level)
- [ ] Gate 8 - import direction
- [ ] Gate 9 - no import-time side effects
- [ ] Gate 10 - execution shape (one bundled PR; no stacked cascade)
- [ ] Gate 11 - abstraction reuse
- [ ] Gate 12 - architecture-doc freshness
- [ ] Gate 13 - learning capture
'''


# ===========================================================================
# Files: relpath -> (template, is_executable). Symlinks handled separately.
# ===========================================================================

def _files(pkg: str) -> dict[str, tuple[str, bool]]:
    return {
        "pyproject.toml": (PYPROJECT, False),
        ".python-version": (PYTHON_VERSION, False),
        ".gitignore": (GITIGNORE, False),
        ".gitattributes": (GITATTRIBUTES, False),
        ".editorconfig": (EDITORCONFIG, False),
        ".pre-commit-config.yaml": (PRE_COMMIT_CONFIG, False),
        "LICENSE": (LICENSE_MIT, False),
        "CHANGELOG.md": (CHANGELOG_MD, False),
        "README.md": (README_MD, False),
        "AGENTS.md": (AGENTS_MD, False),
        "CONTRIBUTING.md": (CONTRIBUTING_MD, False),
        "CLAUDE.md": (CLAUDE_MD, False),
        "Justfile": (JUSTFILE, False),
        f"{pkg}/__init__.py": (PKG_INIT, False),
        f"{pkg}/example.py": (PKG_EXAMPLE, False),
        "tests/__init__.py": ("", False),
        "tests/conftest.py": (CONFTEST, False),
        "tests/test_example.py": (TEST_EXAMPLE, False),
        "tests/architecture/__init__.py": (ARCH_INIT, False),
        "tests/architecture/test_no_side_effects.py": (ARCH_NO_SIDE_EFFECTS, False),
        "tests/architecture/test_house_style.py": (ARCH_HOUSE_STYLE, False),
        "tests/architecture/test_no_any_escape_hatches.py": (ARCH_NO_ANY, False),
        "tests/architecture/test_no_new_top_level_modules.py": (ARCH_NO_NEW_TOP_LEVEL, False),
        "tests/architecture/test_import_direction.py": (ARCH_IMPORT_DIRECTION, False),
        "tests/architecture/test_plan_requirements_referenced.py": (ARCH_PLAN_REQS, False),
        "tests/architecture/test_readme_freshness.py": (ARCH_README_FRESHNESS, False),
        "scripts/code_review_gate.py": (CODE_REVIEW_GATE, False),
        "scripts/apply-branch-protection.sh": (BRANCH_PROTECTION_SCRIPT, True),
        "docs/README.md": (DOCS_README, False),
        "docs/ARCHITECTURE.md": (ARCHITECTURE_DOC, False),
        "docs/PLAN_REQUIREMENTS.md": (PLAN_REQUIREMENTS, False),
        "docs/BRANCH_PROTECTION.md": (BRANCH_PROTECTION_DOC, False),
        "docs/CODEX.md": (CODEX_DOC, False),
        "docs/plans/README.md": (PLANS_README, False),
        ".github/CODEOWNERS": (CODEOWNERS, False),
        ".claude/settings.json": (CLAUDE_SETTINGS, False),
        ".claude/agents/code-reviewer.md": (CODE_REVIEWER_AGENT, False),
        ".claude/agents/architecture-guardian.md": (ARCHITECTURE_GUARDIAN_AGENT, False),
        ".claude/agents/planner.md": (PLANNER_AGENT, False),
        ".claude/skills/code-review/SKILL.md": (CODE_REVIEW_SKILL, False),
        ".claude/skills/learned/README.md": (LEARNED_README, False),
        ".claude/rules/architecture.md": (RULE_ARCHITECTURE, False),
        ".claude/rules/maximize-parallelization.md": (RULE_MAXIMIZE_PARALLELIZATION, False),
        ".claude/rules/autonomous-agent-execution.md": (RULE_AUTONOMOUS_EXECUTION, False),
        ".claude/rules/one-bundled-pr.md": (RULE_ONE_PR, False),
        ".claude/rules/code-review-fanout.md": (RULE_CODE_REVIEW_FANOUT, False),
        ".claude/rules/codex-contribution-guide.md": (RULE_CODEX_CONTRIBUTION, False),
        ".claude/rules/learning-capture.md": (RULE_LEARNING_CAPTURE, False),
        ".codex/hooks.json": (CODEX_HOOKS, False),
        ".githooks/pre-commit": (PRE_COMMIT_HOOK, True),
        ".githooks/pre-push": (PRE_PUSH_HOOK, True),
        ".github/workflows/ci.yml": (CI_WORKFLOW, False),
        ".github/PULL_REQUEST_TEMPLATE.md": (PR_TEMPLATE, False),
        ".github/ISSUE_TEMPLATE/bug_report.md": (ISSUE_BUG, False),
        ".github/ISSUE_TEMPLATE/feature_request.md": (ISSUE_FEATURE, False),
        ".devcontainer/devcontainer.json": (DEVCONTAINER, False),
    }


def _slug_to_package(name: str) -> str:
    """Derive a valid importable package name from a directory name."""

    pkg = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    if not pkg or not pkg[0].isalpha():
        pkg = f"pkg_{pkg}" if pkg else "pkg"
    return pkg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold an agentic Python repo.")
    parser.add_argument("target", help="directory to scaffold into")
    parser.add_argument("--package", help="importable package name (default: from dir name)")
    parser.add_argument(
        "--force", action="store_true", help="write into a non-empty directory"
    )
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    repo = target.name
    pkg = args.package or _slug_to_package(repo)

    if not re.fullmatch(r"[a-z][0-9a-z_]*", pkg):
        print(f"error: invalid package name {pkg!r} (use lowercase, _, start with a letter)")
        return 2

    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()) and not args.force:
        print(f"error: {target} is not empty (pass --force to scaffold anyway)")
        return 2

    today = datetime.date.today()
    fmt = {
        "pkg": pkg,
        "repo": repo,
        "date": today.isoformat(),
        "year": str(today.year),
        # Owner is unknown at scaffold time; CODEOWNERS / LICENSE carry a
        # placeholder the user replaces. Keep it obvious.
        "owner": "OWNER",
    }
    files = _files(pkg)
    written = 0
    for relpath, (template, executable) in sorted(files.items()):
        dest = target / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = template.format(**fmt)
        dest.write_text(content, encoding="utf-8", newline="\n")
        if executable:
            dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written += 1

    # The codex skill-discovery symlink: .agents/skills -> .claude/skills/learned
    # (relative to .agents/, so the target is ../.claude/skills/learned).
    # The target is ALWAYS forward-slash: a git symlink blob written with
    # backslashes will not resolve on Linux / macOS / CI.
    agents_dir = target / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    symlink_path = agents_dir / "skills"
    symlink_target = "../.claude/skills/learned"
    try:
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        symlink_path.symlink_to(symlink_target)
        symlink_note = "created"
    except OSError:
        # Windows without Developer Mode: write the link content as a file so
        # `git add` + a later `git config core.symlinks true` checkout fixes it.
        symlink_path.write_text(symlink_target, encoding="utf-8", newline="\n")
        symlink_note = "fallback file written (run: git config core.symlinks true)"

    print(f"Scaffolded {written} files into {target}")
    print(f"  package name : {pkg}")
    print(f"  .agents/skills symlink : {symlink_note}")
    print()
    print("Next steps:")
    print(f"  cd {target}")
    print("  git init                                  # if not already a repo")
    print("  git add -A")
    print("  python -m venv .venv && . .venv/bin/activate   # or the Windows activate")
    print("  just install                              # editable install + hooks + symlink")
    print("  just check                                # verify the scaffold (lint + arch + test)")
    print()
    print("GitHub setup (after `git push` to a new GitHub repo):")
    print("  - Edit .github/CODEOWNERS: replace @OWNER with the real owner/team.")
    print("  - Apply gated builds + required PR review (run once, as a repo admin):")
    print(f"      REPO=<owner>/{repo} bash scripts/apply-branch-protection.sh")
    print("    See docs/BRANCH_PROTECTION.md for what it enforces.")
    print()
    print("Optional - the superpowers plugin (spec-driven workflows):")
    print("  claude plugin marketplace add obra/superpowers")
    print("  claude plugin install superpowers@superpowers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
