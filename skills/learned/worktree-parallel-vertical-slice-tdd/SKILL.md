---
name: worktree-parallel-vertical-slice-tdd
description: "Parallel TDD implementation of vertical slices using git worktree isolation — prevents merge conflicts by design"
user-invocable: false
origin: auto-extracted
---

# Worktree-Isolated Parallel Vertical Slice TDD

**Extracted:** 2026-03-20
**Context:** Implementing a large feature (20+ tasks) across 5 phases using parallel subagents in isolated git worktrees

## Problem
Large features with many independent services/endpoints take hours sequentially. Parallel agents editing the same repo cause merge conflicts and race conditions on shared files like `Program.cs` or test helpers.

## Solution
Combine three patterns: **git worktree isolation**, **vertical slice architecture**, and **TDD subagents**.

### Why it works
Vertical slice architecture (REPR pattern: `Features/{Feature}/{Operation}/`) means each service lives in its own folder. When agents work on different slices, they never touch the same files. Git worktrees give each agent a clean working copy, so even if two agents build simultaneously, there's no filesystem contention.

### Execution pattern
1. **Analyze task dependency graph** — identify which tasks are independent (can run in parallel) vs dependent (must wait)
2. **Dispatch independent tasks as worktree agents** — each gets:
   - Full context of what already exists (interfaces, types, patterns)
   - Exact file paths to create (prevents overlap)
   - TDD contract: write tests first, then implement, then commit
   - Self-contained commit message
3. **Wait for completion, verify merge** — run full test suite after each batch merges
4. **Dispatch next dependency tier** — repeat with tasks that depended on the completed batch

### Template dispatch prompt
```
You are implementing Task N ({TaskName}) for {Feature}.
Branch: {branch}, Working dir: {path}

## What already exists
- {list interfaces, types, services this task depends on}

## Task: Create {ServiceName}
{exact specification with file paths, interface contracts, test cases}

### TDD: Write tests FIRST ({N} tests):
1. {test case with exact method signature}
...

### After implementation:
1. Run tests: dotnet test --filter "{TestClass}" -v n
2. Run ALL feature tests: dotnet test --filter "{Feature}" -v n
3. Commit with: "feat: {message}"
```

### Key rules
- **Never dispatch agents that touch the same file** — if two tasks modify `Program.cs`, serialize them
- **Stub interfaces early** — if Task B needs an interface from Task A, have Task B create the stub interface itself
- **Include existing type signatures in the prompt** — agents can't see each other's worktrees
- **Always verify after merge** — run the full test suite, not just the new tests

## When to Use
- Feature has 4+ independent tasks that don't share files
- Project uses vertical slice / REPR / feature-folder architecture
- Each task produces 1-3 new files in its own folder
- TDD is required (tests provide the merge safety net)

## When NOT to Use
- Tasks modify shared files (Program.cs, shared models, config)
- Tightly coupled code where changes cascade across files
- Small features (2-3 tasks) — overhead of worktree setup isn't worth it

## Results from Real-Estate-Star WhatsApp feature
- 22 tasks across 5 phases, 195 tests
- Peak parallelism: 4 concurrent agents
- Zero merge conflicts across all batches
- Total: ~30 min wall clock for what would have been ~3 hrs sequential
