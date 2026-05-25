---
name: tailwind-v4-native-binding-ci
description: "Fix Tailwind v4 @tailwindcss/oxide native binding failures on cross-platform CI in npm workspace monorepos"
user-invocable: false
origin: auto-extracted
---

# Tailwind v4 Native Binding CI Fix

**Extracted:** 2026-03-15
**Context:** npm workspace monorepo with Tailwind v4, package-lock.json generated on Windows, CI runs on Linux

## Problem
Tailwind v4 uses `@tailwindcss/oxide`, a Rust-compiled native binding with platform-specific packages (`@tailwindcss/oxide-linux-x64-gnu`, `@tailwindcss/oxide-darwin-arm64`, etc.). When `package-lock.json` is generated on one OS (e.g., Windows) and `npm ci` runs on another (e.g., Linux CI), npm skips the target platform's optional native dependency due to [npm#4828](https://github.com/npm/cli/issues/4828).

**Symptom:** Build fails with:
```
Error: Cannot find native binding.
Caused by: Error: Cannot find module '@tailwindcss/oxide-linux-x64-gnu'
```

Lint and test steps pass (vitest can disable PostCSS). Only `next build` / production builds fail because they invoke PostCSS -> Tailwind -> oxide.

## Solution

### CI Workflow Fix
Add `npm rebuild @tailwindcss/oxide` after `npm ci` in every CI job that runs a build:

```yaml
- name: Install dependencies
  run: npm ci

- name: Fix Tailwind native bindings (npm#4828)
  run: npm rebuild @tailwindcss/oxide || true
```

The `|| true` prevents failure if oxide isn't installed (e.g., a workspace package that doesn't use Tailwind).

### Vitest Fix (tests only)
Disable PostCSS processing in vitest config to avoid the same error in test environments:

```typescript
// vitest.config.ts
export default defineConfig({
  css: {
    postcss: {}, // empty object disables PostCSS processing
  },
});
```

### Stale Lockfile Cleanup
In npm workspace monorepos, only the **root** `package-lock.json` should exist. Per-app lockfiles (`apps/*/package-lock.json`) confuse npm's dependency hoisting and worsen the native binding issue. Remove them:

```bash
git rm apps/*/package-lock.json
```

## When to Use
- Tailwind v4 project with `@tailwindcss/oxide` in dependencies
- npm workspaces monorepo
- CI environment differs from dev machine OS
- Build fails with "Cannot find native binding" but tests pass
- `package-lock.json` was generated on a different platform than CI
