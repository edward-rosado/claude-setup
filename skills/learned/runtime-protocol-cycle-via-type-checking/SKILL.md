---
name: runtime-protocol-cycle-via-type-checking
description: "Break circular imports between runtime_checkable Protocols by demoting cross-package Protocol annotations to TYPE_CHECKING-only."
user-invocable: false
origin: auto-extracted
---

# Break runtime-Protocol circular imports via TYPE_CHECKING

**Extracted:** 2026-05-19
**Context:** Python projects that use `typing.Protocol` (PEP 544) with `@runtime_checkable` for cross-package boundaries, where two packages naturally want to reference each other's Protocols.

## Problem

A `@runtime_checkable Protocol` is a **runtime object** — `isinstance(obj, MyProtocol)` works at runtime, so `MyProtocol` is evaluated and must be importable like any other class. This collides with the convention of declaring Protocols at package boundaries:

```text
package/
├── devices/
│   └── base.py         # defines Device Protocol with attribute: snapshot_decoder: SnapshotDecoder
└── snapshot/
    ├── __init__.py     # re-exports SnapshotDecoder, MockRuntime, ...
    ├── decoder.py      # defines SnapshotDecoder Protocol
    └── mock_runtime.py # uses Device + MidiOutbox in annotations
```

The trap:

1. `devices/base.py` adds `from ..snapshot.decoder import SnapshotDecoder` so `Device` can reference it as an attribute type.
2. Python evaluates `snapshot/__init__.py` whenever any submodule is imported (even `snapshot.decoder` directly).
3. `snapshot/__init__.py` imports `snapshot.mock_runtime`.
4. `snapshot/mock_runtime.py` has `from ..devices.base import Device, MidiOutbox` for type annotations.
5. But `devices.base` is **partially initialized** at this moment (step 1 isn't done yet).
6. `ImportError: cannot import name 'Device' from partially initialized module 'rytm_randomizer.devices.base' (most likely due to a circular import)`.

This isn't a bad design — it's the inherent cost of `@runtime_checkable`. The Protocol is a runtime object, so it can't be "demoted" everywhere. But you can demote it **at type-annotation-only sites**.

## Solution

In modules that use a Protocol **only as a type annotation** (never `isinstance(obj, Proto)`, never subclass it), import it under `TYPE_CHECKING` and use `from __future__ import annotations` so the annotation is a string literal at runtime:

```python
# snapshot/mock_runtime.py — uses Device + MidiOutbox only in type hints
from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    # Annotations only -- avoiding a runtime cycle with ``devices.base``,
    # which itself imports ``SnapshotDecoder`` / ``MutationPlanner`` from
    # the ``snapshot`` subpackage. ``from __future__ import annotations``
    # above means these names are never evaluated at runtime.
    from ..devices.base import Device, MidiOutbox


class BaseMockRuntime(ABC):
    def __init__(self, outbox: MidiOutbox) -> None:  # annotation only — string at runtime
        self._outbox: MidiOutbox = outbox  # same

    def capture_messages(self, plan: Any, *, device: Device) -> list[Any]:
        # ...
```

This breaks the cycle because `Device` and `MidiOutbox` are **never evaluated at runtime in this module** — the strings `"MidiOutbox"` and `"Device"` sit in `__annotations__`, but no `import` happens at module load.

## Decide which side gets the demotion

The rule: **demote on the consumer side, keep eager on the producer side**.

- Producer side: the module that *defines* the Protocol or that does `isinstance(obj, Proto)`. Must do eager `import`.
- Consumer side: the module that *only references* the Protocol in `:` annotations or `->` returns. Safe to demote to `TYPE_CHECKING`.

If both sides do `isinstance`, the design is genuinely circular and one side needs to be split — `TYPE_CHECKING` can't help.

## When to use

- ImportError mentioning "partially initialized module" between two packages that define Protocols.
- One module uses the Protocol only in `:` annotations or `->` returns.
- You've already verified neither module actually needs `isinstance(obj, Proto)` at runtime — type hints only.

## When NOT to use

- The annotation is needed by `pydantic` / `dataclasses(slots=True)` / runtime-introspection libraries that evaluate `__annotations__` eagerly. Some libraries call `typing.get_type_hints(cls)` which forces eager evaluation. In that case, you must break the cycle by splitting the module instead.
- Both modules genuinely need `isinstance(obj, Proto)` at runtime — that's a real circular dependency, not a type-hint cycle.
- Pre-3.10 code without `from __future__ import annotations` — the demotion only works if annotations are strings at runtime.

## Pitfalls

- **The `from __future__ import annotations` must be on the first import line** of the demoted module. Without it, Python evaluates annotations eagerly and the demotion does nothing.
- **`pyright` / `mypy` see the type, so type-checking still works** — but `pydoc` and `inspect.signature()` will surface unevaluated string annotations.
- **`runtime_checkable` is unaffected.** The Protocol is still callable as `isinstance(obj, Proto)` in modules that imported it eagerly — only the demoted module loses runtime access.
- **Don't conflate `TYPE_CHECKING` with `Protocol`.** They're orthogonal. Many `TYPE_CHECKING` usages exist for non-Protocol types. The specific value here is for Protocols-with-cycles.

## Why this is a quirk of Python Protocols specifically

In Java/C# interface terms, the equivalent of "demote a reference to a forward declaration" is automatic via the linker. In TypeScript, interfaces are erased at compile time. **In Python, `Protocol` is dual: a type-system thing AND a runtime thing, simultaneously.** This skill is specifically about the case where you want the type-system view (annotations) without paying the runtime cost (cycle).

If you find yourself reaching for this often, the deeper fix is to look at the import graph — usually a missed seam where one package should own the Protocol contract entirely, and the other package only implements it.
