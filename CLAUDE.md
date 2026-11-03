# NFL betting model playbook (betting_model/)

## Session start (every session, before anything else; Travis, 2026-11-03)
1. `git fetch origin`, then get onto the working branch named at the top of `betting_model/HANDOFF.md`:
   `git pull origin <working branch>`. If this session's branch has no `betting_model/` folder, fast-forward
   it first: `git merge --ff-only origin/<working branch>`. Never start work on a branch without it.
2. `pip install -r betting_model/requirements.txt` (fresh containers are missing scipy). Then, because
   `data/` is gitignored and `update` only fetches 2022+, a fresh container also needs (in `betting_model/`):
   `python -c "from nflmodel import data, routes; data.ensure_data([2019,2020,2021]); routes.refresh_pff(2024); routes.refresh_pff(2025)"`
   Without 2019-21 play by play the QB layer returns NaN and `report` crashes; without 2024-25 PFF data
   `regression_check.py` shows targets/rec DRIFT. A "No drift." with no stat rows above it is NOT a pass.
3. Read `betting_model/HANDOFF.md`, then every file it lists. HANDOFF.md is the state; this file is the rules.
4. Do the first open item in HANDOFF.md and report its result before starting anything new.
5. Before the session ends: rewrite HANDOFF.md (state, open items in order, waiting on Travis, credits left),
   commit and push. Every quotes, board and priced file goes in `betting_model/markets/` and is committed;
   nothing stays only in the scratchpad.

Travis runs a $2,000 model bankroll (started 2026-11-02). Track ONLY bets he calls "yours/the model's"
in `betting_model/bets.csv`; commit and push the log after every change. Current bankroll is computed
from the log (`python nfl.py log summary`).

## Rules (non negotiable)
* Execution venue is Kalshi (Travis, 2026-11-03: "forget Robinhood, I will use Kalshi"). Bet only when edge >= 2%
  after the fee. Kalshi's fee is priced at 2c per contract (`--fee kalshi=0.02`, the default in market.py) until a
  real fill shows the actual fee; replace it then. Robinhood (2c on bet #1) is no longer used.
* Stake: $50 when edge is 2-4%; quarter Kelly above 4%. Max 3 bets per slate.
* Bet requests (Travis, 2026-11-03): whenever Travis asks for a bet for the bankroll, answer with EITHER one
  single prop + one parlay OR two single props + one parlay. A parlay is required every time, shown with its
  SIM HIT RATE (joint, from the same sims as the projections, correlation included) next to its price's
  break-even (with fee) and the books' implied hit rate. Parlay legs: no blind spots, no TD/INT, and no leg that
  repeats a single in the same answer. Every bet still needs edge >= 2% after fee; if the best parlay fails,
  show it anyway, marked "no bet". Stakes via `pricing.plan_game` (max 3 bets, 10% per-game cap).
  Price parlays by replaying the report's sim (same roster, QBs, spread, seed 7), NOT `nfl.py parlay`, which
  re-simulates without spread/total/QB settings.
* Cap: ALL bets on one game combined <= 10% of current bankroll (approved 2026-11-03). The report's
  "Bet plan" applies it: best expected profit first, no repeated player+stat, stakes scaled down together
  (never below $50); if the minimums alone break the cap, the weakest bet is dropped.
* Stop and report if bankroll <= $1,000. After 50 bets, report closing-line value; no CLV edge = recommend stopping.
* Never bet model spreads or totals (both failed walk-forward tests vs real closing lines). Game lines are priced
  only around the big-book consensus line (`gameline` / report).
* Flag model blind spots and keep them out of bets: multi-back committees after returns from IR, direct
  "next man up" backups, a team's pass catchers when a new/third-string QB starts (model has no QB-quality
  adjustment for props), and players with no current-season usage.
* Treat any player who is not ruled out as PLAYING (missed practice or not) until the news says otherwise.
* Big-book prop lines are often not posted until 1-2 days before kickoff; re-check before game day.

## Two stages (Travis, 2026-11-03): projections, then bets
Stage 1 `betting_model/PROJECTION_PROMPT.md`: sims + news only, no prop prices, saves
`betting_model/projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json` (report `--proj`). Stage 2
`betting_model/BETFINDER_PROMPT.md`: big-book lines + any venue's prices vs those projections
(`python nfl.py price --proj ... --quotes ... [--board ...]`). Robinhood is one venue, not the base.
The steps below still apply; the report's `--proj` file is the stage 1 record.

## When asked for a game ("run TNF", "CHI at SEA tonight", etc.)
1. `cd betting_model && python nfl.py update`
2. News: WebSearch trusted sources (official injury reports, ESPN, team beat writers) for injuries, inactives,
   depth/role changes, QB status. Write them to a news JSON with source URLs.
