# Floor and ceiling legs: season consistency + matchup + sim + price (Travis, 2026-11-05)

Say: "Run the floor check for AWAY at HOME" (also step 4b of GAMEDAY_PROMPT.md).

Idea (Travis): if a player has reached a number in every game this season (Strange 4+ catches in all 7 games, for
example) and tonight's matchup is good, that "minimum hit" rung can be added to the parlay. The mirror image for
unders: a number he has never reached, against a defense that shuts his position down.

What the data says first (2026-11-05): Strange's catches were 2, 2, 3, 7, 7, 5, 2 (floor 2, not 4). Henry has 45+ rush
yds in 8 of 8 games, yet the sim gives him 70% tonight against the NFL's best run defense. A 7-for-7 record is not
100%: a true 80% player goes 7-for-7 about 21% of the time. So the season record is evidence to blend, never a promise.

Script (does steps 1 to 6 in about 15 seconds; read its skips, never just its ADD list):

    python floor_legs.py --proj projections/<file>.json --quotes markets/<file>_kalshi_<when>.csv \
        --news news/<file>.json --base "Player:stat:under|over:x:price_cents" ... --singles "Player:stat" ... \
        --out markets/<file>_floor_legs_<when>.csv

It uses each player's LATEST news status, skips under legs when a same-position teammate is questionable or out
(his share can grow: Tuten out makes Rodriguez's 7/7 "never 60+" sample stale), applies the QB-change check to
receiving stats only, and skips any player+stat already bet as a single (`--singles`). It does NOT see players who
played in the sample but are absent tonight without a news item: check the inactives by hand.

---

For every player in tonight's projections (skip blind spots, TD/INT, QB rushing, and anyone with fewer than 4 games):

## 1. Season game log
* Every game he played this season (snaps > 0) for targets, catches, rec yds, carries, rush yds (QBs: att, cmp, yds).
* Flag games he left injured or played a reduced role (snap share far below his usual), with the news link. Show
  them; exclude one only if the reason is documented.

## 2. Rungs (on the venue's x+ grid)
* FLOOR rung (overs): the highest x he reached in EVERY game (7/7). CONSISTENCY rung: the highest x reached in all but
  one game (6/7).
* CEILING rung (unders): the lowest x he never reached, or reached in at most one game.
* Also show each rung's hit count over his last 4 games.

## 3. Matchup for the direction of the leg
From the model's defense-by-position data (2026 to date): the opponent's yards allowed per target or per carry to his
position vs league, yards per game, and rank.
* Over/floor legs need a GOOD matchup: the opponent allows at least the league rate (per target or per carry).
* Under/ceiling legs need a BAD matchup: the opponent allows less than the league rate.
* Note game script from the spread (favorite runs late, underdog throws), defensive injuries, weather.

## 4. Role and news checks (any failure = skip)
* Last 4 weeks of snaps, routes and target or carry share are not below his season level.
* No injury designation; for receiving legs, his QB is the same one who threw to him in the sample (otherwise skip).
* Under/ceiling legs: no same-position teammate questionable or out tonight (his role may grow past the sample).
* Not a blind spot under CLAUDE.md.

## 5. Probability and price
* Sim hit rate: the model's P(x+) tonight (projections `ge`), or P(under) for ceilings.
* Blended: (games hit + 10 x sim hit rate) / (games + 10). The sim counts as 10 games, so 7/7 can't read as 100%.
* Price: the venue's Yes (or No) price at that rung plus the fee (observed 2026-11-05: 1.5c singles, about 2.4c per
  contract on combos; use CLAUDE.md's figure once updated).
* Leg value = blended minus cost. A floor leg priced at 95c with a 92% blend lowers the parlay's value even though it
  "always hits".

## 6. Adding legs to a parlay
A floor or ceiling leg joins a parlay only if ALL of these hold:
1. The matchup fits its direction (step 3) and the role and news checks pass (step 4).
2. Blended probability is at least its price plus fee (it does not dilute the parlay's value).
3. The parlay's JOINT sim hit rate (replay the report's sim: same roster, QBs, spread, seed 7; correlation included)
   still clears the combo price plus fee plus 2% edge.
4. At most 2 floor or ceiling legs per parlay; no leg repeats a single; CLAUDE.md caps (3 bets, 10% per game).

## 7. Output
Table: Player | Stat | Rung (x+ or under) | Season hits (e.g. 7/7) | Last 4 | Sim % | Blended % | Matchup (opponent
per target/carry vs league, rank) | Price | Value | Verdict (add / skip and why). Then each parlay option: legs,
joint sim hit rate, correlation lift, combo price (quote or legs multiplied), books' implied rate, edge.
Say "hit rate high, price too high" when that is the reason a leg is skipped.

## 8. Record it
Save the table to `markets/<season>_wk<NN>_<AWAY>_at_<HOME>_floor_legs.csv` (every candidate, added or not) and grade it
after the game, so the idea gets tested (EDGE_PROMPT.md H8): does a 7/7 season floor hit more often than its sim rate
and its price? Never hand-edit `picks_log.csv`.
