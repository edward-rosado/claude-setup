---
name: cross-branch-model-migration-merge
description: "Merge branches with renamed domain models: systematic type mapping, bulk test rewrite, worktree file copy"
user-invocable: false
origin: auto-extracted
---

# Cross-Branch Model Migration Merge

**Extracted:** 2026-03-20
**Context:** Merging two feature branches where one renamed core domain types (AgentConfig → AccountConfig, IAgentConfigService → IAccountConfigService)

## Problem
When merging branches that evolved independently, one branch may have renamed or restructured domain models. A straight `git merge` resolves text conflicts but leaves the codebase in a broken state — test files still reference old types, DI registrations use old class names, and property mappings are wrong. The build passes the merge but fails compilation.

## Solution

### Step 1: Build the mapping table
Before touching any code, grep for all old type references and build a complete mapping:

```
Old Type              → New Type
AgentConfig           → AccountConfig
AgentIdentity         → AccountAgent
AgentIntegrations     → AccountIntegrations
AgentWhatsApp         → AccountWhatsApp
IAgentConfigService   → IAccountConfigService
config.Id             → config.Handle
config.Identity       → config.Agent
GetAgentAsync()       → GetAccountAsync()
UpdateAgentAsync()    → UpdateAccountAsync()
GetAllAgentIdsAsync() → ListAllAsync() (return type changed!)
```

### Step 2: Fix production code first
Update DI registrations (Program.cs), service implementations, and any class renames. Build to verify.

### Step 3: Rewrite test files in bulk
Don't try find-and-replace — test files construct domain objects inline. Rewrite each test file using the mapping table. Key areas:
- Mock setup: `Mock<IOldService>` → `Mock<INewService>`
- Helper methods: `MakeConfig()` returning old type → returning new type
- Assertions: `It.Is<OldType>(...)` → `It.Is<NewType>(...)`
- Property access in assertions: `c.OldProp` → `c.NewProp`

### Step 4: Handle naming conflicts
When both branches define a class with the same name (e.g., `MultiChannelLeadNotifier`), rename one to avoid CS0104 ambiguity errors. Choose a name that clarifies the different responsibility (e.g., `CascadingAgentNotifier`).

### Step 5: Adapt worktree uncommitted changes
When the source branch has uncommitted work (renames, new files, modifications):
- **New/untracked files**: Copy directly with `cp` — patches don't include untracked files
- **Renames**: Copy from destination path, delete source path — `git diff` patches with renames are fragile on Windows
- **Modifications**: Copy modified files, then manually edit shared files (like Program.cs) that need both branches' changes merged
- **Never overwrite shared files** (Program.cs, DI config) — manually merge the additions

### Step 6: Build + test + commit
Run full build, then full test suite. The test count should increase (new tests from source branch), not decrease.

## When to Use
- Merging branches where one underwent a major domain model rename/restructure
- Integrating worktree uncommitted changes into a different branch
- Any merge where `git merge` succeeds but compilation fails due to type mismatches
- Monorepo projects with vertical slice architecture (changes are feature-scoped but share common types)

## Pitfalls
- **Return type changes**: `GetAllAgentIdsAsync() → ListAllAsync()` changed from `List<string>` to `List<AccountConfig>` — tests that mock the return value break silently if you only rename the method
- **init vs set properties**: New model may use `init` where old used `set` — test helpers that construct objects with object initializers work, but mutation in tests (`config.Status = "active"`) won't compile
- **Namespace changes**: Moving files (Submit/ → Services/) changes the namespace — update `using` statements in both production and test code
