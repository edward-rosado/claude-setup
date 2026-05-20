# claude-setup

Eddie Rosado's AI tooling configuration — portable across machines and devices.

## What This Repo Is

The canonical source of truth for Claude Code rules, skills, plugins, and learned instincts. Changes here propagate to all machines via symlinks and to mobile/web via GitHub MCP integration.

## Structure

- `rules/` — Grouped into `workflow/`, `standards/`, `optimization/`
- `skills/` — Grouped into `comms/`, `git/`, `lang/`
- `learned/instincts/` — Patterns Claude learned about how Eddie works
- `mobile/` — Bootstrap file for claude.ai Projects (phone/iPad)
- `settings.json` — Plugin manifest (declarative, no credentials)
- `setup.sh` — bootstrap installer for macOS / Linux (and Git Bash)
- `setup.ps1` — Windows-native bootstrap installer (PowerShell)
- `.gitattributes` — forces LF on `*.sh` / `*.py` so a Windows clone
  never gets a CRLF-corrupted shell script

## Key Commands

macOS / Linux (`setup.sh`) — Windows (`setup.ps1`):

```bash
./setup.sh --install           # .\setup.ps1 -Install        — symlink into ~/.claude/
./setup.sh --check             # .\setup.ps1 -Check          — verify installation
./setup.sh --generate-mobile   # .\setup.ps1 -GenerateMobile — build mobile knowledge
./setup.sh --sync              # .\setup.ps1 -Sync           — pull new instincts
./setup.sh --test              # .\setup.ps1 -Test           — run test suite
./setup.sh --uninstall         # .\setup.ps1 -Uninstall      — remove (manifest-driven)
```

## Symlink behavior

- macOS / Linux: native symlinks.
- Windows: skill *directories* → junctions (no elevation). Rule/instinct
  *files* → real symlinks if Developer Mode is on, otherwise **copies**
  (a snapshot — re-run `-Install` after editing a rule).
- Both installers record a manifest (`~/.claude/.claude-setup-manifest`);
  `uninstall` removes exactly what was installed.

## Rules

- Never store credentials, tokens, or secrets in this repo
- Settings are merged, never overwritten
- Keep `setup.sh` and `setup.ps1` behaviorally in sync — a change to one
  is incomplete until the other matches
- Test idempotency before committing changes to either installer
- The `mobile/project-knowledge.md` file is gitignored (generated artifact)
