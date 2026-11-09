# Weekly grade prompt: every box score, every prediction, slow learning (Travis, 2026-11-09)

Say: "Grade the week" or "Grade week N" (or `/nfl-game grade-week N`). Run it Monday night or Tuesday, and once
more after snap counts post. It grades EVERY game we projected that week, not one game. For one game with bets,
POSTGAME_PROMPT.md still settles the bankroll; this prompt is the accuracy check.

The rule: ONE WEEK CHANGES NOTHING. Bugs get fixed now. Patterns get counted. The model changes only when a
pattern repeats in 3+ games AND a MODEL_LAB_PROMPT.md test passes on held-out seasons.

---

## 1. Data (stop if a check fails)
* CLAUDE.md "Session start", then `cd betting_model && python nfl.py update` and `python regression_check.py`
  (stat rows AND "No drift.").
* Every game we projected must be in play by play. A game missing = data not posted yet; wait, never guess.

## 2. Box scores
* `python grade_week.py --week N --league --simcast` reads the SAVED pre-kickoff projections and SizzleSims
  files (never a rerun: nflverse and PFF revise earlier weeks, so a rerun after `update` cannot match exactly).
* Cross-check against the official box score (WebSearch ESPN or NFL.com "<AWAY> <HOME> box score"): every QB line
  and every player whose result sits outside his 80% range. A mismatch is a data bug: stop and find it.
* "SNAP COUNTS NOT POSTED" means players who played without a touch are missing. Regrade after snaps post
  (usually 1 to 2 days) before counting coverage as final.

## 3. In-game injuries and early exits (every game, every miss)
* The grader lists players the play-by-play shows "injured during the play" (and whether they returned), plus
  early exits (last touch before halftime for a player projected 4+ touches) with no injury note.
* For each one, AND for each miss outside the 80% range: WebSearch "<player> injury <opponent>", the team's
  postgame injury notes, and the beat writers' live updates. Record what happened with the URL. Not found is
  "not found".
* A teammate's exit explains the other side too: when a starter leaves, his backup's big game is the same event
  (GB at NE week 9: Jacobs out in the 1st quarter with a broken finger, Kaleb Johnson 14 carries).
* The model does not simulate players leaving mid-game. These misses are class "in-game exit": graded as usual,
  shown again without them so an injury does not hide a real miss, and counted in the ledger.

## 4. Pre-game misses (signal we had and did not use)
* Any player in the box score with a real role who was NOT in the sims: why? Check the news file and the
  report's ROSTER CHECK lines. Active, off IR, elevated or depth-chart starters must be in the sims (Hollins,
  week 9). A miss here is a process fix in SIM_PROMPT.md, logged in the ledger.
* Any player in the sims who did not play: was the inactive in the news before kickoff?

## 5. Read the scorecard
| Number | Calibrated | Action |
|---|---|---|
| A+B inside 80% range | about 80% | above 90% or below 70% over 5+ games: ranges too wide or narrow, MODEL_LAB test |
| Mean PIT by stat | about 0.50 | 0.40 or less / 0.60 or more over 5+ games: bias candidate for MODEL_LAB |
| League panel under p10 / p50 / p90 | 10 / 50 / 90 | compare with the regression baseline; one week is noise |
| Model vs book vs best miss | best <= book | the 20/80 best estimate stays unless 2+ seasons say otherwise |
| Model's side vs the book | over 50% on unders | this is the betting edge check; counts toward CLV, not a model change |

## 6. Classify every miss (POSTGAME_PROMPT.md table plus "in-game exit")
Variance; in-game exit; known blind spot confirmed; signal we had and did not use; pattern to watch; bug.
Write each into `reviews/lessons.csv`: same lesson again = add the game, raise `games`, keep the evidence specific.

## 7. Model changes: the only three allowed outcomes
1. Bug (wrong player, wrong join, roster rule broken, a number that cannot be right): fix now, rerun
   `regression_check.py` (must stay "No drift."), note it in the ledger.
2. Pattern at 3+ games: write the MODEL_LAB test (hypothesis, data, bar) and run it on 2024-25 + 2026 to date.
   Ship only if it passes. Fail: leave it off and record why.
3. Everything else: no change. Say so, with the count still needed.
Betting rules never change from this prompt (2+ seasons of closing lines AND Travis's approval).

## 8. Record and reply
* `python simcast/build_page.py`, publish SizzleSims to the same URL (scorecards on every played game).
* Commit `reviews/` (grades CSV, grade md, grades_log.csv, lessons.csv), `simcast/games/`, any fix; update
  HANDOFF.md; push.
* Reply for a phone: the uncomfortable result first; scores table; coverage by grade; in-game exits with URLs;
  misses by class; what changed in the code and what did NOT (with the count it needs); self-grade (process,
  predictions, bets) with one line of evidence each. [Certain] / [Likely] / [Guessing]. Never write " - ".
