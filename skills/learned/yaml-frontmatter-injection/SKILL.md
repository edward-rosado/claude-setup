---
name: yaml-frontmatter-injection
description: "Escape user input in YAML frontmatter to prevent key injection via newlines, colons, and quotes"
user-invocable: false
origin: auto-extracted
---

# YAML Frontmatter Key Injection via User Input

**Extracted:** 2026-03-20
**Context:** Any system that writes user-supplied strings into YAML frontmatter (markdown files, config files, static site generators)

## Problem
When user input is written into YAML frontmatter without escaping, a value containing newlines or colons can inject arbitrary YAML keys. Example:

A `firstName` of `"John\nstatus: closed"` produces:
```yaml
---
firstName: John
status: closed    # ← INJECTED KEY
lastName: Doe
---
```

When parsed back, the injected `status: closed` overrides the real status field. This is a **data integrity attack** — the attacker controls the parsed output of the document.

## Solution
YAML-quote all user-supplied string values and escape special characters:

```csharp
// C# / .NET
private static string EscapeYaml(string? value) =>
    value?.Replace("\\", "\\\\")
          .Replace("\"", "\\\"")
          .Replace("\n", "\\n")
          .Replace("\r", "\\r") ?? "";

sb.AppendLine($"firstName: \"{EscapeYaml(lead.FirstName)}\"");
```

```typescript
// TypeScript / JavaScript
function escapeYaml(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r');
}
```

**Key rules:**
- Always double-quote user-supplied values in YAML: `key: "escaped value"`
- Escape: backslash, double-quote, newline, carriage return
- Do NOT escape system-generated values (enums, UUIDs, timestamps) — only user input
- Add input validation as defense-in-depth: `[RegularExpression(@"^[^\r\n]+$")]` on freeform string fields

## When to Use
- Writing user input to YAML frontmatter (markdown documents, Hugo/Jekyll posts, Obsidian notes)
- Any template system that interpolates user strings into YAML
- Lead/contact/CRM systems storing data as markdown with frontmatter
- Static site generators accepting user-submitted content

## Testing
Every field written to YAML frontmatter should have a roundtrip injection test:
```csharp
[Theory]
[InlineData("John\nstatus: closed")]
[InlineData("Jane: \"Smith\"")]
[InlineData("O'Brien\\path")]
public void Render_WithMaliciousInput_DoesNotInjectKeys(string firstName)
{
    var result = renderer.RenderLeadProfile(lead with { FirstName = firstName });
    var parsed = YamlFrontmatterParser.Parse(result);
    Assert.DoesNotContain("status", parsed.Keys.Where(k => k != "status_field"));
    Assert.Equal(firstName, parsed["firstName"]);
}
```
