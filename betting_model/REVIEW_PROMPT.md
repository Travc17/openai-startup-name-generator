# Model review and improvement prompt

Paste this into a new session (or say: "Run the model review in betting_model/REVIEW_PROMPT.md"):

---

You are the lead quantitative reviewer for an NFL player-prop simulation model in `betting_model/`
that is being prepared for PAID SUBSCRIBERS. Read `CLAUDE.md`, `betting_model/README.md`, every
module in `betting_model/nflmodel/`, `betting_model/nfl.py`, `betting_model/bets.csv`, and the
reviews in `betting_model/reviews/` before changing anything.

Your job: find what is wrong, missing, or overstated, fix what can be proven better, and tell me
plainly what is not ready to sell. Quality and honesty beat speed. A finding you cannot support
with data is a hypothesis, not a finding.

## Non-negotiable rules
* Never invent stats, lines, results, or performance. Every number you report comes from a run you
  did in this session, with the command shown.
* No look-ahead: every projection may use only data from before the game it projects.
* A change ships only if it beats the current model on HELD-OUT games: paired comparison on the same
  player-games and same random seeds, scored by CRPS (and calibration), with |t| >= 2. Report every
  test, including failures. If it does not pass, leave it off and document it in the README.
* Look players up by ID, never by name (past bugs: "Bri.Thomas", "Brian Thomas" vs "Jr.").
* When a result is surprisingly large in either direction, assume a bug first and check data
  alignment and units before believing it (past bug: multiplying by a ratio that should divide).
* PFF data is licensed: never commit it, never put raw PFF numbers in anything public.
* Keep the betting rules in `CLAUDE.md` unchanged unless I approve a change.

## Audit checklist (work through all of it)
1. Data integrity: joins between nflverse, snap counts, depth charts, and PFF; week alignment; missing
   weeks; duplicate players; traded players mid-season; IDs that fail to map.
2. Leakage: any feature, prior, or fitted constant that sees future games (fitted JSONs such as
   copula.json, absences.json, depth.json, returns.json: confirm how they were fit and re-fit them
   walk-forward if needed).
3. Calibration by segment: WR/TE/RB/QB, starters vs backups, favorites vs underdogs, early vs late
   season, home vs away, dome vs outdoor, and each stat. Find where the model is over- or
   under-confident and why.
4. Known gaps, each to be built and tested:
   * Draft-capital prior for backup/third-string QBs (current prior is an average backup).
   * TD and INT calibration (pass TDs, anytime TD, INT lines) before any TD/INT bet.
   * Next-man-up roles: when a starter is out, direct backups inherit his routes/carries.
   * Blowout game script: link the market spread to volume more strongly than +0.13 rushes/pt if
     the data supports it.
   * Weather (wind, precipitation) for passing and kicking.
   * Kicker and defense props only if they can be validated.
5. Pricing: Robinhood fee (2c/contract), push handling, combo price discount (0.928 observed on one
   ticket: verify against more tickets), no-vig math vs big books.
6. Risk: Kelly sizing, the 10% cap, correlated exposure across bets on the same player or game.
7. Proof of edge: what the closing-line-value log in `bets.csv` shows, how many bets are needed
   before claiming an edge, and a plan to build a public, timestamped, every-pick record.
8. Product readiness for paid subscribers: data licensing (PFF terms, FTN CC-BY-SA attribution),
   state rules on selling picks, responsible-gambling language, disclaimers, and how picks will be
   published before kickoff.

## Deliverables
1. A ranked issue list: severity, evidence (command + numbers), and fix or reason not fixed.
2. Each fix implemented and backtested, with before/after numbers, committed with a clear message.
3. Updated README with every test (passed and failed) and an updated `CLAUDE.md` playbook if a rule
   or workflow changed.
4. Lightweight regression checks (a script that re-runs calibration on a fixed season and flags drift).
5. A "subscriber readiness" scorecard: Ready / Needs work / Not ready, for model accuracy,
   calibration, proven edge, data licensing, legal, and product presentation, with the single most
   important next step.

Be direct. If something I believe is wrong, say so with the data. If the model is not ready to sell,
say so in the first line.
