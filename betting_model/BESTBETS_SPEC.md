# Best Bets bot: spec (APPROVED with changes by Travis, 2026-11-12 ~5:30 PM ET; built: `bestbets.py`, `BESTBETS_PROMPT.md`)

What Travis asked (2026-11-12, 5:21 PM ET): an agent that takes our sim passes and picks its favorite bets.
- **Bet types:** alt-line parlays, single player props, game totals and spreads.
- **Pricing:** Kalshi pricing only.
- **Excluded stats:** rush attempts, pass attempts, pass completions.
- **Lines:** full lines or alt lines.
- **Probability cap:** never a line above 80%.
- **Ranking:** lines closer to 50% rank higher when confidence allows.

No prompt or code is written until Travis says yes (CLAUDE.md "bots and automations" rule).

## 1. Trigger
- **On demand:** "best bets AWAY HOME" or `/nfl-game AWAY HOME bestbets`.
- **Automatic:** at the end of every FINAL pass (90 minutes before kickoff, after inactives). It rides the pass schedules that already exist; no new cron.
- **Earlier passes:** on demand only. Those are preliminary, because inactives can still change everything.

## 2. Inputs
| Input | Where | Cost |
|---|---|---|
| Latest projections (the sims) | `projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json` | 0 |
| Kalshi player-prop ladders | `kalshi_quotes.py` -> `markets/<game>_kalshi_<when>.csv` | 7 credits |
| Kalshi game lines (moneyline, spread, total) | odds feed, `bookmakers=kalshi` (verified 2026-11-12: posted) | 3 credits |
| Big-book main lines (consensus spread, total, prop main lines) | `nfl.py odds` -> `markets/<game>_books_<when>.csv` | 10 credits |
| News + blind spots | `news/<game>.json`, projections `meta.adjustments.blind` | 0 |
| Current bankroll | `python nfl.py log summary` (bets.csv) | 0 |

## 3. Source of truth
- **Player props:** the model's sims, replayed exactly (seed 7, `simcast/rerun.py` check must pass). The same draws give single probabilities and parlay joint hit rates, so correlation is included.
- **Spreads, totals, moneyline:** NOT the model. Its own spreads and totals failed walk-forward tests against closing lines. These are priced from the market-anchored score sim around the big-book consensus line (`nfl.py gameline` method), so a game-line bet only exists when Kalshi's price is off the books.
- **Prices:** Kalshi asks plus the fee: 1.5c per contract on a single, 2.4c on a combo, as observed on real fills.

## 4. Script vs judgment
**Script (`bestbets.py`) does all the math, deterministically:**
- eligibility filters
- the 80% cap
- fees, probabilities and edges
- parlay joint hit rates
- the ranking score
- stakes, via `pricing.plan_game`: 5% of the current bankroll, $50 minimum, 10% per game, max 3 bets
- a self-check that every output obeys every rule; it stops on any violation

**Prompt (`BESTBETS_PROMPT.md`) does the judgment:**
- input freshness: quotes under 30 minutes old at the final pass, inactives in
- news and blind-spot sanity
- choosing the final answer from the script's ranked list: it may DROP a pick with a stated reason, but never add one the script did not pass
- the phone reply

## 5. Rules the script enforces
**Excluded stats** (Travis): `rush_att`, `pass_att`, `pass_cmp`.

**Excluded (existing CLAUDE.md rules):**
- TD and INT props
- QB rushing
- QB passing-yards unders
- blind spots
- players with no current-season usage
- grade C rows

**80% cap:**
- No single and no parlay leg whose bet side the model gives more than 80%.
- No single and no parlay leg priced above 80c on Kalshi.

**Edge:** model probability minus (Kalshi ask + fee) must be at least 10 points. This is the tested bar: 2-10% edges were break-even on 2025-26 closing lines.

