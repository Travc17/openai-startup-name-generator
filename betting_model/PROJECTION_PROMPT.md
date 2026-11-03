# Stage 1: projection prompt (no prices)

Say: "Run projections for AWAY at HOME, week N" (or a list of games for a slate).
Stage 2 (`BETFINDER_PROMPT.md`) reads what this stage saves. This stage never decides a bet.

---

You are building projections for NFL games: every relevant player's full distribution for
targets, catches, receiving yards, carries, rushing yards, rush+rec yards, and QB attempts,
completions, yards (TD/INT shown but not calibration-checked). Projections come from 25,000
simulated games per matchup using `betting_model/` and the research below.

## Independence rule (most important)
Do NOT look at player prop lines or prices (Robinhood, DraftKings, anyone) while projecting.
Seeing a line anchors the projection toward it, and then stage 2 can never tell whether the model
adds anything beyond the books. The ONLY market inputs allowed are the game spread and total
(tested input for game script; the big-book consensus line).

## 1. Data (always)
* `cd betting_model && python nfl.py update` (nflverse play by play, player stats, snap counts,
  depth charts, PFF routes run). Then `python regression_check.py`; if it prints DRIFT, stop and fix.
* For every player you will project: last 4 weeks of routes, snaps, target share, carries share
  (CLAUDE.md rule). A role that changed in the last 2 weeks matters more than the season average.

## 2. News (search trusted sources, save every item with a URL to news.json)
Sources: official team injury reports, NFL.com, ESPN, team beat writers, coach press conferences.
* Practice reports Wed/Thu/Fri (DNP / limited / full) and final game status (Out / Doubtful /
  Questionable). A player not ruled out is PLAYING until the news says otherwise.
* IR moves, activations, returns from injury (first game back: snap limits?), suspensions,
  trades, signings, practice-squad elevations.
* Depth chart changes and coaching comments on roles: "more snaps for X", "pitch count",
  "rotation", new play caller or coordinator.
* QB: confirmed starter for both teams; if a backup starts, who, and how much NFL experience.
* Weather for outdoor stadiums: wind (only wind is tested, QB pass yards, `--wind` above 8 mph),
  rain/snow and temperature noted but NOT used.
* Inactives (released about 90 minutes before kickoff): re-run if any projected player is out.

## 3. What you are probably missing (check every game)
* Opponent defensive injuries (top CB, safety, pass rusher). The model does NOT adjust for these
  yet (untested). Note them; never hand-adjust for them without saying so.
* Short week, travel, rest. Untested: note only.
* Players with no history on the team (trades, rookies with no snaps): the model cannot project
  them well. Mark as blind spots.
* Blind spots from CLAUDE.md: multi-back committees after IR returns, direct next-man-up backups,
  pass catchers with a new/third-string QB, players with no current-season usage, coach-driven
  role cuts (example: Brian Thomas Jr., wk9 2026).

## 4. Manual adjustments (the least tested part of the whole system)
Every `--out`, `--mult`, `--catch`, `--qb`, `--blind` is human judgment. Each one must have a news
item with a URL behind it. The report saves all of them in the projections file
(`meta.adjustments`) so later reviews can grade whether adjustments helped or hurt.
Prefer the automatic, tested features (next man up, injury bump rules, route-role blend) over
hand multipliers.

## 5. Run and save
```
python nfl.py report AWAY HOME --week N --out ... --fav TEAM --spread X --total Y --news news.json \
  --blind ... --sims 25000 --no-log --html <scratchpad>/game.html \
  --proj projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json
```
(`--no-log` here because picks are logged in stage 2, once prices exist.)
* The projections file is the record: commit it before kickoff. Never edit it after kickoff.
  A re-run after news makes a new timestamp; keep the latest pre-kickoff file.
* Multi-game slate: one projections file per game.

## 6. Hand off to stage 2
Reply with: projected box score per team (medians and 10th/90th), QB lines, blind spots,
adjustments made and why (with links), news still pending (inactives, questionable players), and
the path of each projections file. No prices, no picks, no "edge" in this stage.
