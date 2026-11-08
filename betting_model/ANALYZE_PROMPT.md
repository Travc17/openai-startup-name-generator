# Game analysis prompt: sims, alt-line hit rates, matchups. No prices (Travis, 2026-11-08)

Say: "Run the game analysis for AWAY at HOME" (or `/nfl-game AWAY HOME analyze`). Add "25k" for 25,000 sims.

What it is: the sims plus two reads, with NO prop prices, NO Kalshi, NO edges, NO bets. It answers "how often does
each skill player clear each alt rung" and "who has the softest matchup". It costs at most 2 Odds API credits
(spread and total only) or zero if the lines come from a WebSearch.

---

## 1. Setup (stop if a check fails)
* CLAUDE.md "Session start", then `cd betting_model && python nfl.py update` and `python regression_check.py`
  (stat rows AND "No drift.").
* Clock in ET vs kickoff. Before inactives (about 90 minutes before kickoff) this is a preliminary read; after
  them it is the final read. Say which in the reply.

## 2. News (every item with a URL in `news/<season>_wk<NN>_<AWAY>_at_<HOME>.json`)
* Injury report and final statuses, inactives if posted, IR activations, practice-squad elevations, starting QBs.
* Role news only if a coach or beat writer says it. Defensive, OL, weather and schedule items: note only, never
  hand-adjust (SIM_PROMPT.md section 1 is the input map).
* Blind spots per CLAUDE.md: depth backups, IR-return committees, new-QB pass catchers, no current-season usage.

## 3. Lines: spread and total only
* Big-book consensus spread and total: WebSearch, or `python nfl.py odds AWAY HOME --out markets/<file>_lines.csv`
  without `--alt`. Never pull props or Kalshi for this prompt.

## 4. Run
```
python nfl.py report AWAY HOME --week N --fav TEAM --spread X --total Y [--qb "TEAM=Name"] \
  --out "Name" ... --blind "Name" ... [--wind MPH] --news news/<file>.json \
  --sims 10000 --no-log --html <scratchpad>/game.html --proj projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json
python analyze_game.py projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json --out analysis/<season>_wk<NN>_<AWAY>_at_<HOME>.md
```
Seed 7 (default). Sanity checks from SIM_PROMPT.md section 5: team points near the implied totals, no ruled-out
player in the box score, QB volume inside his season range or a stated reason.

## 5. How to read the output
* Hit-rate ladder: for each player and stat, the HIGHEST alt rung (x+) the sims cleared at least 80 / 70 / 60 / 50%
  of the time. A rung the sims hit 80% is not a bet: without the price it says nothing about value.
* Matchups: opponent's yards allowed per target (receiving), per carry (rushing) or per attempt (QB) vs the
  league average (1.00x). Rank 32 = allows the most. Role = last 4 games' target or carry share vs his season.
  Depth players (under 5% of targets or 10% of carries) are left out; "N games" flags a short sample.
* Best matchups need a softer opponent (1.05x+), a real role (10%+ targets or 25%+ carries) and a role that is not
  shrinking. Matchup rates are context: defense-vs-position tested neutral as an extra model input.

## 6. Reply (phone)
First line: predicted score and win chance. Then:
1. Ladder table per team (QB, WRs, TEs, RBs): median, 80% and 60% rungs at minimum.
2. Best and toughest matchups, one line each with the rate and rank.
3. Inactives and status items used, each with its URL. Blind spots named.
4. What would change the read (a game-time decision, a late scratch).
No prices, no edges, no stakes. Tags [Certain] / [Likely] / [Guessing]. Never write " - ".

## 7. Save
Commit `news/`, `projections/`, `analysis/` and push. SizzleSims (`simcast/export.py`, build, publish) only if
Travis asks for the page. Update HANDOFF.md.
