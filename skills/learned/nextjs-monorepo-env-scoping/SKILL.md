---
name: nextjs-monorepo-env-scoping
description: "Next.js resolves .env files from its own app directory, not the monorepo root — common cause of undefined NEXT_PUBLIC_* vars"
user-invocable: false
origin: auto-extracted
---

# Next.js Monorepo .env File Scoping

**Extracted:** 2026-03-15
**Context:** Monorepo with multiple Next.js apps (e.g., Turborepo, npm workspaces, pnpm workspaces)

## Problem

Environment variables defined in the monorepo root `.env` file are invisible to Next.js apps in subdirectories. `NEXT_PUBLIC_*` variables appear as `undefined` at runtime even though they exist in a `.env` file — because Next.js only reads `.env*` files relative to the directory containing `next.config.*`.

## Solution

Place `.env.local` (or `.env`) in each Next.js app's own directory:

```
monorepo/
  .env                    # NOT read by Next.js apps below
  apps/
    portal/.env.local     # Read by portal app
    agent-site/.env.local # Read by agent-site app
```

### Key behaviors

1. **Resolution path**: Next.js calls `loadEnvConfig(dir)` where `dir` is the app root (where `next.config.*` lives). It never walks up to parent directories.
2. **Build-time inlining**: `NEXT_PUBLIC_*` vars are replaced at build/start time via `DefinePlugin`. Changing `.env.local` requires restarting the dev server.
3. **Priority order**: `.env.local` > `.env.$(NODE_ENV)` > `.env` (all within the app directory).

### Diagnostic checklist

When a `NEXT_PUBLIC_*` var is undefined:

1. Verify the `.env*` file is in the same directory as `next.config.*`
2. Verify the variable name starts with `NEXT_PUBLIC_` (server-only vars are not exposed to the browser)
3. Restart the dev server after any `.env` change
4. Check for typos in the variable name (case-sensitive)

## When to Use

- Setting up a new Next.js app in a monorepo
- Debugging undefined `NEXT_PUBLIC_*` variables
- Moving environment config between monorepo root and app directories
- Onboarding a developer who added vars to the wrong `.env` file
