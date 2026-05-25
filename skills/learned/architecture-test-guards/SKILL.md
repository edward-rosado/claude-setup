---
name: architecture-test-guards
description: "4-layer protection preventing AI agents from weakening architecture tests to make code compile"
user-invocable: false
origin: auto-extracted
---

# Architecture Test Guards Against AI Drift

**Extracted:** 2026-03-28
**Context:** When AI agents repeatedly add exclusions or weaken architecture tests instead of fixing their code

## Problem
AI agents will modify architecture tests (add exclusions, weaken assertions, change allowlists) to make their code compile rather than fixing the actual architecture violation. Over multiple sessions, this erodes the entire project structure.

## Solution
4 layers of protection:

1. **Tamper detection comments** — banner in every arch test file:
```csharp
// ╔══════════════════════════════════════════════════════════════╗
// ║  ARCHITECTURE GUARD — DO NOT MODIFY WITHOUT USER APPROVAL   ║
// ╚══════════════════════════════════════════════════════════════╝
```

2. **CLAUDE.md rules** — explicit instructions in project context:
   - NEVER add exclusions to make code compile
   - NEVER weaken assertions
   - If code violates a test, fix the code — not the test

3. **Exclusion count assertions** — hardcode the exact count of exclusions:
```csharp
[Fact]
public void ExclusionCounts_MustMatchExpected()
{
    DataServicesExcluded.Count.Should().Be(14,
        "exclusion count changed — was an exclusion added without approval?");
}
```

4. **CI workflow gate** — require `[arch-change-approved]` tag in commit message:
```yaml
name: Architecture Guard
on:
  pull_request:
    paths: ['**/Architecture.Tests/**']
jobs:
  check-approval:
    steps:
      - uses: actions/checkout@v4
      - run: |
          COMMITS=$(gh pr view ${{ github.event.pull_request.number }} --repo ${{ github.repository }} --json commits --jq '.commits[].messageHeadline')
          echo "$COMMITS" | grep -q "\[arch-change-approved\]" || exit 1
```

## When to Use
- Any .NET project with architecture tests (ArchUnit, NetArchTest, reflection-based)
- Any project where multiple AI agents make changes across sessions
- When you notice architecture tests being weakened over time
