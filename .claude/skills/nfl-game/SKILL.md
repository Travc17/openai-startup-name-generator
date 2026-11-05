---
name: nfl-game
description: Run Travis's NFL game-day chain for one game with the betting_model. Use when Travis says "/nfl-game AWAY HOME [mode]", "run the full sim", "game-day prompt", "best bets for the bankroll", "floor check", "final pass", or "grade the game". Modes are sim, bets, floor, final, grade and full.
---

# NFL game-day chain (betting_model/)

Arguments: `AWAY HOME [mode]`, e.g. `JAX BAL final`. No mode means `sim`. If the teams are missing, ask for them
in one line. The prompt files named below are the source of truth: read the one for the mode and follow it step by
step. This skill only says which file to run, in what order, and what every mode has in common.

## Every mode, first
1. CLAUDE.md "Session start": fetch, pull the working branch named in `betting_model/HANDOFF.md`, install, fetch the
   missing data. `python regression_check.py` must print stat rows AND "No drift."
2. Read `betting_model/HANDOFF.md` for this game's state: placed bets, open items, the last pass's numbers.
3. Check the clock in ET against kickoff. Inactives post about 90 minutes before kickoff; a pass before then is
   the afternoon pass, never final.

## Modes
| Mode | Run | Output |
|---|---|---|
| `sim` | `SIM_PROMPT.md` (afternoon pass) | median box score, 80% ranges, status scenarios, SizzleSims republished |
| `bets` | `GAMEDAY_PROMPT.md` steps 3 to 6 on the latest projections (step 4b runs `FLOOR_PROMPT.md`) | verdict table: 1 or 2 singles + 1 or 2 parlays, max 3, or "pass" |
| `floor` | `FLOOR_PROMPT.md` via `floor_legs.py` (`--base` = planned or placed parlay, `--singles` = singles) | floor/ceiling table + parlay options |
| `final` | `SIM_PROMPT.md` final pass (real inactives), then `bets` (SizzleSims page; no clip unless asked) | the prediction of record + final bets |
| `grade` | GAMEDAY_PROMPT.md step 7 "After the game" + SIM_PROMPT.md section 8 + FLOOR_PROMPT.md step 8 | settled bets, scorecard, review in `reviews/` |
| `full` | `sim`, then `bets` | both |

## Rules that bind every mode (CLAUDE.md wins on any conflict)
* Independence: no prop prices while setting sim inputs; only the consensus spread and total.
* Every news item and every adjustment carries a source URL; a fact not found is "not found", never a guess.
* Only tested inputs move the numbers (SIM_PROMPT.md section 1). Defensive and OL injuries, rain, short week,
  coaching and kicker changes are noted with URLs and never hand-adjusted.
* PFF: route-based role is ON (refreshed by `nfl.py update`). PFF data stays in `betting_model/data/` and is never
  committed or shared outside the model's outputs. The key lives in the environment, never in chat or the repo.
* Bets: edge 2% or more after fee, stakes via `pricing.plan_game`, 10% per-game cap, no TD/INT, no blind spots, no
  QB rushing. Model-only bets are labeled. Never place a bet or move money: Travis places every bet himself.
* Never hand-edit `picks_log.csv`. Never commit an MP4. No NFL logos or licensed music in SizzleSims.

## Every mode, last
1. Save every capture (books, Kalshi, priced, floor) in `betting_model/markets/`, projections in `projections/`,
   news in `news/`, SizzleSims games in `simcast/games/`.
2. Update HANDOFF.md (what ran, the numbers, what is pending), commit, push to the working branch.
3. Reply for a phone: verdict or predicted score first; tables over paragraphs; [Certain] / [Likely] / [Guessing]
   tags; source links; never write " - ".
