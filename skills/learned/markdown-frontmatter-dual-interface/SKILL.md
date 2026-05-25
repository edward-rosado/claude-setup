---
name: markdown-frontmatter-dual-interface
description: "Use YAML frontmatter in markdown files as both human-readable docs and machine-indexable data store"
user-invocable: false
origin: auto-extracted
---

# Markdown + YAML Frontmatter as Dual-Purpose Interface

**Extracted:** 2026-03-19
**Context:** When generating documents that non-technical users read directly (Google Drive, GitHub, shared folders) but the system also needs to search, filter, and update programmatically.

## Problem

You need files that serve two audiences simultaneously:
1. **Humans** — clean, scannable documents with plain language, formatted numbers, and no jargon
2. **Machines** — structured, typed, indexable fields for search, filtering, status tracking, and round-trip updates

JSON/YAML files are machine-readable but hostile to non-technical users. Pure markdown is human-friendly but impossible to query programmatically.

## Solution

Use markdown files with YAML frontmatter split into two sections:

```markdown
---
# === System (internal, not displayed) ===
id: a1b2c3d4-e5f6-7890
status: active
createdAt: 2026-03-19T14:30:00Z
internalToken: hashed-abc123

# === Indexable (structured, searchable) ===
firstName: Jane
lastName: Doe
email: jane@example.com
score: 82
category: relocation
city: Kill Devil Hills
state: NC
tags: [relocation, high-score, pre-approved]
---

# Jane Doe

**Received March 19, 2026 at 2:30 PM**

## Contact
- **Phone:** (555) 123-4567
- **Email:** jane@example.com
```

### Key Architecture Decisions

1. **Frontmatter is the source of truth** — the markdown body is rendered FROM frontmatter data via a dedicated renderer class. Never parse the markdown body to extract data.

2. **Centralize rendering** — one static renderer class (e.g., `MarkdownRenderer.RenderProfile(model)`) owns all formatting. Change the layout in one place.

3. **Read-back via frontmatter only** — to update or query, parse YAML frontmatter, not the markdown body. Use a library like YamlDotNet or gray-matter.

4. **Tags for search** — auto-generate a `tags` array from structured fields for lightweight filtering without a full search engine.

5. **Status field for resumability** — store pipeline/workflow status in frontmatter so a retry mechanism can scan files and pick up where processing left off.

### Renderer Pattern (C#)

```csharp
public static class DocumentRenderer
{
    public static string Render(DomainModel model)
    {
        var sb = new StringBuilder();

        // YAML frontmatter — system + indexable data
        sb.AppendLine("---");
        sb.AppendLine($"id: {model.Id}");
        sb.AppendLine($"status: {model.Status}");
        sb.AppendLine($"name: {model.Name}");
        sb.AppendLine($"tags: [{string.Join(", ", model.Tags)}]");
        sb.AppendLine("---");
        sb.AppendLine();

        // Human-readable body — rendered from the same data
        sb.AppendLine($"# {model.Name}");
        sb.AppendLine();
        sb.AppendLine($"**Status:** {FormatStatus(model.Status)}");
        // ... format numbers, dates, etc. for human consumption

        return sb.ToString();
    }
}
```

### Path Centralization Pattern

When files live in a folder hierarchy, centralize all path construction:

```csharp
public static class DocPaths
{
    public const string Root = "My App";
    public const string ItemsFolder = "My App/Items";

    public static string ItemFolder(string name) => $"{ItemsFolder}/{name}";
    public static string ItemFile(string name) => $"{ItemsFolder}/{name}/Profile.md";
}
```

## When to Use

- Generating documents for non-technical users (Google Drive, Dropbox, shared folders)
- Need to search/filter/aggregate across documents later
- Files need a status field for workflow tracking or retry logic
- Multiple systems read/write the same files (human edits + programmatic updates)
- The folder IS the user interface — no portal or dashboard exists

## When NOT to Use

- Users never see the raw files (use JSON/database instead)
- High-frequency writes (frontmatter parsing adds overhead)
- Documents with no structured data component (pure prose)
