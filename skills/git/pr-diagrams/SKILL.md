---
name: pr-diagrams
description: Post Mermaid architecture diagrams as a comment on a pull request. Use when the user asks to add diagrams to a PR, or when invoked by the open-pr or update-pr skills after creating/updating a PR.
---

# PR Architecture Diagrams

Post Mermaid architecture diagrams as a comment on a pull request to help reviewers understand the changes at a glance.

## Instructions

1. **Detect repository context** by running:
   ```
   gh repo view --json owner,name,defaultBranchRef --jq '{org: .owner.login, repo: .name, base: .defaultBranchRef.name}'
   ```
   Use the returned values as `<owner>`, `<repo>`, and `<base-branch>` throughout all subsequent steps and commands.
2. **Determine the PR number**:
   - If a PR number was provided (e.g., by the calling skill or user), use it
   - Otherwise, detect the current branch (`git branch --show-current`) and look up the PR: `gh pr view --json number --jq .number`
3. **Check for existing diagram comment** — this is **critical** to avoid duplicate comments:
   - Run: `gh api repos/<owner>/<repo>/issues/<number>/comments --jq '[.[] | select(.body | startswith("## Architecture Diagrams"))] | first | .id'`
   - If an ID is returned (not null), **update** the existing comment: `gh api repos/<owner>/<repo>/issues/comments/<comment_id> -X PATCH -f body="..."`
   - **Only if no matching comment exists**, create a new one: `gh pr comment <number> --body "..."`
   - **NEVER post a second diagram comment** — always update the existing one
4. **Assess whether diagrams add value** before creating them:
   - **Skip diagrams** for small PRs (e.g., bug fixes, config changes, test-only changes, or PRs touching ≤ 3 files with no new architectural components). Instead, post a comment: `## Architecture Diagrams\n\nNo diagrams needed — this PR is a small, focused change.`
   - **Post diagrams** only for PRs that introduce new data flows, services, handlers, integrations, or significant structural changes
5. **Analyze the diff** to identify key flows, components, and interactions introduced or changed:
   - Run `gh pr diff <number> --name-only` to see changed files
   - Read the key files to understand the architecture
6. **Create 2-4 Mermaid diagrams** depending on complexity:
   - **Message/request routing**: How data flows through the system (entry point → processor → handler)
   - **Core logic flow**: The main business logic lifecycle with decision points, branching, and error handling
   - **Data model relationships**: How key entities, enums, or tables relate to each other (when the PR introduces new models)
   - Skip any diagram category that doesn't apply to the PR
7. **Save diagrams to `docs/architecture/`**:
   - Save each diagram as a separate markdown file in `docs/architecture/`
   - File name is the kebab-cased diagram heading (e.g., `### Message Routing` → `docs/architecture/message-routing.md`)
   - Each file contains the diagram heading as an `# H1`, a one-line description, and the Mermaid code block
   - Overwrite existing files with the same name (diagrams should reflect the latest state)
   - Create the `docs/architecture/` directory if it doesn't exist
8. **Update `docs/architecture/README.md`** to include any new diagram files:
   - Read the existing README to see the current table of contents
   - Add entries for any new diagram files under the appropriate category heading
   - If no existing category fits, create a new `##` heading for it
   - Do not remove or reorder existing entries
9. **Commit and push the diagram files** so they are included in the PR:
   - Stage only the `docs/architecture/` files: `git add docs/architecture/`
   - Commit: `git commit -m "Update architecture diagrams"`
   - Push to the current branch: `git push`
10. **Post the comment** with the diagrams (after the files are committed and pushed)

## Mermaid Syntax Rules

These rules are critical for correct rendering on GitHub:

### Line Breaks in Node Labels
- **NEVER** use `\n` for line breaks — it renders as literal text
- **ALWAYS** use `<br/>` inside quoted labels for multiline text
- Example: `Node["First line<br/>Second line"]`

### Node Labels
- Use double quotes for labels containing special characters: `Node["Label with spaces"]`
- Keep labels concise and business-oriented
- Use readable names, not class names (e.g., `"Set status to InProgress"` not `"UpsertAsync(SyncStates.InProgress)"`)

### Flow Direction
- Use `flowchart LR` for left-to-right routing/pipeline diagrams
- Use `flowchart TD` for top-down process/lifecycle flows

### Edges
- Solid lines (`-->`) for normal flow
- Dotted lines (`-.->`) for error/exceptional/recovery paths
- Labels on edges: `-->|"label text"|`

### Decision Nodes
- Use curly braces for diamond shapes: `Decision{"Question?"}`

### Subgraphs
- Group related concepts: `subgraph Title ["Display Name"]`
- Use for error recovery blocks, data models, or logical groupings

### Characters to Avoid
- Do NOT use parentheses `()` inside quoted node labels — they conflict with Mermaid's node shape syntax
- Use square brackets or rephrase instead
- Do NOT use pipe characters `|` inside node labels
- Escape or avoid special Mermaid characters in labels: `{}`, `()`, `[]`, `|`, `"`

## Diagram Style Guidelines

- Diagrams should clarify **what this PR changes**, not the entire system
- Each diagram gets a `###` heading and a one-line description
- The comment starts with `## Architecture Diagrams`
- Do NOT include implementation details like method signatures or fully qualified class names
- Keep each diagram focused on one concept
- Limit to 15 nodes per diagram for readability

## Context

- Organization: detected dynamically from `gh repo view` (`<owner>`)
- Repository: detected dynamically from `gh repo view` (`<repo>`)
