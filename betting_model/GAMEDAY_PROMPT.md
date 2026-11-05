# Game-day prompt: best bets for the model bankroll (Travis, 2026-11-05)

Say: "Run the game-day prompt for AWAY at HOME". Tonight: JAX at BAL, Thursday Night Football, 8:15 PM ET.

---

You are finding tonight's bets for Travis's model bankroll on Kalshi. Work in this order and skip nothing. A fact
you could not find is "not found", never a guess. Every news item gets a source URL.

## 0. Setup (CLAUDE.md "Session start")
* Branch `claude/tender-faraday-offel8` holds all current work: `git fetch origin` then `git pull origin
  claude/tender-faraday-offel8`. Install deps and the missing data (CLAUDE.md step 2). `regression_check.py` must
  print stat rows and "No drift."
* Read HANDOFF.md, BETFINDER_PROMPT.md, EDGE_PROMPT.md. Bankroll: `python nfl.py log summary`.
* Check the clock in ET. Do two passes: an afternoon pass when asked, and a FINAL pass after inactives post
  (about 90 minutes before kickoff). No bet is final before the final pass.

## 1. News sweep: every outlet you can reach
WebSearch every source (WebFetch is blocked for many news sites: cite the search results' URLs). For BOTH teams:
* Official final injury report and game statuses (for a Thursday game it posts Wednesday), then inactives.
* Confirmed starting QBs (BAL: Fagnano's ankle, Huntley's status).
* Beat writers and outlets: Ravens (Baltimore Sun, Baltimore Banner, Russell Street Report, Baltimore Beatdown,
  ESPN's Ravens reporter); Jaguars (Jaguars.com, Florida Times-Union, ESPN's Michael DiRocco); NFL.com, ESPN, CBS,
  Yahoo, RotoWire, NBC Sports/Rotoworld; beat writers' X posts that search surfaces.
* Roles: backfield splits (Tuten, Rodriguez, Abdullah, Allen; Henry, Hill), snap or pitch counts, Thomas Jr.'s
  role, Meyers' hamstring, Andrews, anyone returning or limited.
* Defensive injuries for the matchup (JAX: Travon Walker, Antonio Johnson; BAL: Roquan Smith, Nate Wiggins,
  Jaylinn Hawkins, any new ones). The model does NOT adjust for these (untested): note them, never hand-adjust.
* Weather in Baltimore at kickoff: wind (add `--wind` above 8 mph), rain.
* Line moves since the open captures in `markets/*_open*`: spread, total, the props we care about. A big move
  usually means news: find the news.
Append every item with its URL to `news/<season>_wk<NN>_<AWAY>_at_<HOME>.json`.

## 2. Re-run stage 1 on the final inputs (SIM_PROMPT.md: the full input sweep, scenarios and sanity checks)
* `report` with `--out` for anyone ruled out or inactive, the current consensus `--fav/--spread/--total`, `--news`,
  blind spots (existing plus new ones: a committee after an injury, a direct next-man-up backup, a new or
  third-string QB's pass catchers), `--sims 25000 --no-log --proj projections/<file>.json`.
* Independence rule: do NOT look at prop prices while setting adjustments; only the spread and total. Every
  adjustment needs a news URL.
* SizzleSims (CLAUDE.md 5c): export, build, publish (the page is for Travis and friends; no clip unless he asks).

## 3. Prices (close capture, saved to `markets/`)
* Books: `python nfl.py odds AWAY HOME --alt --out markets/<file>_books_close.csv`.
* Kalshi ladders (the execution venue) to `markets/<file>_kalshi_close.csv`: cents, yes/no on each rung, asks of
  95c or more skipped as no real offer.
* `python nfl.py price --proj ... --quotes <books + kalshi> --fee kalshi=0.02 --csv markets/<file>_priced_close.csv`.
* Ladder rungs have no two-sided book price: use 1 minus the books' alt-Over implied probability as a conservative
  floor for the Under (method in HANDOFF.md).

## 4. Matchup against hit rate (for every candidate leg)
Show side by side:
* Sim hit rate (the model's probability) and the price's break-even (cost plus the 2c fee).
* The books' no-vig probability, or the floor, and Kalshi's price.
* Matchup: the opponent's yards allowed to that position (last 4 to 6 games and the season, from the model's
  defense-by-position data), game script from the spread (a big favorite runs late, the underdog passes), pace,
  weather, defensive injuries from step 1.
* Role check: last 4 weeks of snaps, routes, and target or carry share (CLAUDE.md).
* Verdict: does the matchup support the hit rate or argue against it? A high hit rate is not a bet when the price
  already reflects it. Hit rate alone is never the test (EDGE_PROMPT.md H8).

## 4b. Floor and ceiling legs
Run FLOOR_PROMPT.md with `floor_legs.py` (close Kalshi quotes, final news file, the planned parlay as `--base`, the
planned singles as `--singles`): season game logs, the rung each player reached in every game (or never reached),
matchup for that direction, sim and blended probability, price. Its qualifying legs can join a parlay under its
step 6 rules. Save the table to `markets/<file>_floor_legs_close.csv`.

## 5. Pick the bets (CLAUDE.md rules, Travis's game-day format)
* 1 or 2 single props and 1 or 2 parlays, HARD MAX 3 bets total (slate cap), at least one parlay.
* Every bet: edge of 10% or more after the fee (CLAUDE.md, 2026-11-05); alt rungs only; UNDERS only, except a
  low-rung over (rung below the book's main line, FLOOR_PROMPT checks pass, labeled untested); no QB pass-yds
  unders; no blind spots, no TD/INT; skip QB rushing props; no parlay leg repeating a single.
* Prefer BOTH AGREE (model and books). A model-only bet is labeled as such, with the rule stake shown and the
  $50 minimum recommended; Travis decides. If nothing passes, the first line says "pass".
* Parlays: price by replaying the report's sim (same roster, QBs, spread, seed 7), never `nfl.py parlay`. Show the
  sim hit rate, correlation lift, the books' implied joint rate, Kalshi's price (Travis supplies combo quotes), and
  the most to pay for a 10% edge. Rank candidates by sim hit rate, then keep only those that clear the edge.
* Show the BEST ESTIMATE (20% model median / 80% book main line) beside the model median for every player listed.
* Stakes: flat $50 per bet (10% per-game cap on the current bankroll still applies).

## 6. Reply (Travis reads it on his phone)
First line: the verdict (the bets, or "pass"). Then one table: Bet | Venue | Price limit | Stake | Sim hit % |
Break-even % | Books % | Matchup | Grade. Then: what could flip it before kickoff, blind spots left out and why,
sources as links. Confidence tags [Certain] / [Likely] / [Guessing]. Never write " - ".

## 7. After Travis fills
* Log every fill in `bets.csv` (`python nfl.py log add ...`), record closing prices (`picks close`), commit, push,
  update HANDOFF.md.
* After the game: settle, `picks grade`, grade every rung and quote (EDGE_PROMPT.md step 4), add the SizzleSims
  scorecard, write the review in `reviews/`.
