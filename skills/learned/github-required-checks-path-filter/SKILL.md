---
name: github-required-checks-path-filter
description: "Fix GitHub required status checks that wait forever when path-filtered workflows don't trigger"
user-invocable: false
origin: auto-extracted
---

# GitHub Required Status Checks with Path-Filtered Workflows

**Extracted:** 2026-03-16
**Context:** Any GitHub repo with branch protection required status checks AND workflows that use `paths:` filters

## Problem

When a GitHub Actions workflow uses `paths:` to only trigger on certain file changes, and that
workflow's job name is a **required status check** in branch protection, PRs that don't touch
those paths will have the check stuck at "Waiting for status to be reported" forever. The merge
button stays blocked.

A second variant: the required check name doesn't exactly match the workflow job `name:` field
(e.g., em dash `—` vs double hyphen `--`, or "build" vs "coverage"). The workflow runs and
passes, but the required check never gets satisfied because GitHub matches on exact string.

## Solution

### Variant 1: Path-filtered workflow never triggers

Use `dorny/paths-filter` to detect changes, then define two jobs with the **same `name:`** —
one runs the real work, the other is a no-op skip. Only one runs per PR, but GitHub always
sees the required check name reported.

```yaml
name: API

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  # NOTE: No paths filter here — workflow always triggers

jobs:
  changes:
    name: "Detect changes"
    runs-on: ubuntu-latest
    outputs:
      api: ${{ steps.filter.outputs.api }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            api:
              - 'apps/api/**'
              - '.github/workflows/api.yml'

  build-and-test:
    name: "API — build and test"      # Must match branch protection exactly
    needs: changes
    if: needs.changes.outputs.api == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # ... real build/test steps ...

  skip:
    name: "API — build and test"      # Same name — GitHub sees the check reported
    needs: changes
    if: needs.changes.outputs.api != 'true'
    runs-on: ubuntu-latest
    steps:
      - run: echo "No API changes — skipping."
```

### Variant 2: Job name doesn't match required check

Ensure the `name:` field in the workflow job matches the required status check **exactly** —
including Unicode characters (em dash vs hyphen), casing, and spacing.

```yaml
# Branch protection requires: "Agent Site — lint, test, coverage"
# BAD:  name: "Agent Site -- lint, test, build"    # wrong dash, wrong word
# GOOD: name: "Agent Site — lint, test, coverage"  # exact match
```

### Diagnosing

```bash
# List required status checks for a branch
gh api repos/{owner}/{repo}/branches/main/protection/required_status_checks \
  --jq '.checks[].context'

# Compare against actual workflow job names
grep -r '^\s*name:' .github/workflows/*.yml
```

## When to Use

- PR checks show "Waiting for status to be reported" and never complete
- Branch protection blocks merge despite all visible CI checks passing
- Adding a new path-filtered workflow to a repo with required status checks
- Renaming workflow jobs in a repo with branch protection
