# claude-setup

Portable AI tooling configuration for Claude Code.

## Quick Start

```bash
git clone git@github.com:edward-rosado/claude-setup.git
cd claude-setup
chmod +x setup.sh
./setup.sh --install
```

## What Gets Installed

| Component | Source | Target |
|-----------|--------|--------|
| Rules (9) | `rules/workflow\|standards\|optimization/` | `~/.claude/rules/` (flattened) |
| Skills (5) | `skills/comms\|git\|lang/` | `~/.claude/skills/` (flattened) |
| Instincts | `learned/instincts/` | `~/.claude/homunculus/instincts/` |
| Settings | `settings.json` | Merged into `~/.claude/settings.json` |
| Plugins (7) | Declared in `settings.json` | Installed via Claude CLI |

## Mobile / iPad / Phone

Start a claude.ai session in the "Eddie's Workspace" project. The project instructions tell Claude to read this repo via GitHub MCP — no manual setup needed.

Offline fallback:
```bash
./setup.sh --generate-mobile
# Then paste mobile/project-knowledge.md into claude.ai Project Knowledge
```

## Commands

```bash
./setup.sh --install           # Install (symlinks + plugins)
./setup.sh --check             # Verify status
./setup.sh --generate-mobile   # Generate mobile instructions
./setup.sh --sync              # Pull new learned instincts
./setup.sh --uninstall         # Remove everything
./setup.sh --test              # Run tests
./setup.sh --install --dry-run # Preview without changes
```

## Platform Support

| Platform | Method |
|----------|--------|
| macOS / Linux | Native symlinks |
| Windows (Developer Mode) | Native symlinks via Git Bash |
| Windows (no Dev Mode) | Directory junctions + file symlinks |
| iPad / Android / Phone | claude.ai Project via GitHub MCP |
