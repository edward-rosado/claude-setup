---
name: shared-library-extraction
description: "Checklist for moving app code to shared monorepo packages — env vars, error tracking, analytics, types"
user-invocable: false
origin: auto-extracted
---

# Shared Library Extraction Checklist

**Extracted:** 2026-03-16
**Context:** Moving hooks, API clients, or utilities from an app directory into a shared monorepo package (e.g., `apps/web/lib/` → `packages/ui/`)

## Problem
When code lives in an app, it freely depends on app-specific concerns: environment variables, error tracking (Sentry), analytics, runtime assumptions. Moving it to a shared package without addressing these creates broken imports, runtime crashes on different platforms (edge, SSR, browser), or silent regressions (lost error reporting).

## Solution

Before moving code to a shared package, audit for these 5 categories:

### 1. Environment Variables → Parameters
```typescript
// BAD: shared lib reads process.env (breaks in Cloudflare Workers edge runtime)
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5135";
export function submitCma(agentId: string, req: Request) { ... }

// GOOD: consumer passes the value
export function submitCma(apiBaseUrl: string, agentId: string, req: Request) { ... }
```

### 2. Error Tracking → onError Callback
```typescript
// BAD: shared lib depends on Sentry
import * as Sentry from "@sentry/nextjs";
catch (err) { Sentry.captureException(err); }

// GOOD: optional callback, consumer provides Sentry
export function useMyHook(options?: { onError?: (err: Error) => void }) { ... }
// Consumer: useMyHook({ onError: (err) => Sentry.captureException(err) })
```

### 3. Analytics → Post-Action Callbacks
Don't bake analytics calls into shared code. Let the consumer fire them:
```typescript
// Shared hook exposes state, consumer fires analytics
const { state } = useCmaSubmit(apiUrl);
useEffect(() => { if (state.phase === "submitted") trackConversion(); }, [state.phase]);
```

### 4. Types → Single Source of Truth
Move shared API types to a dedicated types package. The shared lib and all apps import from there — no re-declarations.
```
packages/shared-types/cma.ts  ← defines CmaSubmitRequest
packages/ui/cma-api.ts        ← imports from shared-types (never re-declares)
apps/portal/progress.ts       ← imports from shared-types
```

### 5. Config/Prop Blast Radius
Grep the entire codebase for removed config fields, deleted props, and renamed files. Things that reference the old code:
- Templates/layouts passing now-deleted props
- Type definitions with removed fields
- Test fixtures with old config values
- Documentation and architecture diagrams
- Schema files (JSON Schema, OpenAPI, etc.)

## When to Use
- Moving any module from `apps/*/` to `packages/*/` in a monorepo
- Extracting a hook, API client, or utility into a shared library
- When a spec review flags "this breaks in edge runtime" or "lost Sentry reporting"
