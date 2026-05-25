---
name: ada-hidden-checkbox-pill-refactor
description: "Replace hidden checkbox + label pill toggles with button role=checkbox for full-area click and ADA compliance"
user-invocable: false
origin: auto-extracted
---

# ADA: Hidden Checkbox Pill → Button role="checkbox"

**Extracted:** 2026-03-16
**Context:** Pill/toggle UI elements that visually look like buttons but use hidden checkboxes

## Problem
A common pattern uses `<span>` styled as a pill, containing a visually-hidden `<input type="checkbox">` and a `<label htmlFor>`. The label text is clickable via `htmlFor`, but the pill's padding area is dead space — users must click exactly on the text. No focus ring, no ARIA role, screen readers don't understand the toggle state.

```tsx
// BAD — only label text is clickable, no focus ring, no ARIA
<span style={{ ...pillStyles }}>
  <input type="checkbox" id="toggle"
    style={{ position: "absolute", opacity: 0, width: 0, height: 0, pointerEvents: "none" }} />
  <label htmlFor="toggle">I'm Buying</label>
</span>
```

## Solution
Replace with a single `<button>` using `role="checkbox"` and `aria-checked`:

```tsx
// GOOD — entire pill is clickable, keyboard-accessible, screen-reader friendly
<button
  type="button"
  role="checkbox"
  aria-checked={isChecked}
  className="pill-toggle"
  onClick={() => setIsChecked(v => !v)}
  style={isChecked ? pillChecked : pillBase}
>
  I'm Buying
</button>
```

Add focus-visible CSS:
```css
.pill-toggle:focus-visible {
  outline: 2px solid var(--color-primary, #1B5E20);
  outline-offset: 2px;
}
```

**Why `role="checkbox"` not `role="switch"`:** Use checkbox when selections are independent (user can pick multiple). Use switch for binary on/off of a single thing.

**Test updates:** Change `getByLabelText(/text/)` → `getByRole("checkbox", { name: /text/ })` and `.toBeChecked()` → `.toHaveAttribute("aria-checked", "true")`.

## When to Use
- Pill/toggle UI where a styled container wraps a hidden checkbox + label
- User reports "only clickable in the center" or "hard to click"
- ADA audit flags missing focus indicators or ARIA roles on toggle controls
