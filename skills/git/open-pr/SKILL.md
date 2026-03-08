---
name: open_pr
description: Push the current branch and open a PR for all commits on the current branch using GitHub CLI (`gh`). Use when the user asks to open a PR, create a pull request, or submit their branch for review.
---

# Open Pull Request

Push the current branch and open a PR for all commits on the current branch using GitHub CLI (`gh`).

## Instructions

1. **Detect repository context** by running:
   ```
   gh repo view --json owner,name,defaultBranchRef --jq '{org: .owner.login, repo: .name, base: .defaultBranchRef.name}'
   ```
   Use the returned values as `<owner>`, `<repo>`, and `<base-branch>` throughout all subsequent steps and commands.
2. **Verify GitHub CLI** is available (`gh --version`) and authenticated (`gh auth status`)
   - If not authenticated or organization SAML authorization needed, prompt user to authorize
   - Organization SAML may require visiting the authorization URL or running `gh auth refresh -h github.com -s repo`
3. **Push the current branch** to origin (`git push origin <branch-name>`)
4. **Analyze changes from base branch** using `git diff --stat <base-branch>..HEAD` and `git log --oneline <base-branch>..HEAD`
   - Compare against the merge target branch (`<base-branch>`), not incremental commits
   - The PR description should reflect the **final state of changes** compared to the base branch
   - **Exclude inherited commits**: Check if any commits in the log were already merged to `<base-branch>` via other PRs (look for PR merge indicators like `(#NNN)` suffixes in commit messages). These are inherited from a parent branch and should NOT be described in this PR. Only describe work that is unique to this branch. When in doubt, run `gh pr list --state merged --search "<commit subject>"` to check if a commit was already PRed separately.
5. **Read the PR template** from `.github/pull_request_template.md` if it exists
6. **Prompt for PBI ticket number** (required):
   - Ask: "Enter the PBI ticket number (e.g., AB#1487081):"
   - Prepend it to the PR title (e.g., "AB#1487081 Fix system account type mismatch")
   - Continue prompting until a valid ticket number is provided
7. **Prompt for work item linking** (optional):
   - Ask: "Would you like to link a work item to this PR? (Enter work item number, or press Enter to skip)"
   - If provided, add it to the PR description under "Related Work" section
   - If skipped, omit the "Related Work" section
8. **Create comprehensive PR description** that includes:
   - Overview of the main purpose
   - All changes compared to the base branch (final state, not incremental development steps)
   - Proper security impact assessment
   - Testing details
   - **Focus on WHAT changed from user/business perspective, not HOW it was implemented**
   - Avoid mentioning specific technologies, frameworks, or architectural patterns unless they directly impact users
   - Be concise, don't get into implementation details
   - Describe what differs from the base branch, not the development history
9. **Create PR title**:
   - Use the primary commit message as the base (remove conventional commit prefixes like "feat:", "fix:", etc.)
   - Prepend the PBI ticket number: `"<PBI_TICKET> <title>"`
10. **Create PR using GitHub CLI**: `gh pr create --title "<PBI_TICKET> <title>" --body "<description>" --base <base-branch> --head <branch-name>`
11. **Post architecture diagrams** (only for non-trivial PRs) by invoking the `pr-diagrams` skill with the PR number
    - **Skip diagrams** for small PRs (e.g., bug fixes, config changes, or PRs touching ≤ 3 files with no new architectural components)
    - **Post diagrams** for PRs that introduce new data flows, services, handlers, integrations, or significant structural changes
    - The `pr-diagrams` skill saves files to `docs/architecture/`, commits, and pushes them before posting the PR comment — so the diagram source files are included in the PR diff
12. **Return the PR URL** as a clickable markdown link:
    - Example: `[View Pull Request](https://github.com/<owner>/<repo>/pull/828)`

## Context

- Organization: detected dynamically from `gh repo view` (`<owner>`)
- Repository: detected dynamically from `gh repo view` (`<repo>`)
- Base branch: detected dynamically from `gh repo view` (`<base-branch>`)
- PR template: `.github/pull_request_template.md`

## Authentication & Error Handling

- **GitHub CLI Authentication**: Check with `gh auth status` before creating PR
- **Organization SAML**: If you see "Resource protected by organization SAML enforcement":
  - The authorization URL will be provided in the error message
  - User must visit the URL in browser to authorize, or run `gh auth refresh -h github.com -s repo`
  - Wait for user confirmation before retrying PR creation
- **Token Scopes**: Ensure token has `repo` scope for creating PRs
- **Fallback**: If `gh` CLI fails, inform user they can create PR manually on GitHub web interface

## PR Description Guidelines

- **Describe differences from `<base-branch>`, NOT incremental development changes**
- **Only describe commits unique to this branch** — if the branch was created from a parent feature branch, commits inherited from the parent that were already merged via separate PRs (identifiable by `(#NNN)` PR suffixes in commit messages) must be excluded from the description. The PR should only cover the work done on this specific branch.
- **Focus on business capabilities and user-facing changes, NOT implementation details**
  - Describe WHAT changed (e.g., "Users can now retrieve account variables")
  - Avoid HOW it was implemented (e.g., avoid "database-backed", "VariableRepository", "PostgreSQL", "Clean Architecture")
- Compare the final state of the branch against the base branch, not individual commits
- Never mention files, models, or features that never existed in the base branch
- Do not reference intermediate refactoring steps, consolidations, or deletions of files created in this branch
- The PR title should reflect the main purpose/feature, not development tooling
- Include both major changes (features/fixes) and minor changes (tooling/config)
- Remove conventional commit prefixes from the PR title
- **PBI ticket number is REQUIRED** in the title
- Work item linking is **optional**
- **Do NOT list every test and function** that was modified:
  - Summarize changes by category (e.g., "Added 5 header verification tests")
  - Focus on "what was changed and why" not "list of all changes"
  - Keep PR descriptions concise and high-level
