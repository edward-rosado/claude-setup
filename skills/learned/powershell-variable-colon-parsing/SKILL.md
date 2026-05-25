---
name: powershell-variable-colon-parsing
description: "PowerShell interprets $var: as scope-qualified variable -- use ${var}: for literal colon after variable"
user-invocable: false
origin: auto-extracted
---

# PowerShell Variable-Colon Parsing Trap

**Extracted:** 2026-03-14
**Context:** Writing PowerShell scripts that interpolate variables followed by colons in strings

## Problem
PowerShell treats `$variable:` as a scope/drive-qualified variable reference (like `$env:PATH`, `$script:counter`). When a variable is followed by a literal colon in a double-quoted string, PowerShell throws:

> Variable reference is not valid. ':' was not followed by a valid variable name character.

Example that fails:
```powershell
Write-Host "For $customWebsite: ensure the zone is added"
```

## Solution
Wrap the variable name in braces to delimit it from the colon:
```powershell
Write-Host "For ${customWebsite}: ensure the zone is added"
```

The `${}` syntax explicitly marks where the variable name ends, so PowerShell treats the colon as a literal character.

## When to Use
- Any time a PowerShell double-quoted string contains `$variable:` where the colon is meant as punctuation
- Common in status messages, log output, and user-facing script output
- Also applies to other delimiter characters that PowerShell might interpret (e.g., `$var.method` vs `${var}.literal`)