**Ranking (Travis: "closer to 50% ranked higher if confidence allows"):**
- **Formula:** score = edge points minus 0.1 x (distance of the bet's probability from 50%, in points).
- **Example:** a 60% bet with a 12-point edge scores 11.0; a 78% bet with a 13-point edge scores 10.2, so the 60% bet ranks first.
- **Confidence:** a bet only gets ranked at all if it clears the 10-point bar and passes every rule above. A much bigger edge can still outrank a bet nearer 50%.

**Parlays:**
- 2 to 4 legs, player props only. Game lines come from a separate score sim, so a joint hit rate with props would be made up.
- Each leg passes the same rules and the 80% cap.
- No leg repeats a single in the same answer.
- The same player is allowed only for rushing plus receiving.
- Price = Kalshi leg asks multiplied (no combo discount) + 2.4c.
- Shown with sim hit rate, break-even and the books' implied rate.

**Answer format:** CLAUDE.md "bet requests": 1 or 2 singles plus 1 parlay. The parlay is always shown, marked "no bet" if it fails.

## 6. Output
- `markets/<game>_bestbets_<when>.csv`: every candidate with probability, price, fee, edge, score, rule flags and verdict.
- **Reply table:**
  - the bet
  - the most it is worth paying
  - stake
  - sim hit rate vs break-even vs books
  - grade
  - one-line reason
  - the 3 best near-misses marked "no bet"
- Model-only bets are labeled. Nothing is written to `bets.csv` or `picks_log.csv`.

## 7. Idempotency
- The same projections file and the same quote files give the identical output (seed 7 replay, no other randomness).
- Output files are named by capture stamp. A rerun overwrites only its own CSV.

## 8. Failure path
| Failure | What the bot does |
|---|---|
| Replay mismatch | stop: "projections cannot be reproduced" |
| No Kalshi quotes, or quotes too old at the final pass | re-pull once, else "no prices, no bets" |
| Odds API credits under 25 | ask Travis before pulling |
| Nothing clears the bar | "pass" plus the near-miss table |
| Self-check finds a rule break | stop and report it |

## 9. Connectors (least privilege)
- **Uses:** the Odds API (proxy-injected key) for Kalshi and book prices, and WebSearch for news.
- **Never uses:** a Kalshi account, Robinhood or any brokerage tool, or messaging.
- **Approval gate:** the bot NEVER places a bet or moves money. Travis places every bet himself.

## 10. Model
- Runs inside the game-day session that runs the final pass.
- The math is in the script, so it does not depend on which model runs the prompt.

## 11. Test case (before first live use)
1. **WAS at NYG**, pass 2b projections + midday Kalshi/book captures. Checks:
   - two runs give identical CSVs
   - zero excluded stats
   - zero legs above 80% or 80c
   - three hand-checked edges match
   - stakes inside the 5% / 10% caps
2. **Backfill** every game with saved Kalshi captures (weeks 9-10) and grade the picks against box scores. This is a sanity check only; too few games to prove anything.

## 12. Rule conflicts that need Travis's decision (the bot cannot ship until answered)
1. **Rush attempts excluded.** Rush-attempt unders were the strongest bet type in both test seasons (+17.6% and +24.6% ROI). Excluding them removes the best-tested edge.
2. **Spreads and totals.** CLAUDE.md bans model spreads and totals. Proposal: allow game lines priced only from the big-book consensus (section 3).
3. **Full lines.** CLAUDE.md says alt rungs only. Proposal: allow Kalshi's rung at the books' main line, at the same 10-point bar.
4. **Overs.** Model overs lost both seasons (-6.8%, -4.4%). Proposal: keep unders plus labeled low-rung overs (floor check).
5. **80% cap measure.** Proposal: the model's probability of the bet side AND the Kalshi price, both at or under 80%.

## 13. Travis's answers (2026-11-12) and how they were built
* "Keep all bet types in": attempts/completions allowed as singles, each with a non-attempt alternate; NEVER in parlays.
  Spreads, totals, moneyline and overs are in the list. Bankroll stakes still follow the approved CLAUDE.md rules.
* "In lack of edge still provide bets": the list always has 10 picks, labeled BANKROLL / VALUE / MODEL LEAN / NO EDGE.
* "10 totals ranked by best, at least 3 parlays, rest singles or game lines": 10 picks, 3+ parlays, best score first.
* Ranking uses the BEST estimate probability (20% model + 80% market: Kalshi's own two-sided no-vig price per rung), not
  the raw model: the first build ranked on the raw model and its top picks were the McCarthy volume gap (model overs,
  which lost in both test seasons). Parlay best probability = sims' joint rate x product of (best / model) per leg.
* "Project score, winner and total better, not just consensus": the model's own spreads lost to consensus (margin error
  10.58 vs 9.67) and its totals had no edge on 543 bets (README "Game lines"). Queued: a blend test (model weight fit on
  2022-24, judged on 2025-26). Until it passes, game lines are priced on the consensus-anchored score sim, and say so.
* Test run (WAS@NYG midday captures): two runs byte-identical, self-check passed, 3 parlays, attempt alternates shown.
* Travis 2026-11-12 ~5:50 PM: "also provide 2 long parlays with up to 8 legs but more than 3 legs. So 12 bets": built (4-8 legs, beam search,
  legs not used in the 10 picks, pay-at-most shown).
