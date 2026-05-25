---
name: safe-branch-cleanup-diff-apply
description: "Clean up messy feature branches without force push using git diff | git apply on a new branch"
user-invocable: false
origin: auto-extracted
---

# Safe Branch Cleanup via Diff-Apply

**Extracted:** 2026-03-21
**Context:** When a feature branch has accumulated merge commits, cherry-picks, CI retrigger noise, and junk files, and you need a clean PR without force-pushing.

## Problem
Feature branches that depend on other feature branches accumulate noise:
- Duplicate commits from cherry-picks/merges of the dependency branch
- Empty "retrigger CI" commits
- Merge conflict resolution commits
- Temp/debug files (CI logs, .bak files)
- The PR diff shows far more changes than the actual feature

Rebasing would require a force push, which risks losing history and can confuse collaborators. The user may explicitly prohibit force pushes.

## Solution

1. **Create a new branch from the target base:**
   ```bash
   git checkout -b feat/my-feature-v2 origin/main
   ```

2. **Categorize files** from the old branch diff into logical groups:
   ```bash
   git diff origin/main feat/my-feature-old --name-status
   ```
   Categorize into: feature code, tests, config, docs, CI, JUNK (skip), already-in-base (skip).

3. **Apply each group as a patch:**
   ```bash
   # Preview first
   git diff origin/main feat/my-feature-old -- path/to/group/ file1.cs file2.cs | git apply --stat

   # Apply
   git diff origin/main feat/my-feature-old -- path/to/group/ file1.cs file2.cs | git apply
   ```

4. **Handle deletions separately** (diff won't show files that need deleting from base):
   ```bash
   git rm path/to/file-that-should-be-deleted.ts
   ```

5. **Commit each group with a clean message:**
   ```bash
   git add path/to/group/
   git commit -m "feat: descriptive message for this logical group"
   ```

6. **Push and create new PR**, close old PR with reference:
   ```bash
   git push -u origin feat/my-feature-v2
   gh pr create --base main --head feat/my-feature-v2 --title "..."
   gh pr close OLD_PR_NUMBER --comment "Superseded by #NEW_PR_NUMBER"
   ```

## Key Details

- **`git diff base old-branch -- paths | git apply`** is the core trick — it generates a patch of exactly the delta between base and the old branch for specific files, then applies it to the working tree. No commits are created until you explicitly `git add && git commit`.
- **Always `--stat` first** to preview what will be applied before actually applying.
- **Group order matters**: apply foundational types/config first (models, schemas), then feature code that depends on them, then tests, then CI/docs last.
- **Deletions aren't automatic**: if the old branch deleted a file that still exists in base, you must `git rm` it manually.
- **The old branch is preserved** — no history is lost, no force push needed.
- **Junk files** (CI logs, temp files, .bak) are simply never included in any `git diff` path list.
- **If `git apply` fails with conflicts**, use `git apply --3way` to get standard merge conflict markers you can resolve manually.

## When to Use

- Feature branch has 2x+ more commits than the actual logical changes
- Branch was built on top of another feature branch that has since merged
- Cherry-picks or merges created duplicate/conflicting commit history
- PR diff shows changes from a dependency branch mixed with feature changes
- User explicitly says "no force push" or "safest approach"
- `git log origin/main..HEAD` shows merge commits, retrigger commits, or noise
