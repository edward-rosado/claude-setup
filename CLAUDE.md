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
- `setup.sh` — Cross-platform bootstrap script

## Key Commands

```bash
./setup.sh --install           # Symlink everything into ~/.claude/
./setup.sh --check             # Verify installation
./setup.sh --generate-mobile   # Build mobile project knowledge
./setup.sh --sync              # Pull new instincts from ~/.claude/
./setup.sh --test              # Run test suite
./setup.sh --uninstall         # Remove symlinks
```

## Rules

- Never store credentials, tokens, or secrets in this repo
- Settings are merged, never overwritten
- Test idempotency before committing changes to setup.sh
- The `mobile/project-knowledge.md` file is gitignored (generated artifact)
