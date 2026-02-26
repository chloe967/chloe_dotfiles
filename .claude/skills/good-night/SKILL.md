---
name: good-night
description: End-of-day reflection — extract lessons, update logs, plan improvements
---

Run the end-of-day routine. Work through each phase in order.

**Keep it tight.** There's a real tradeoff between gathering context and moving
quickly. Don't turn this into a sprawling data dump — extract signal, skip noise.

## Phase 1: Gather Evidence

Collect the day's data from all available sources in parallel:

1. **Granola**: Get ALL meeting transcripts from today. For each meeting,
   extract key lessons, mistakes, and things to do differently.
2. **Chloe's daily log**: Read today's log from ~/git/obsidian/chloe/daily_logs/.
   Pay special attention to the priorities table (est vs actual time) and the
   **Running Reflections and Thoughts** section — this is a rich, unfiltered
   source of ideas and evidence about what's working.
3. **Obsidian git diff**: Run `git -C ~/git/obsidian diff --stat` and read
   changed files — look for evidence of what process-level changes Chloe is
   experimenting with.
4. **Chloe's weekly log**: Read the current week's log from
   ~/git/obsidian/chloe/weekly_logs/ to anchor tomorrow's priorities against
   weekly objectives (back-chain, don't just react).
5. **Claude's own notes**: Read your most recent daily log and improvement
   notes from ~/git/obsidian/claude/.
6. **Git activity**: Run `git log --oneline --since="today"` across repos in
   ~/git/ to see what was actually accomplished today.

## Phase 2: Synthesize

Abstract the evidence into clear categories:

- **Key lessons and insights** from meetings and work
- **Mistakes to correct** — specific and constructive, not vague
- **Things to do differently tomorrow** — concrete behavioral shifts, not
  aspirations (e.g., "block 90 min for deep work before standup" not "focus more")
- **Calibration update** — for every priority that has both est and actual
  time, compute the ratio (actual/estimated). Track Chloe's running "factor of
  delay" over time in ~/git/obsidian/claude/improvement_notes/calibration.md.
  Use this to give better estimates in future morning briefs.

## Phase 3: Draft End-of-Day Review

Fill in the End-of-Day Review section of Chloe's daily log as a draft for her
to edit. Use the template already in the daily log:

- What took longer than expected and why?
- What was unexpectedly easy or fast?
- What got blocked or deferred?
- What would you do differently tomorrow?
- Any new information that changes your priorities going forward?

Base answers on actual evidence from Phase 1, not generic observations.

## Phase 4: Take Actions

Follow a clear hierarchy of selectivity:

1. **Freely**: Write notes to yourself about how the day went, any learnings.
   Update ~/git/obsidian/claude/daily_logs/ and improvement_notes/ as needed.
2. **High bar + explanation**: Create new tools, skills, or MCPs — only when
   there's strong evidence of repeated need across multiple days. Always explain
   why you're creating it.
3. **Most selectively**: Update parts of CLAUDE.md that have genuinely gone out
   of date. Only do this when there's clear evidence of stale information.

## Phase 5: Weekly Reflection (Friday Only)

On Fridays, additionally:

1. Read all of this week's daily logs (both Chloe's and Claude's)
2. Create a concise-as-possible weekly self-log at
   `~/git/obsidian/claude/weekly_logs/MM-DD-YYYY.md` (date = Monday of that week)
3. Focus on: patterns across the week, calibration insights, what to carry
   forward vs drop

## Phase 6: Shut Down Background Processes

Kill the reflection watcher if it's running:
`tmux kill-session -t watcher 2>/dev/null`
It will be relaunched by good-morning tomorrow.

## Phase 7: Commit and Push Dotfiles

Commit and push any changes in the dotfiles repo (`~/git/chloe_dotfiles`):

1. Run `git -C ~/git/chloe_dotfiles status` to check for changes.
2. If there are changes, stage all files, commit with a brief message describing
   what changed (e.g., "Update good-night skill", "Add new MCP config"), and push.
3. If there are no changes, skip this phase.

## Phase 8: Present Summary

Present a concise end-of-day summary to Chloe:

1. **Meeting highlights** — key takeaways from today's meetings
2. **Accomplishments** — what got done (with git evidence)
3. **Learnings** — most important lessons and insights
4. **Calibration check** — today's factor of delay (est vs actual), trend
5. **Tomorrow preview** — back-chain from weekly objectives, not just today's
   leftovers. What moves the weekly goals forward most?
6. **Claude's take** — your honest, opinionated read on what's working, what
   isn't, and what you'd change. Don't be neutral — be a thought partner.
7. **Draft review** — note that the end-of-day review is drafted in her daily log
8. **Notes updated** — mention any changes to your own notes or tools
