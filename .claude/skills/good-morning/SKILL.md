---
name: good-morning
description: Morning briefing — priorities, daily log, and journal reflection
---

Run the morning routine. Work through each phase in order.

## Phase 1: Gather Context

Collect information from all available sources in parallel:

1. **Calendar**: Use Google Calendar to get today's events and tomorrow's.
2. **Granola**: Get recent meeting transcripts. Extract action items and
   decisions relevant to Chloe.
3. **Slack**: Check DMs and key team channels for anything that needs
   attention or provides context on priorities.
4. **Gmail**: Scan for anything urgent or relevant.
5. **Obsidian**: Read Chloe's most recent daily and weekly logs from
   ~/git/obsidian/chloe/ to understand ongoing threads.
6. **Claude's own notes**: Read your most recent daily log and improvement
   notes from ~/git/obsidian/claude/ to re-establish your own context.
7. **Git repos**: Run `git -C <repo> log --oneline -10` for each repo in
   ~/git/ to see recent activity and PRs.

## Phase 2: Create Chloe's Daily Log

Create a new file at `~/git/obsidian/chloe/daily_logs/MM-DD-YYYY.md` using
today's date. Use this template:

```markdown
# MM-DD-YYYY

## Today's Priorities

| # | Priority | Est. Time | Actual Time | Notes |
|---|----------|-----------|-------------|-------|
| 1 | ...      | ...       |             |       |
| 2 | ...      | ...       |             |       |
| 3 | ...      | ...       |             |       |

## Schedule

(Today's calendar events with relevant Slack/Granola context for each)

## Context & Framing

(Why these priorities matter today. Connect to weekly/long-term goals.
Note any blockers, dependencies, or people to loop in.)

## Slack & Email Digest

(Notable messages, threads, or emails worth knowing about)

## End-of-Day Review

_Fill this out at the end of the day._

- What took longer than expected and why?
- What was unexpectedly easy or fast?
- What got blocked or deferred?
- What would you do differently tomorrow?
- Any new information that changes your priorities going forward?
```

**Generate priorities by back-chaining from weekly objectives, not reacting to
the inbox.** Start from the current weekly log's objectives, ask "what does
today most need to advance those goals?", then layer in urgent/time-sensitive
items. If Chloe reorders the priority numbers in the table, treat that as
feedback that you didn't back-chain correctly.

Assign time estimates based on past daily logs and your calibration notes.
Be specific and realistic.

### Weekly Log (Monday Only)

On Mondays, also create `~/git/obsidian/chloe/weekly_logs/MM-DD-YYYY.md` (date
= today, the Monday). Include a weekly objectives table populated from last
week's unfinished items plus this week's calendar commitments:

```markdown
# Week of MM-DD-YYYY

## Weekly Objectives

| # | Objective | Status | Notes |
|---|-----------|--------|-------|
| 1 | ...       |        |       |
| 2 | ...       |        |       |
| 3 | ...       |        |       |

## Carried Over from Last Week

(Items that weren't completed, with context on why and updated priority)

## Key Meetings & Commitments

(This week's calendar at a glance — meetings, deadlines, events)
```

## Phase 3: Morning Journal

Present Chloe with a short reflection prompt (should take <=10 minutes).
Tailor the questions to what's actually going on — don't be generic. Draw from
recent meetings, goals, and company context. Example angles:

- What's the highest-leverage thing you could do today for the team?
- What's one thing from yesterday you'd approach differently?
- What's something you're curious about or want to learn this week?
- How does today connect to your longer-term goals?

## Phase 4: Self-Maintenance

Do this quietly — report only if you made notable changes:

1. **Start reflection watcher**: Check if the tmux `watcher` session is running
   (`tmux has-session -t watcher 2>/dev/null`). If not, launch it:
   `tmux new-session -d -s watcher 'bash ~/git/chloe_dotfiles/reflection-watcher.sh'`
   This background agent watches Chloe's Obsidian reflections throughout the day
   and makes targeted improvements to skills and config.
2. **Update CLAUDE.md**: Scan ~/git/ for structural changes (new repos, new
   directories). Update the directory tree if anything changed.
3. **Check for new MCPs/skills**: Look in ~/.claude/ and the dotfiles repo for
   any new configurations. Update CLAUDE.md MCP descriptions if needed.
4. **Update your own notes**: Write/update ~/git/obsidian/claude/daily_logs/
   with your own entry. Review and optionally update improvement_notes/ with
   anything you've learned about being more effective.

## Phase 5: Agentic Engineering Intel

Surface one or two noteworthy updates on agentic workflows, tooling, or best
practices. This is a lightweight "what's new in how we work with agents" digest.

**Sources (check in parallel):**
1. **Slack**: Scan team channels for workflow tips, tool announcements, or
   interesting agent patterns people are sharing.
2. **Notion**: Check the "Engineering with Agents" page and its parent
   onboarding docs for any recent edits or new resources.
3. **Web (Exa)**: Search for recent posts from the people listed in the
   "Who's Worth a Follow?" section of the Engineering with Agents Notion page.
   As of writing, that includes:
   - Boris Cherny (Creator of Claude Code, @bcherny)
   - Cat Wu (PM on Claude Code, @_catwu)
   - Thariq (Eng on Claude Code, @trq212)
   - Peter Steinberger (Creator of OpenClaw, @steipete)
   - Steve Yegge (Creator of Gas Town, @Steve_Yegge)
   Refresh this list from Notion each time in case it's been updated.

**Output format in the briefing:**
- 1-2 bullet points, each with a short summary and a link.
- Be opinionated: if something is relevant to Chloe's current setup (MCPs,
  CLAUDE.md patterns, skill design, etc.), say so and recommend a concrete
  action. Don't just report news, interpret it.
- If nothing notable happened, skip this section. Don't pad it.

## Phase 6: Present the Briefing

Summarize everything for Chloe in a concise briefing:

1. **Today's schedule** at a glance
2. **Top 3-5 priorities** with time estimates and reasoning
3. **Key context** from Slack, meetings, and email
4. **Agentic engineering intel** (from Phase 5, if anything notable)
5. **The journal reflection prompt**
6. **Any changes** you made to CLAUDE.md or your own notes
