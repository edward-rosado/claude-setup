---
name: ecc-windows-unicode-fix
description: "ECC instinct-cli crashes on Windows cp1252 -- set PYTHONIOENCODING=utf-8 for Unicode output"
user-invocable: false
origin: auto-extracted
---

# ECC Instinct CLI Windows Unicode Fix

**Extracted:** 2026-03-14
**Context:** Running ECC continuous-learning-v2 instinct-cli.py commands on Windows

## Problem
The instinct-cli.py `status` and `evolve` commands print Unicode bar characters
(like `█`) for confidence visualization. On Windows, Python defaults to cp1252
encoding which cannot encode these characters, causing:

```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 4-13:
character maps to <undefined>
```

The script crashes partway through output -- you see partial results then a traceback.

## Solution
Prefix any instinct-cli.py command with `PYTHONIOENCODING=utf-8`:

```bash
PYTHONIOENCODING=utf-8 python3 "path/to/instinct-cli.py" status
PYTHONIOENCODING=utf-8 python3 "path/to/instinct-cli.py" evolve
```

This tells Python to encode stdout as UTF-8 instead of the Windows default cp1252.

## When to Use
- Running any ECC instinct-cli.py command on Windows
- Any Python script that prints Unicode characters on Windows
- Seeing `UnicodeEncodeError: 'charmap'` errors from Python on Windows
