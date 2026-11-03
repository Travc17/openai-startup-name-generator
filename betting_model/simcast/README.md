# SimCast: watch the most typical simulated game

Turns a saved projections file into a broadcast-style page: score bug, field with the line of
scrimmage and first down line, live box score, and play by play. Each game is the single most
typical of the model's 25,000 simulations.

```
cd betting_model
python simcast/export.py projections/2026_wk09_JAX_at_BAL.json   # writes simcast/games/<same name>.json
python simcast/build_page.py                                      # bundles every game into simcast/simcast.html
```

Export one game per projections file, then build once; the page has a game picker.

## What is the model's and what is filled in

* `rerun.py` reruns the exact simulation behind the projections file (same seed and inputs) and
  stops if any saved median differs.
* `typical.py` picks the game. Player stats: the sim closest to the median across the stats of players
  with a real role (0.8+ avg targets for receiving, 1.5+ carries for rushing, QB always; depth players are
  shown but do not decide it), among sims whose numbers agree with each other (the model's calibration step adjusts
  each stat on its own, so about 9 in 10 sims have something like 2 catches on 1 target). Score: the
  most typical draw of the score simulation, which is anchored to the market spread and total.
* `sequence.py` lays the box score out as plays (order, drives, downs, field position, kicks, clock,
  each player's per-touch yards) with a search that only accepts legal football. A play's yards only
  move between touches by the same player, so totals never change.
* `export.py` replays every play and fails if the result differs from the box score by a single yard.

Not simulated: sacks, penalties, fumbles, returns. Receivers marked with a dagger are the model's
"everyone else" targets, assigned to the team's other recent receivers; since every player with recent snaps
is simulated, that pool is usually empty and the volume shows as "Other <TEAM> receivers".

Publish: `betting_model/simcast/simcast.html` to https://claude.ai/artifact/Bx8jZgufz7Amfk5FgysjRh (same URL).
