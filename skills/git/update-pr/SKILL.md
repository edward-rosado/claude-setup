---
name: update-pr
description: Update an existing pull request with new changes from the current branch using GitHub MCP tools. Use when the user asks to update a PR, refresh a pull request description, or sync PR details with the latest branch changes. Also use proactively after committing and pushing changes to a branch that has an open PR, to keep the description and diagrams in sync.
---

# Update Pull Request

Update an existing pull request with new changes from the current branch using GitHub MCP tools.

**IMPORTANT: Prefer the GitHub MCP server tools (`mcp__github-mcp-server__*`) for all GitHub operations. If MCP tools fail or are unavailable, fall back to the `gh` CLI.**

## MCP Tools Reference

Use `ToolSearch` to load these tools before calling them:
- `mcp__github-mcp-server__search_pull_requests` — find PRs by branch name
- `mcp__github-mcp-server__pull_request_read` — get PR details, diff, files
- `mcp__github-mcp-server__update_pull_request` — update PR title, body, state

## Instructions

1. **Detect repository context** by running:
   ```
   gh repo view --json owner,name,defaultBranchRef --jq '{org: .owner.login, repo: .name, base: .defaultBranchRef.name}'
   ```
   Use the returned values as `<owner>`, `<repo>`, and `<base-branch>` throughout all subsequent steps and commands.
2. **Detect the current branch** using `git branch --show-current`
3. **Find the PR for the current branch** using `mcp__github-mcp-server__search_pull_requests` with query `head:<branch-name> is:open`, owner `<owner>`, repo `<repo>`
   - If no PR is found, ask the user for the PR number
   - If a PR is found, use its number
4. **Get current PR details** using `mcp__github-mcp-server__pull_request_read` with method `get` to retrieve the title and body
5. **Check for PBI ticket number in PR title**:
   - If the PR title already starts with a PBI ticket number (e.g., "AB#1488592 Fix..."), use that ticket number and skip prompting
   - If the PR title does NOT start with a PBI ticket number, prompt for PBI ticket number (required):
     - Ask: "Enter the PBI ticket number (e.g., AB#1487081):"
     - Continue prompting until a valid ticket number is provided
6. **Push the current branch** to origin (`git push origin <branch-name>`)
7. **Get the diff** using `mcp__github-mcp-server__pull_request_read` with method `get_diff` and also run `git diff --stat <base-branch>..HEAD` locally
   - The base branch is available from the PR details (`base.ref`)
   - Compare against the merge target branch, not incremental commits
   - The PR description should reflect the **final state of changes** compared to the base branch
   - **Exclude inherited commits**: Also run `git log --oneline <base-branch>..HEAD` and check if any commits were already merged to the base branch via other PRs (look for PR merge indicators like `(#NNN)` suffixes in commit messages). These are inherited from a parent branch and should NOT be described in this PR. Only describe work that is unique to this branch.
8. **Update PR description** to reflect:
   - **All changes compared to the base branch** (describe the complete diff, not incremental updates)
   - **Focus on WHAT changed from user/business perspective, not HOW it was implemented**
   - Describe business capabilities and user-facing changes, not technical implementation details
   - Maintain existing description structure and content
   - Update sections to accurately represent what differs from the base branch
   - Write as if describing the complete feature/changes from the base branch perspective
9. **Update PR title**:
   - If the changes significantly change the PR's purpose, update the title
   - Ensure the PBI ticket number is prepended to the title: `"<PBI_TICKET> <title>"`
   - Example: If PBI is "AB#1487081" and title is "Fix system account type mismatch", ensure it's "AB#1487081 Fix system account type mismatch"
   - If the current title already has the correct PBI ticket number, preserve it
   - If a PBI ticket number was extracted from the existing title, use that; otherwise use the one provided during prompting
10. **Update the PR** using `mcp__github-mcp-server__update_pull_request` with:
   - `owner`: `<owner>`
   - `repo`: `<repo>`
   - `pullNumber`: the PR number
   - `title`: the updated title (if changed)
   - `body`: the updated description
11. **Post architecture diagrams** by invoking the `pr-diagrams` skill with the PR number
    - The `pr-diagrams` skill saves files to `docs/architecture/`, commits, and pushes them before posting the PR comment — so the diagram source files are included in the PR diff
12. **Return the PR URL** as a clickable markdown link:
    - Example: `[View Pull Request](https://github.com/<owner>/<repo>/pull/828)`

## Context

- Organization: detected dynamically from `gh repo view` (`<owner>`)
- Repository: detected dynamically from `gh repo view` (`<repo>`)
- Base branch: detected dynamically from `gh repo view` (`<base-branch>`)
- **Prefer GitHub MCP tools; fall back to `gh` CLI if MCP is unavailable**

## Error Handling

- If MCP tools fail with authentication errors, inform the user to check their MCP server configuration
- If the PR cannot be found for the current branch, ask the user for the PR number
- **Fallback**: If MCP tools fail or are unavailable, retry the same operations using the `gh` CLI:
  - Find PR: `gh pr view --json number,title,body,baseRefName,headRefName`
  - Get diff: `gh pr diff <number>`
  - Update title: `gh pr edit <number> --title "<title>"`
  - Update body: `gh pr edit <number> --body "<description>"`
  - Verify `gh` is authenticated first with `gh auth status`
  - If `gh` CLI also fails, inform the user they can update the PR manually on GitHub web interface

## PR Description Guidelines

- **Describe differences from `<base-branch>`, NOT incremental development changes**
- **Only describe commits unique to this branch** — if the branch was created from a parent feature branch, commits inherited from the parent that were already merged via separate PRs (identifiable by `(#NNN)` PR suffixes in commit messages) must be excluded from the description. The PR should only cover the work done on this specific branch.
- **Focus on business capabilities and user-facing changes, NOT implementation details**
  - Describe WHAT changed (e.g., "Users can now retrieve account variables")
  - Avoid HOW it was implemented (e.g., avoid "database-backed", "VariableRepository", "PostgreSQL", "Clean Architecture")
- Compare the final state of the branch against the base branch, not individual commits
- Never mention files, models, or features that never existed in the base branch
- Do not reference intermediate refactoring steps, consolidations, or deletions of files created in this branch
- Preserve existing PR description structure and content
- Update sections to accurately reflect the complete diff from the base branch
- **PBI ticket number is REQUIRED** in the title
- **Only prompt for PBI ticket number if the PR title doesn't already include one**
- If changes fundamentally change the PR purpose, consider updating the title
- Always push changes before updating the PR description
- Use past tense when describing what was added/changed
- **Do NOT list every test and function** that was modified:
  - Summarize changes by category (e.g., "Added 5 header verification tests")
  - Focus on "what was changed and why" not "list of all changes"
  - Keep PR descriptions concise and high-level
