---
name: tailwind-v4-css-modules-reference
description: "Tailwind v4 CSS Modules require @reference 'tailwindcss' for @apply to resolve utility classes"
user-invocable: false
origin: auto-extracted
---

# Tailwind v4 CSS Modules Require @reference Import

**Extracted:** 2026-03-22
**Context:** Using `@apply` with Tailwind utility classes inside CSS Module files (`.module.css`) in Tailwind v4

## Problem

In Tailwind v4, CSS Modules are scoped and do NOT have access to Tailwind utilities by default. Using `@apply` in a `.module.css` file without the reference import causes build failures:

```
Error: cannot apply unknown utility class "flex"
```

This worked in Tailwind v3 without any special import. The change is non-obvious and causes failures across every CSS Module file.

## Solution

Add `@reference "tailwindcss";` at the top of every `.module.css` file that uses `@apply`:

```css
/* Component.module.css */
@reference "tailwindcss";

.container {
  @apply flex items-center justify-center px-4;
}
```

Without the `@reference` line, the `@apply` directive cannot resolve Tailwind utility classes because CSS Modules are scoped by default in v4.

## When to Use

- Writing or migrating CSS Module files (`.module.css`) in a Tailwind v4 project
- Extracting inline Tailwind classes from JSX into colocated CSS Modules
- Upgrading a project from Tailwind v3 to v4 that uses CSS Modules
- Build fails with "cannot apply unknown utility class" in `.module.css` files
