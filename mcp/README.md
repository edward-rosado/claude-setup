# MCP Setup

Declarative + scripted installation of [Model Context Protocol](https://modelcontextprotocol.io/) servers for Claude Code.

## What gets installed

| Server | Scope | Purpose | Auth |
| --- | --- | --- | --- |
| **Playwright** | user | Browser automation — E2E render-checks, scraping, visual verification | none |

Plugin-managed MCPs (Notion, Slack, Gmail, Figma, Google Drive, ms365, GitHub Copilot, Remotion media/ElevenLabs/TwelveLabs/Pexels/Replicate) are NOT in this file — they auto-install when their plugin is enabled in [`../settings.json`](../settings.json) and complete OAuth in the Claude Code UI.

## Install

```bash
# macOS / Linux
./setup.sh --mcp

# Windows
.\setup.ps1 -Mcp
```

Idempotent: re-running skips already-installed servers (checked via `claude mcp get <name>`). Failures on individual servers print a warning and continue with the rest.

You can run it alongside the normal install:

```bash
./setup.sh --install --mcp
```

## Adding a server

1. Edit [`servers.json`](./servers.json) — add an entry under `servers`. Fields:
   - `transport`: `stdio` (most common), `http`, or `sse`
   - `command` + `args`: for stdio, the executable and its argv
   - `url`: for http / sse, the endpoint
   - `purpose`: human-readable one-liner describing when to use it
   - `auth`: `none` / `oauth` / `api-key`
   - `docs`: upstream URL
2. Re-run `./setup.sh --mcp` (or `.\setup.ps1 -Mcp`).
3. Commit `servers.json`.

## Why this lives in the repo

A new machine should get the same MCP loadout as every other machine, with zero remembered-command friction. `claude mcp add ...` is one-liner-per-server; a declarative source of truth makes the loadout reproducible and reviewable.

Plugin-managed MCPs are already declarative (via `enabledPlugins` in `settings.json`). This file picks up the stragglers that don't ship as part of a plugin.

## Why Playwright

A pattern that repeatedly shows up in agent sessions: a CI deploy "passes," `curl` returns HTTP 200, but the page actually crashes client-side or renders the wrong content. `WebFetch` can't see this; only a real browser can. The Playwright MCP server gives agents a `navigate`, `wait_for_selector`, `screenshot`, `evaluate` surface so any session can render-check without manual setup.

## References

- [Playwright MCP server (microsoft/playwright-mcp)](https://github.com/microsoft/playwright-mcp)
- [Claude Code MCP docs](https://docs.claude.com/en/docs/claude-code/mcp)
- [MCP spec](https://modelcontextprotocol.io/)
