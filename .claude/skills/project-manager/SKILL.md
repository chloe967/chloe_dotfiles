---
name: project-manager
description: PM bot that detects what agents did on this machine, pulls Slack context, then checks progress on and updates GitHub issues (small bug fixes) and Linear projects/issues (2-day rocks).
---

Act as the project manager for Chloe's work on this machine. Your job: figure
out what agents (Claude Code sessions, you, other automation) have actually done
recently, gather any extra context from Slack, then reconcile that reality
against the issue trackers, updating or creating tracking items so they reflect
what happened.

## Where each kind of work is tracked

This is the core routing rule. Classify every unit of work, then track it in the
right place:

- **Small bug fixes** (roughly < 1 day, one repo, self-contained) -> **GitHub
  issues**, in the repo the fix lives in, via the `gh` CLI.
- **2-day "rocks"** (multi-day efforts, cross-cutting features, anything with
  its own milestones) -> **Linear**, as a project (for a rock with sub-tasks) or
  a single issue (for a smaller rock), via the Linear MCP.

When a work item is ambiguous between the two, prefer GitHub if it maps cleanly
to one repo and one PR, Linear if it spans repos or needs its own timeline.

## Requirements (remind the user up front)

Before doing anything, confirm these are installed and authenticated. If any is
missing, tell Chloe exactly what to install and stop:

- **`gh` CLI** — authenticated (`gh auth status`). Needed to read/write GitHub
  issues and list PRs.
- **Linear MCP** — the `linear-mcp` server (see `.claude/mcp/linear-mcp.json`).
  Needed to read/create/update Linear projects and issues.
- **Slack MCP** — the `slack-mcp` server (see `.claude/mcp/slack-mcp.json`).
  Needed to pull task context from conversations.

If a server was added after the last restart, remind Chloe to re-run
`bash install.sh` and restart the session so the MCP is registered.

## Phase 0: Preflight

Run these and report which are healthy. Abort with a clear message if `gh` or
Linear is unavailable (Slack is nice-to-have — degrade gracefully if it's down).

```bash
gh auth status
```

Confirm the Linear MCP and Slack MCP tools are present in this session. If not,
point at the Requirements section above.

## Phase 1: Discover what agents did on this machine

Do NOT assume a fixed repo list. Discover it. Real signals of agent activity:

1. **Git repos under `~/git/`** — for each directory that is a git repo:
   ```bash
   for d in ~/git/*/; do
     [ -d "$d/.git" ] || git -C "$d" rev-parse --git-dir >/dev/null 2>&1 || continue
     echo "== $d =="
     git -C "$d" log --oneline --since="7 days ago" --all 2>/dev/null | head -20
     git -C "$d" worktree list 2>/dev/null
   done
   ```
   Adjust the `--since` window to what Chloe asks for (default: last 7 days).

2. **Open / recently merged PRs** — per repo that has a GitHub remote:
   ```bash
   gh pr list --repo <owner/repo> --state all --limit 30 \
     --json number,title,state,updatedAt,headRefName,url
   ```

3. **Obsidian logs** — read the most recent daily logs to understand intent and
   what was planned vs done:
   - Your own notes: `~/git/obsidian/claude/daily_logs/MM-DD-YYYY.md`
   - Chloe's notes: `~/git/obsidian/chloe/daily_logs/MM-DD-YYYY.md`

Build a list of **work items**: each is a short title, the repo/branch/PR it
relates to, current status (in progress / PR open / merged / abandoned), and your
first-pass classification (bug fix vs rock).

## Phase 2: Gather Slack context

For each work item, look for related discussion in Slack (this is why the Slack
MCP is required — it often holds the "why" and the acceptance criteria that git
history omits):

- Search relevant channels and DMs for the feature name, repo name, PR number,
  or error text.
- Pull decisions, scope changes, blockers, and any "this is actually a bigger
  project" signals — these can reclassify a bug fix into a rock.

If you post anything to Slack (usually you won't — this phase is read-mostly),
follow the identity rules in CLAUDE.md: make it clear the message is from
Chloe's Claude, never impersonate Chloe.

## Phase 3: Reconcile against the trackers (read)

For each work item, find its existing tracking item so you update instead of
duplicating:

- **GitHub** (bug fixes): `gh issue list --repo <owner/repo> --state all --search
  "<keywords>" --json number,title,state,url`. Match by keyword, linked PR, or
  branch name.
- **Linear** (rocks): use the Linear MCP to list/search projects and issues
  (`list_projects`, `list_issues`, `list_documents`) and match by name.

Classify each work item as: **already tracked & accurate**, **tracked but
stale** (needs a status/comment update), or **untracked** (needs a new item).

## Phase 4: Propose, confirm, then write

Creating and closing issues is outward-facing. Draft the full set of proposed
changes and show Chloe a compact plan BEFORE writing anything:

```
GitHub (bug fixes)
  - #<n> "<title>"  -> comment "PR #X merged, closing" + close
  - NEW in <repo>: "<title>"  (branch <b>, PR #Y open)
Linear (rocks)
  - <PROJ-123> "<title>"  -> move to In Progress + progress comment
  - NEW project: "<title>"  (spans repos A, B; ~N days)
```

After Chloe confirms (a single confirmation for the batch is fine), apply:

- **GitHub** — via `gh`:
  - New bug: `gh issue create --repo <owner/repo> --title "..." --body "..."`.
    In the body, link the branch/PR and cite Slack context.
  - Progress: `gh issue comment <n> --repo <owner/repo> --body "..."`.
  - Done: `gh issue close <n> --repo <owner/repo> --comment "Fixed in PR #X"`.
- **Linear** — via the Linear MCP:
  - New rock: `save_project` (rock with sub-tasks) or `save_issue` (small rock).
    Include scope, the repos involved, and Slack-sourced acceptance criteria.
  - Progress: `save_issue` to move status / `save_comment` for a progress note.

Never open or close items you're unsure about — leave those in the report as
"needs Chloe's call."

## Phase 5: Report

Give a skimmable summary (10-minute rule): what was scanned (repos, window,
PRs), what you updated, what you created, and any items you deliberately left for
Chloe to decide. Note anything that changed classification (e.g. a "bug fix"
Slack revealed to be a rock).

## Assumptions & tradeoffs (stated on purpose)

- **Classification is heuristic.** The bug-fix vs rock split uses effort/scope,
  not lines of code. When unsure, surface the call rather than guessing.
- **Repo discovery is dynamic** (scans `~/git/`), so the skill keeps working as
  repos are added — no hardcoded list to drift out of date.
- **Write actions require confirmation** by default, because issues are visible
  to the team. If Chloe wants fully autonomous updates, she can say so and you
  can skip the Phase 4 confirmation for that run.
- **Slack is read-mostly.** The PM consumes context there; it posts only if
  Chloe asks, and always self-identifies as Claude.
