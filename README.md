# claude-setup

Portable AI tooling configuration for Claude Code. Two purposes:

1. **Make setting up a new machine easy** — one command symlinks all the
   rules, skills, and settings into `~/.claude/`.
2. **House global, cross-repo-cutting skills** — skills that are useful in
   *any* codebase (e.g. `create-python-repo`, which scaffolds a fully
   set-up Python repo), kept in one versioned place.

## Quick Start

**macOS / Linux:**

```bash
git clone https://github.com/edward-rosado/claude-setup.git
cd claude-setup
./setup.sh --install
```

**Windows** (PowerShell — the native path, no Git Bash required):

```powershell
git clone https://github.com/edward-rosado/claude-setup.git
cd claude-setup
.\setup.ps1 -Install
```

> **Windows symlinks.** Skill *directories* are linked as junctions (no
> elevation needed). Rule/instinct *files* cannot be junctions — with
> **Developer Mode** ON they are real symlinks; with it OFF they are
> **copied** (a snapshot — re-run `-Install` after editing a rule).
> Enable Developer Mode at *Settings → Privacy & Security → For
> Developers* for live file symlinks. `setup.sh` also works under Git
> Bash if you prefer bash.

**Prerequisite:** Python 3 must be on `PATH` — the settings merge uses it
(no `jq` dependency).

## What Gets Installed

| Component | Source | Target |
|-----------|--------|--------|
| Rules (9) | `rules/workflow\|standards\|optimization/` | `~/.claude/rules/` (flattened) |
| Skills (6) | `skills/comms\|git\|lang/` | `~/.claude/skills/` (flattened) |
| Instincts | `learned/instincts/` | `~/.claude/homunculus/instincts/` |
| Settings | `settings.json` | Merged into `~/.claude/settings.json` |
| Plugins | Declared in `settings.json` | Enabled via the merged `enabledPlugins` — Claude Code activates them on next start |

The installer records everything it creates in a manifest
(`~/.claude/.claude-setup-manifest`), so `--uninstall` removes exactly
what was installed and nothing else. Any pre-existing file it would
overwrite is backed up to `~/.claude/backups/` first.

## Commands

| macOS / Linux | Windows | Does |
|---|---|---|
| `./setup.sh --install` | `.\setup.ps1 -Install` | Symlink rules + skills, merge settings |
| `./setup.sh --check` | `.\setup.ps1 -Check` | Report installation status |
| `./setup.sh --uninstall` | `.\setup.ps1 -Uninstall` | Remove what was installed (backups kept) |
| `./setup.sh --generate-mobile` | `.\setup.ps1 -GenerateMobile` | Build `mobile/project-knowledge.md` |
| `./setup.sh --sync` | `.\setup.ps1 -Sync` | Pull new learned instincts into the repo |
| `./setup.sh --test` | `.\setup.ps1 -Test` | Run the test suite (needs bash) |
| `./setup.sh --install --dry-run` | `.\setup.ps1 -Install -DryRun` | Preview without changes |

## Skills

Global, cross-repo skills live under `skills/<category>/<name>/`. Notable:

- **`create-python-repo`** (`skills/lang/`) — scaffolds a new Python repo
  with the full agentic, spec-driven setup: an architecture-conformance
  test suite, parallel pytest, an automatic post-push code review, GitHub
  gating, the codex `.agents/skills` symlink, agent profiles, a dev
  container, and contribution guides. Ask Claude to "create a python
  repo" and it runs.

## Mobile / iPad / Phone

Start a claude.ai session in the "Eddie's Workspace" project. The project
instructions tell Claude to read this repo via GitHub MCP — no manual
setup needed.

Offline fallback:

```bash
./setup.sh --generate-mobile          # or:  .\setup.ps1 -GenerateMobile
# Then paste mobile/project-knowledge.md into claude.ai Project Knowledge
```

## Platform Support

| Platform | Installer | Symlink method |
|----------|-----------|----------------|
| macOS / Linux | `setup.sh` | Native symlinks |
| Windows + Developer Mode | `setup.ps1` (or `setup.sh` via Git Bash) | Native symlinks |
| Windows, no Dev Mode | `setup.ps1` | Junctions for skill dirs; copies for rule/instinct files |
| iPad / Android / Phone | — | claude.ai Project via GitHub MCP |

The repo ships a `.gitattributes` forcing LF line endings on `*.sh` /
`*.py`, so a Windows clone never gets a CRLF-corrupted shell script.
