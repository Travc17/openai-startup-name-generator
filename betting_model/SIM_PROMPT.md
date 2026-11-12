# Full sim prompt: 25,000 sims on the freshest inputs (Travis, 2026-11-05)

Say: "Run the full sim for AWAY at HOME" (add "final pass" after inactives post).

This is stage 1 (PROJECTION_PROMPT.md) with every input angle made mandatory. Its rules still hold: no prop
prices while setting inputs, every adjustment has a news URL, a fact you could not find is "not found", never a
guess. This prompt never picks a bet.

Read this first: more inputs do not make the sims more accurate unless the model can use them. The model takes a
short list of tested inputs (section 1). Everything else gets checked, written down with a URL, and kept OUT of the
numbers, so the post-game scorecard can show whether it would have mattered. Accuracy is proven by grading the
predictions after the game (section 8), not by how much was searched.

---

## 0. Setup and data freshness (stop if any check fails)
* CLAUDE.md "Session start": fetch, pull the working branch, install, fetch the missing data.
* `cd betting_model && python nfl.py update`, then `python regression_check.py`: it must print stat rows AND
  "No drift." (no rows above it = not a pass).
* Prove last week is in the data: both teams' most recent game appears in play by play, snap counts and PFF routes.
  If not, say which source is stale and stop.
* Clock in ET. Two passes: AFTERNOON (inputs as of now) and FINAL (after inactives, about 90 minutes before
  kickoff). Only the final pass is the prediction of record.

## 1. Input map: what the model can and cannot use
| Input | Used how | Flag |
|---|---|---|
| Consensus spread and total | game script | `--fav --spread --total` (median across the big books) |
| Starting QBs | QB layer | `--qb "TEAM=Name"` when not last game's starter |
| Players ruled out or inactive | removed; next man up automatic | `--out "Name"` |
| Wind above 8 mph (outdoor) | QB pass yards only | `--wind MPH` |
| Route-based role, injury bump rules, depth promotion | automatic (tested) | none |
| Role news (coach says more or fewer snaps) | human judgment, least tested | `--mult "Name=1.10"` + URL |
| Players the model cannot price | kept out of bets | `--blind` (CLAUDE.md blind spots) |
| Defensive injuries, OL injuries, rain/snow/cold, short week, travel, coaching or play-caller change, kicker change, referees | NOT modeled (untested) | note with URL, never hand-adjust |

## 2. Sweep: every outlet you can reach, both teams
WebSearch every source (WebFetch is blocked for many news sites: cite the search results' URLs). Sources: official
team sites and injury reports, NFL.com, ESPN (team reporters), CBS, Yahoo, NBC Sports/Rotoworld, RotoWire, The
Athletic, local papers and team blogs, beat writers' X posts that search surfaces. Append every item to
`news/<season>_wk<NN>_<AWAY>_at_<HOME>.json` with player, team + position (e.g. "JAX RB"), status, URL, time found.
Items are in time order; the LATEST item per player is his status.

a. Injury report: practice participation every day of the week (DNP / limited / full), final game status,
   game-time decisions, and coach comments on them.
b. Transactions: IR placements and activations (designated to return), practice-squad elevations (posted the
   afternoon before the game), signings, releases, trades, suspensions. A new body on the roster can take snaps
   the model does not know about.
c. QBs: confirmed starter and backup for both teams; if a backup or third-stringer starts, his NFL experience
   (his pass catchers become a blind spot under CLAUDE.md).
d. Roles: depth chart changes; "pitch count", "rotation", "more snaps for X"; a player's first game back from
   injury; last 4 weeks of snaps, routes, target share and carry share for every projected player (role changed in
   the last 2 weeks matters more than the season).
e. Offensive line: starters out or questionable (note only).
f. Defense: top CB, safeties, pass rushers, LBs out or limited, both teams (note only); plus each defense's yards
   allowed by position, last 4 to 6 games and season, from the model's data.
g. Weather at the kickoff hour (outdoor only): sustained wind AND gusts, rain or snow chance, temperature. Roof
   status for retractable stadiums.
h. Schedule spot: short week (TNF), travel and time zones, rest days, coming off a bye (note only).
i. Lines: the big-book consensus spread and total now vs the open (`markets/*_open*`). A move of 1 point or more,
   or a player's props being pulled (check only whether props are posted, never their prices), is a news alert:
   find the cause before running.
j. Special teams: kicker change, returner change (note only).
k. Things that slip: a player listed as out who is still in the model's roster, a player in the data who is no
   longer on the team, a player who played in recent games but appears in no news and no depth chart (search his
   name), name spellings that do not match the model's player (check every `--out`, `--blind` and news name maps
   to a real model player).

