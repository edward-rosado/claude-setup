# Claude Setup — Design Document

**Date:** 2026-03-08
**Status:** Approved

## Problem

Eddie's AI tooling setup (Claude Code rules, skills, plugins, learned instincts) lives machine-wide in `~/.claude/`. This means:
- No version control — changes can be lost
- No portability — new machines start from scratch
- No mobile access — claude.ai on phone/iPad has no context
- No consistency — setup drifts across devices

## Solution

A single GitHub repo (`claude-setup`) that:
1. Is the canonical source of truth for all AI tooling configuration
2. Has a cross-platform setup script that symlinks everything into `~/.claude/`
3. Generates a mobile-friendly output for claude.ai Projects (phone/iPad)
4. Supports zero-touch mobile sessions via GitHub MCP integration

## Repo Structure

```
claude-setup/
├── rules/
│   ├── workflow/              # how you work
│   │   ├── agents.md
│   │   ├── development-workflow.md
│   │   └── git-workflow.md
│   ├── standards/             # how you code
│   │   ├── coding-style.md
│   │   ├── patterns.md
│   │   ├── security.md
│   │   └── testing.md
│   └── optimization/          # how you tune
│       ├── hooks.md
│       └── performance.md
├── skills/
│   ├── comms/                 # communication
│   │   └── eddie-voice/SKILL.md
│   ├── git/                   # git operations
│   │   ├── open-pr/SKILL.md
│   │   ├── update-pr/SKILL.md
│   │   └── pr-diagrams/SKILL.md
│   └── lang/                  # language-specific
│       └── dotnet/SKILL.md
├── learned/
│   └── instincts/             # patterns Claude learned about how you work
├── mobile/
│   ├── bootstrap.md           # Claude reads this first on mobile
│   └── project-knowledge.md   # auto-generated fallback (gitignored)
├── settings.json              # plugin manifest (no credentials)
├── setup.sh                   # cross-platform bootstrap
├── tests/
│   └── test_setup.sh          # idempotency + correctness tests
├── docs/
│   └── plans/
│       └── 2026-03-08-claude-setup-design.md  # this file
├── .gitignore
├── CLAUDE.md
└── README.md
```

## Setup Script (`setup.sh`)

### Flags
```
setup.sh --install           # symlink rules+skills, install plugins
setup.sh --generate-mobile   # build project-knowledge.md from all rules
setup.sh --sync              # pull new instincts from ~/.claude/ into repo
setup.sh --uninstall         # remove symlinks, restore backups
setup.sh --check             # dry-run, exit 0 if already installed
setup.sh --test              # run test suite
```

### Install Behavior
1. Detect platform (macOS/Linux/Windows)
2. Locate `~/.claude/`
3. Back up existing files that would be overwritten → `~/.claude/backups/`
4. Symlink each rule file (flattened): `rules/workflow/agents.md` → `~/.claude/rules/agents.md`
5. Symlink each skill directory (flattened): `skills/git/open-pr/` → `~/.claude/skills/open-pr/`
6. Symlink learned instincts: `learned/instincts/` → `~/.claude/homunculus/instincts/`
7. Merge settings into `~/.claude/settings.json` (env vars, plugin enables)
8. Register marketplaces and install plugins
9. Verify all symlinks resolve

### Platform Handling
| Platform | Symlink method |
|----------|---------------|
| macOS/Linux | `ln -sf` |
| Windows (Git Bash, Developer Mode) | `ln -sf` |
| Windows (fallback) | `cmd //c mklink` for files, `mklink /J` for dirs |

### Idempotency Guarantees
- Check if symlink already points to correct target → skip
- Check if backup already exists → skip
- Plugin install commands are naturally idempotent
- Running `--install` N times produces the same result as running it once

## Mobile/Web Delivery

### Zero-Touch (GitHub MCP)
- claude.ai Project "Eddie's Workspace" has one line in Project Knowledge:
  ```
  Read and follow all instructions from github.com/edward-rosado/claude-setup — start with mobile/bootstrap.md
  ```
- `bootstrap.md` tells Claude which repo files to read and in what order
- GitHub MCP integration handles auth (private repo, OAuth-based)
- No tokens stored in repo

### Offline Fallback
- `setup.sh --generate-mobile` concatenates all rules into `mobile/project-knowledge.md`
- Paste into claude.ai Project Knowledge manually
- Gitignored since it's a generated artifact

## Settings Manifest (`settings.json`)

Declarative plugin list — not a raw copy of `~/.claude/settings.json`:
```json
{
  "env": {
    "ECC_HOOK_PROFILE": "standard"
  },
  "plugins": [
    "everything-claude-code@everything-claude-code",
    "github@claude-plugins-official",
    "superpowers@claude-plugins-official",
    "figma@claude-plugins-official",
    "security-guidance@claude-plugins-official",
    "skill-creator@claude-plugins-official",
    "learning-output-style@claude-plugins-official"
  ],
  "marketplaces": {
    "everything-claude-code": {
      "source": "github",
      "repo": "affaan-m/everything-claude-code"
    }
  }
}
```

The setup script merges this into existing settings — never overwrites.

## Test Suite (`tests/test_setup.sh`)

1. Create temp `~/.claude-test/` directory
2. Run `--install` targeting temp dir
3. Assert all symlinks exist and resolve correctly
4. Assert settings.json has expected entries
5. Run `--install` again — assert no changes (idempotency)
6. Run `--uninstall` — assert clean state
7. Cleanup temp directory

## What's NOT in the Repo
- Credentials, tokens, OAuth (security risk)
- Session history (sensitive conversation content)
- Cache/metrics/file-history (machine-specific, auto-regenerated)

## Sync Workflow

```
Edit rule on laptop → commit + push → next mobile session auto-pulls
Claude learns new instinct → setup.sh --sync → commit + push → available everywhere
```
