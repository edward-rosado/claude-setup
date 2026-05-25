---
name: github-actions-upload-artifact-silent-fail
description: "upload-artifact@v4 silently succeeds with 0 files by default; always set if-no-files-found: error"
user-invocable: false
origin: auto-extracted
---

# GitHub Actions upload-artifact Silent Failure

**Extracted:** 2026-03-16
**Context:** When sharing build artifacts between GitHub Actions jobs using upload-artifact/download-artifact v4

## Problem
`actions/upload-artifact@v4` defaults to `if-no-files-found: warn`. When the upload path matches zero files (wrong path, build output in unexpected location, etc.), the step completes with **status: success** — no error, no failure. The downstream `actions/download-artifact@v4` then fails with:

```
Unable to download artifact(s): Artifact not found for name: <name>
```

The artifact appears in the job step list as "completed success" but does NOT appear in the run's artifact list (`gh api repos/{owner}/{repo}/actions/runs/{id}/artifacts`). This makes it very hard to diagnose — you think the upload worked but the download is broken.

## Solution

Always set `if-no-files-found: error` on upload-artifact to fail fast:

```yaml
- name: Upload build output
  uses: actions/upload-artifact@v4
  with:
    name: my-build
    path: apps/my-app/.output/
    if-no-files-found: error   # CRITICAL: default is 'warn' which silently succeeds
    retention-days: 1
```

### Debugging checklist when "Artifact not found" occurs:

1. Check the **artifact list** for the run — not the step status:
   ```bash
   gh api repos/{owner}/{repo}/actions/runs/{run_id}/artifacts
   ```
   If your artifact name is missing, the upload silently failed.

2. Verify the upload path matches what the build actually produces. Add a debug step:
   ```yaml
   - name: Debug build output
     run: ls -la apps/my-app/.output/ || echo "Directory does not exist"
   ```

3. Check if the upload step had a conditional (`if:`) that evaluated to false.

4. Verify the download `path` restores files to the right location. `upload-artifact` stores files **relative to the upload path**, so downloading to a parent directory won't recreate the subdirectory structure.

## When to Use
- Setting up artifact sharing between GitHub Actions jobs
- Debugging "Artifact not found" errors in download-artifact
- Any CI pipeline using upload-artifact@v4 or later
