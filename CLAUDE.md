# NFL betting model playbook (betting_model/)

Travis runs a $2,000 model bankroll (started 2026-11-02). Track ONLY bets he calls "yours/the model's"
in `betting_model/bets.csv`; commit and push the log after every change. Current bankroll is computed
from the log (`python nfl.py log summary`).

## Rules (non negotiable)
* Bet only when edge >= 2% after Robinhood's fee (2c per contract, seen on bet #1).
* Stake: $50 when edge is 2-4%; quarter Kelly above 4%; cap 10% of current bankroll. Max 3 bets per slate.
* Stop and report if bankroll <= $1,000. After 50 bets, report closing-line value; no CLV edge = recommend stopping.
* Never bet model spreads or totals (both failed walk-forward tests vs real closing lines). Game lines are priced
  only around the big-book consensus line (`gameline` / report).
* Flag model blind spots and keep them out of bets: multi-back committees after returns from IR, direct
  "next man up" backups, a team's pass catchers when a new/third-string QB starts (model has no QB-quality
  adjustment for props), and players with no current-season usage.
* Treat any player who is not ruled out as PLAYING (missed practice or not) until the news says otherwise.
* Big-book prop lines are often not posted until 1-2 days before kickoff; re-check before game day.

## When asked for a game ("run TNF", "CHI at SEA tonight", etc.)
1. `cd betting_model && python nfl.py update`
2. News: WebSearch trusted sources (official injury reports, ESPN, team beat writers) for injuries, inactives,
   depth/role changes, QB status. Write them to a news JSON with source URLs.
3. Lines: WebSearch big-book (DraftKings/FanDuel/BetMGM/consensus) spread, total, moneyline, and player prop lines.
   Put them in the board CSV as `book` rows. Add Robinhood prices from the user's screenshots as prop/spread/total/ml/tt rows.
4. `python nfl.py report AWAY HOME --week N --out "Player" ... --fav TEAM --spread X --total Y --news news.json
   --board board.csv --blind "Player" ... --sims 25000 --html <scratchpad>/game.html`
5. Publish the HTML with the Artifact tool (same file path per game to keep the URL), then reply with: score
   prediction, edges (or "pass"), best bet with stake, top singles/parlays, and anything the model can't price.
6. After the game: settle bets in the log with the closing price, and write a review in `betting_model/reviews/`.

PFF Pro API: key is stored as an environment network secret for api.pff.com (never in chat or the repo).
`python nfl.py update` refreshes PFF weekly receiving data (routes run). PFF data is licensed: it stays in
`betting_model/data/` (gitignored) and is never committed. Route-based role (50/50 blend) is ON: tested
2024-25, targets -0.93% (t=-3.35), receptions -0.60% (t=-2.43). Coverage/man-zone matchups tested neutral (off).
Before recommending any player, check his last 4 weeks of routes, snaps, and target share.

Board CSV columns: `kind,name,stat,line,price,price2,book` (see `betting_model/nflmodel/report.py` docstring).
