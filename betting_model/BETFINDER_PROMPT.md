# Stage 2: bet finder prompt (prices, any venue)

Say: "Find bets for AWAY at HOME" after stage 1 (`PROJECTION_PROMPT.md`) has saved projections.
This stage never re-simulates and never changes a projection. If news broke after the projections
were made, send it back to stage 1.

---

You are pricing one game's (or a slate's) saved projections against real prices. Two separate
questions for every price:
* **Model edge**: model probability minus what the bet costs at that venue.
* **Market edge**: the big books' no-vig probability minus what the bet costs. No model involved.

## 1. Load projections
`betting_model/projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json`. Check `made_utc` is after the
latest injury news. Read `meta.adjustments` and the blind-spot flags.

## 2. Pull lines from the popular books
DraftKings, FanDuel, BetMGM, Caesars, Fanatics (plus any book Travis names). For every player in the
projections file: main line AND both prices (over and under), plus alternate lines where posted.
* Best source: The Odds API (key `ODDS_API_KEY`, host api.the-odds-api.com allowed):
  `python nfl.py odds AWAY HOME --out markets/<season>_wk<NN>_<AWAY>_at_<HOME>_books_open.csv [--alt]`
  pulls DraftKings, FanDuel, BetMGM, Caesars, Fanatics player props (yards, attempts, completions,
  carries, catches, rush+rec yards; TD/INT skipped) plus spread/total into a second file. It prints
  credits left and how many lines have both sides priced. About 10 credits per game per pull (free
  plan: 500 a month); `--alt` roughly doubles it.
* Fallback: WebSearch. It is thin (JAX@BAL wk9 found 3 book lines, none with both prices), and a
  one-sided line cannot produce a market edge.
* Never invent a line or price. A line you could not find is "not found", not estimated.
* Big-book prop lines often post only 1-2 days before kickoff: re-check on game day.

Write them to a quotes CSV (`venue,player,stat,line,side,price,captured_at`), American odds for
books. Add execution venues the same way (Robinhood rungs as `yes`/`no` at the rung, price in cents;
fee per contract set with `--fee venue=0.02`; Robinhood defaults to 2c). Save every quotes file to
`betting_model/markets/` (open and close captures).

## 3. Price
```
python nfl.py price --proj projections/<file>.json --quotes markets/<file>.csv [--board board.csv] \
  --csv <scratchpad>/priced.csv
```
Verdicts:
* **BOTH AGREE**: model and books both say this venue's price is wrong by 2%+. Strongest bet.
* **market only**: the venue is off the books' no-vig price; the model is neutral. Line shopping.
* **model only**: no two-sided book price to compare with. Current rules allow it; treat as weaker.
* **model vs market**: the model says bet, the books say no. Until the model is shown to beat the
  books (EDGE_PROMPT.md H4), assume the model is wrong. Paper-log only.
* **blind spot**: never bet.

Proposed rule (NOT active until Travis approves): real-money bets only on BOTH AGREE, plus market only
once H3 passes. Until then the CLAUDE.md rules apply unchanged (edge >= 2% after fee, stakes, 10%
per-game cap, max 3 bets per slate, blind spots out).

## 4. Matchups to exploit
Matchups are already inside the projections (defense-by-position yards per target, game script from
the spread). The bet finder's job is to show where a matchup is NOT priced in: the largest gaps
between the projection and the books, then which venue sells that side cheapest. Also check
same-game combos where a venue prices correlated legs (QB yards + his top receiver) as if they were
independent; the projections' joint sims price the real combination (use `report`'s parlay tools).

## 5. Choose venue and size
For each bet, buy at the venue with the lowest cost for the same outcome (after fees). Apply the
CLAUDE.md stake rules and the per-game cap (`pricing.plan_game`). Note book limits and alt-line
vig: alternate lines usually carry a bigger house cut than main lines.

## 6. Record and reply
* The published report (HTML + Canva, CLAUDE.md step 5) is made now: re-run `report` with the same
  arguments plus `--board` (same seed, so the same simulated games as the projections file).
* Save the priced CSV next to the quotes in `markets/`. Bets Travis calls the model's go in `bets.csv`;
  record closing prices before kickoff.
* Reply with: bets (venue, price, stake, model %, books %, verdict), the biggest model vs market
  disagreements (labeled as tests, not bets), lines not found, and anything stale.
* After the game, grade every quote (EDGE_PROMPT.md, data capture step 4).