3. Lines: WebSearch big-book (DraftKings/FanDuel/BetMGM/consensus) spread, total, moneyline, and player prop lines.
   Put them in the board CSV as `book` rows. Add Robinhood prices from the user's screenshots as prop/spread/total/ml/tt rows.
   Save a copy of every board to `betting_model/markets/` (open and close captures; see EDGE_PROMPT.md). Price history
   is the only way to test profit, so never leave a board only in the scratchpad.
4. `python nfl.py report AWAY HOME --week N --out "Player" ... --fav TEAM --spread X --total Y --news news.json
   --board board.csv --blind "Player" ... --sims 25000 --html <scratchpad>/game.html`
   `--blind "Name"` excludes all of a player's props; `--blind "Name:rec,rec_yds,targets"` only those stats
   (e.g. an RB's receiving props with a third-string QB while his rushing stays bettable).
   Outdoor game with wind forecast above 8 mph: add `--wind MPH` (tested on QB pass yards only).
   Run `python regression_check.py` after `update` or any code change; if it prints DRIFT, fix before publishing.
5. Publish the HTML with the Artifact tool (same file path per game to keep the URL), then reply with: score
   prediction, edges (or "pass"), best bet with stake, top singles/parlays, and anything the model can't price.
5b. Canva for every report (rule set by Travis 2026-11-03): `report` writes `<html name>.canva.txt`, a brief built
   only from the report's numbers: a carousel with the summary, the FULL box score for each team, and book line vs
   prediction (big-book lines plus each Robinhood ladder's main line, the rung priced closest to 50c). Both are required
   on every report (Travis, 2026-11-03), plus a "Highest hit-rate parlays" page (alt lines, 3-6 legs, ticket 5-40c,
   ranked by sim hit rate regardless of edge; same player only rushing + receiving; blind spots excluded). Lines tables are
   sorted highest hit rate first. No overlapping or ghosted text: check every page thumbnail, not just the numbers.
   Pass that text unchanged to Canva create-design (Instagram Post (Portrait)),
   then read-design and check EVERY number against the brief. Fix mismatches with edit-design (ask Travis before
   committing edits) or regenerate; never share a Canva design with a number that differs from the report.
   Reply with both links: the Canva graphic (shareable) and the HTML report (full box score, sources).
5c. SizzleSims (formerly SimCast) for every game (Travis, 2026-11-03): after the projections file is saved, in `betting_model/`:
   `python simcast/export.py projections/<file>.json` (reruns the exact sims and stops on any mismatch), then
   `python simcast/build_page.py`, then publish `betting_model/simcast/simcast.html` with the Artifact tool to
   https://claude.ai/artifact/Bx8jZgufz7Amfk5FgysjRh (read it first; same URL every time; all games share one
   page with a picker). Commit `simcast/games/*.json`. Default is the MEDIAN game (Travis): every RB/WR/TE at his
   exact median, each QB line = the sum of his receivers (every completion to a named player, never a placeholder),
   the QB's own median shown under his box; score = median score. Opens at the 90-second clip; both box scores show.
6. Before kickoff, record closing prices for logged picks (`python nfl.py picks close --game G --label L --price P`).
   After the game: settle bets in the log with the closing price, run `python nfl.py picks grade`, and write a
   review in `betting_model/reviews/`.

Paper-trading log (`picks_log.csv`): `report` records every qualifying pick before kickoff and refuses games
already in the data. Never add or edit rows by hand; this is the public every-pick record for subscribers.
Automatic in every report (tested, see README "Model review"): next man up by position, no injury bump once a
player has missed 2+ straight games, per-stat calibration maps, walk-forward team-volume fit. Parlay tickets
are priced with NO combo discount (too few Robinhood tickets observed to fit one).

PFF Pro API: key is stored as an environment network secret for api.pff.com (never in chat or the repo).
`python nfl.py update` refreshes PFF weekly receiving data (routes run). PFF data is licensed: it stays in
`betting_model/data/` (gitignored) and is never committed. Route-based role (50/50 blend) is ON: tested
2024-25, targets -0.93% (t=-3.35), receptions -0.60% (t=-2.43). Coverage/man-zone matchups tested neutral (off).
QB layer is ON: QB lines (att/cmp/yds/TD/INT) are summed from the same simulated targets; QB quality scales
his receivers (tested 2024-25: QB completions -0.97% error, t=-2.6; receiver yards in QB-change games -1.1%).
Its prior is an AVERAGE backup, so third-string/undrafted QBs are still too generous: keep them and their pass
catchers as blind spots. TD/INT props are not calibration-checked yet: no TD/INT bets until they are.
Default starter = last game's starter; override with --qb "TEAM=Name".
Before recommending any player, check his last 4 weeks of routes, snaps, and target share.

Board CSV columns: `kind,name,stat,line,price,price2,book` (see `betting_model/nflmodel/report.py` docstring).
