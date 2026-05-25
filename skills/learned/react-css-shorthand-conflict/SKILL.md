---
name: react-css-shorthand-conflict
description: "Avoid mixing CSS shorthand (border) with longhand (borderColor) in React inline styles to prevent DOM reconciliation warnings"
user-invocable: false
origin: auto-extracted
---

# React CSS Shorthand/Longhand Conflict

**Extracted:** 2026-03-15
**Context:** React inline styles that toggle between two style objects where one uses shorthand and the other uses longhand CSS properties.

## Problem
React warns: "Removing a style property during rerender (borderColor) when a conflicting property is set (border) can lead to styling bugs."

This happens when one style object uses `border` (shorthand) and another spreads it then adds `borderColor` (longhand). On toggle, React removes the longhand property while the shorthand still exists, causing unpredictable browser behavior.

## Solution
Never mix CSS shorthand and longhand properties in React inline styles that may be toggled or spread together. Use only longhand properties:

```tsx
// BAD — shorthand + longhand conflict
const base: React.CSSProperties = {
  border: "2px solid #e0e0e0",  // shorthand sets borderWidth + borderStyle + borderColor
};
const checked: React.CSSProperties = {
  ...base,
  borderColor: "#1B5E20",  // longhand overrides shorthand's borderColor
};

// GOOD — all longhand, no conflict
const base: React.CSSProperties = {
  borderWidth: 2,
  borderStyle: "solid",
  borderColor: "#e0e0e0",
};
const checked: React.CSSProperties = {
  ...base,
  borderColor: "#1B5E20",  // cleanly overrides same property
};
```

This applies to all CSS shorthand families: `border`/`borderColor`, `margin`/`marginTop`, `padding`/`paddingLeft`, `background`/`backgroundColor`, etc.

## When to Use
- Writing React components with inline styles that toggle between style variants
- Spreading a base style object and overriding individual properties
- Any time you see the "Removing a style property during rerender" console error
