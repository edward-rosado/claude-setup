---
name: v8-unreachable-defensive-branches
description: "Fix V8 coverage gaps from defensive null checks on values guaranteed non-null by control flow"
user-invocable: false
origin: auto-extracted
---

# V8 Unreachable Defensive Branch Coverage Fix

**Extracted:** 2026-03-17
**Context:** React projects with 100% V8 branch coverage thresholds (vitest --coverage with v8 provider)

## Problem

V8 branch coverage counts `if (x) doSomething(x)` as two branches even when the false branch is unreachable due to control flow guarantees. Common in React `useEffect` cleanup functions:

```tsx
// ❌ False branch is unreachable — cleanup only runs when interval WAS set
useEffect(() => {
  if (paused) return; // early return = no cleanup function returned
  intervalRef.current = setInterval(fn, 5000);
  return () => {
    if (intervalRef.current) clearInterval(intervalRef.current); // false branch never hit
  };
}, [paused, fn]);
```

The cleanup function at lines 5-7 only executes when the effect *didn't* return early — meaning `intervalRef.current` was always assigned on line 3. The `if` guard's false branch is dead code.

## Solution

Remove the defensive guard. The underlying Web APIs handle null/undefined safely:

```tsx
// ✅ clearInterval(null) is a no-op per HTML spec
return () => { clearInterval(intervalRef.current!); };
```

**Safe-to-remove guards (Web API spec guarantees):**
- `clearInterval(null)` → no-op
- `clearTimeout(null)` → no-op
- `element.removeEventListener(type, null)` → no-op
- `cancelAnimationFrame(0)` → no-op

**NOT safe to remove** (will throw):
- `observer.disconnect()` on a null observer
- `controller.abort()` on a null AbortController
- `subscription.unsubscribe()` on a null subscription

## When to Use

- V8 coverage reports an uncovered branch on an `if (ref.current)` or `if (timer)` guard
- The guarded value is guaranteed non-null by the surrounding control flow
- The underlying API call is safe with null/undefined per spec
- You've exhausted test-based approaches (rerender, unmount timing) and the branch remains uncovered
