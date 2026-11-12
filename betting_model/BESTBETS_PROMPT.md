# Best Bets prompt: 12 bets per game (10 ranked + 2 long parlays), Kalshi prices only (Travis, 2026-11-12)

Say "best bets AWAY HOME" or `/nfl-game AWAY HOME bestbets`. It also runs automatically at the end of every FINAL pass.

The spec is `BESTBETS_SPEC.md`. All math happens in `bestbets.py`.
- This prompt never changes a number. It may DROP a pick, with a stated reason, and the next pick in the CSV takes its place.
- It never adds a pick the script did not pass.
- It never places a bet or moves money. Travis places every bet himself.

## 1. Inputs (stop if any fails)
* **Latest projections** for the game: `projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json`.
  - Run it after the final pass (inactives in).
  - An earlier pass is "preliminary": say so in the first line.
* **Fresh Kalshi prop ladders:** `python kalshi_quotes.py AWAY HOME --out markets/<game>_kalshi_<when>.csv` (7 credits).
* **Big-book main lines:** `python nfl.py odds AWAY HOME --out markets/<game>_books_<when>.csv` (10 credits).
  - Optional: alt ladders `markets/<game>_books_alt_<when>.csv` (3 credits).
* **Credits:** under 25 left, ask Travis before pulling. Quotes older than 30 minutes at the final pass get re-pulled.

## 2. Run
```
python bestbets.py --proj projections/<game>.json --kalshi markets/<game>_kalshi_<when>.csv \
  --books markets/<game>_books_<when>.csv --books-alt markets/<game>_books_alt_<when>.csv --pull-game --when <when>
```

**`--pull-game`:** saves Kalshi's moneyline, spread and total (and alternates) to `markets/<game>_kalshi_game_<when>.csv`. It costs about 5 credits.

**The replay check:** it must pass. A mismatch stops the run with "projections cannot be reproduced". Never work around it.

**What the script enforces (Travis 2026-11-12):**
- every bet type allowed
- no single and no parlay leg above 80%: neither the model's nor the best estimate's probability of the bet side may exceed it
- nothing priced above 80c
- parlays: 2 to 4 legs, never an attempts or completions leg, at least 3 parlays among the 10 picks
- every attempts or completions single carries a non-attempt alternate (same player's yards line, same direction)
- no player+stat twice across picks; a player in at most 2 picks
- PLUS 2 long parlays, 4 to 8 legs (Travis 2026-11-12: "so 12 bets"):
  - found by beam search on best-estimate return per $1
  - use legs not already in the 10 picks, and share at most 2 legs with each other
  - same leg rules and 80% cap
- long-parlay fee: estimated from Kalshi's schedule (7% x P x (1 - P), at least 1c). The flat 2.4c seen on a ~30c combo
  overstates the fee on a 5-10c ticket. Replace the estimate when a real long-ticket fill shows the fee.
- ranking: score = best-estimate edge points - 0.1 x distance from 50%
- self-check: it stops on any rule break

## 3. Read the output (`markets/<game>_bestbets_<when>.md` and `.csv`)
**Two probabilities per bet:**
- **Best hit** (20% model + 80% market, the prediction of record): this is what the ranking uses.
- **Model hit** (the raw sims): the model is overconfident, and model overs lost money in both test seasons.

**Labels:**
| Label | Meaning |
|---|---|
| BANKROLL | passes the approved bankroll rules (model edge 10+ points after fee, unders or labeled low-rung overs, caps); staked at 5%, max 3 per game, 10% per game |
| VALUE | best-estimate edge above 0 |
| MODEL LEAN | only the raw model sees an edge |
| NO EDGE | listed only because Travis wants 10 bets |

* **Game lines:** priced on the score sim anchored to the big-book consensus. The model's own score projection lost to consensus in the walk-forward tests (README "Game lines"). Say so on every game-line pick until the blend test (section 6) passes.

## 4. Judgment checks before replying (drop and replace, never edit numbers)
* A pick on a player who is questionable, inactive or limited in the latest news.
* A pick that leans on a known model gap (example: the McCarthy volume gap, 2026-11-12). Keep it, but say so in the reason.
* Two picks that are really the same bet: for example, the QB's yards and his top receiver's yards in two separate singles. Keep the better one.
* A game-line pick whose Kalshi contract wording does not match the line shown. Confirm the contract terms or drop it.

## 5. Reply (phone)
**First line:** projected score, winner with win chance, and total. Then:
1. **The 10 picks, best first, then the 2 long parlays.** Long parlays show "pay at most": Kalshi's real combo quote prices
   the legs' correlation and usually sits ABOVE the legs multiplied. Columns:
   - bet
   - Kalshi price
   - best hit vs break-even
   - label
   - stake (BANKROLL only)
   - one-line reason

   Attempt picks show their non-attempt alternate on the next line.
2. **The bankroll plan:** BANKROLL picks with stakes, or "no bankroll bet". Remind Travis that only BANKROLL picks are model bets; the rest are his call with his own money (his $10k personal floor applies).
3. **What would change the list:** a late scratch, a line move of 1+ point.

Tags: [Certain] / [Likely] / [Guessing]. Never write " - ".

## 6. Save
**Commit and push:**
- `markets/<game>_bestbets_<when>.{csv,md}`
- `markets/<game>_kalshi_game_<when>.csv`
- the quote files

**HANDOFF.md:** the picks and labels.

**Never log to `bets.csv`** unless Travis calls a bet "yours" or "the model's".

**Open test, queued (do not claim it is done):** blend the model's own game projection (`nflmodel/scores.py`) with the consensus. Fit the weight on 2022-24 and judge margin, total and win errors on 2025-26. If a model weight above 0 wins, it becomes the score, winner and total of record and the game-line probability. If not, consensus stays.