## 3. Scenarios for unresolved statuses
CLAUDE.md: anyone not ruled out is PLAYING in the base run. For each questionable or game-time player who matters
(a starter, or 10% or more of his team's targets or carries), also run an "out" scenario to the scratchpad
(`--no-log`, no `--proj`). List every player whose median moves 10% or more: those are STATUS-SENSITIVE until
inactives post. At the final pass, rerun the base with the real inactives.

## 4. Run
```
python nfl.py report AWAY HOME --week N --fav TEAM --spread X --total Y --qb "TEAM=Name" \
  --out "Name" ... --blind "Name" ... [--wind MPH] [--mult "Name=1.10"] --news news/<file>.json \
  --sims 25000 --no-log --html <scratchpad>/game.html --proj projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json
```
Seed 7 (the default) so every later replay (parlays, SizzleSims, floor legs) matches exactly.

## 5. Sanity checks (fix or explain every failure before publishing)
* Each team's median points vs its implied total from the spread and total (within about 3 points).
* QB median attempts and yards inside his season range, or a stated reason (new QB, game script).
* No ruled-out player in the box score; every confirmed starter present; carries and targets go to real players.
* ZERO "ROSTER CHECK" lines in the report output (2026-11-09, Hollins): every RB/WR/TE the news or the team's
  inactives report lists as active, activated off IR, designated to return or elevated is in the sims. Fix with
  `--players "Name" --blind "Name"` (first game back = blind spot). Never write "not modeled" for an active player.
* Final pass: put EVERY RB/WR/TE on both official inactive lists in the news file and `--out` each one, depth
  players included (week 9: five depth players were simulated but inactive). Zero "INACTIVE CHECK" lines.
* Final pass: `python nfl.py update` AFTER inactives post, so the depth chart is game day's (it adds starters the
  usage history misses, ranked among players not ruled out).
* Each key player's 80% range covers most of his last 4 games, or a stated reason (role change, injury).
* `python simcast/export.py projections/<file>.json` passes its replay check (exact rerun of the 25,000 sims) and
  the median box score adds up (receivers sum exactly to the QB line).
* Versus the previous run of this game: every player whose median moved, by how much, and the input that moved it.

## 6. Save and publish
* Commit and push the projections file, the news file and `simcast/games/*.json` before kickoff. Never edit a
  projections file after kickoff.
* SizzleSims (CLAUDE.md 5c): `python simcast/export.py projections/<file>.json --books markets/<file>_books_<when>.csv`
  (adds the best estimate), build, publish to the same artifact URL (no video clip unless Travis asks).

## 7. Reply (Travis reads it on his phone)
First line: predicted score and win chance. Then:
1. The box score of record (median game anchored to the BEST ESTIMATE, Travis 2026-11-12), both teams, every player
   with snaps in the sims: QB line; each receiver's targets, catches, yards; each rusher's carries and yards. Show the
   model's own median beside any QB or rusher line where they differ.
2. Key players' 80% ranges and A/B/C grades (the Predictions panel).
3. Inputs used, each with its URL. Things noted but NOT modeled, each with its URL.
4. Status-sensitive players and what changes if they sit.
5. What changed since the last run, and why.
6. Still pending (inactives, game-time decisions), and when the final pass runs.
Confidence tags [Certain] / [Likely] / [Guessing]. Never write " - ".

## 8. After the game: the accuracy test
SizzleSims scorecard: share of players inside their 80% range by grade (A should land near 80%), plus each median's
miss. Grade every "noted but not modeled" item: did the players it touched miss in the direction it predicted?
Three or more games pointing the same way is the evidence needed to propose testing that input in the model. One
game is noise. Write it into the game's review in `reviews/`.
