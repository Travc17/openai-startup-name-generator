"""Scenario (NOT the prediction of record): WAS at NYG final pass replayed with RAIN on (heavy rain + lightning at kickoff,
2026-11-12). Rain constants fit on 2019-25 (every season before this one). Same roster, QBs, spread, wind, seed 7.
Saved to analysis/ and graded with the week (record vs rain scenario vs book)."""
import sys, io, json, contextlib
sys.path.insert(0, "."); sys.path.insert(0, "simcast"); sys.path.insert(0, "lab")
import numpy as np, pandas as pd
from rerun import rerun, check
from nflmodel import game as G
from nflmodel.market import name_key
import rain_fit
PROJ = "projections/2026_wk10_WAS_at_NYG.json"
with contextlib.redirect_stdout(io.StringIO()):
    RP = rain_fit.fit(range(2019, 2026))
    base = rerun(PROJ)
assert not check(base), "official replay mismatch"
orig = G.GameModel.simulate
def sim_rain(self, *a, **k):
    self.cfg.rain_override = RP
    k["rain"] = True
    return orig(self, *a, **k)
G.GameModel.simulate = sim_rain
with contextlib.redirect_stdout(io.StringIO()):
    wet = rerun(PROJ)
G.GameModel.simulate = orig
books = pd.read_csv("markets/2026_wk10_WAS_at_NYG_books_close.csv")
books = books[~books.venue.str.contains("alt", case=False, na=False) & ~books.stat.isin(["spreads", "totals"])]
main = books.assign(k=books.player.map(name_key)).groupby(["k", "stat"]).line.median().to_dict()
pid = {v["pid"]: n for n, v in base["proj"]["players"].items()}
B, W = base["sim"]["players"], wet["sim"]["players"]
rows = []
for p, n in pid.items():
    for st in ("pass_att", "pass_cmp", "pass_yds", "targets", "rec", "rec_yds", "rush_att", "rush_yds"):
        if st not in B.get(p, {}):
            continue
        b, w = np.asarray(B[p][st], float), np.asarray(W[p][st], float)
        ml = main.get((name_key(n), st))
        rows.append(dict(player=n, stat=st, model=float(np.median(b)), rain=float(np.median(w)), book=ml,
                         best=None if ml is None else round(0.2 * float(np.median(b)) + 0.8 * ml, 1),
                         best_rain=None if ml is None else round(0.2 * float(np.median(w)) + 0.8 * ml, 1),
                         lo_rain=float(np.percentile(w, 10)), hi_rain=float(np.percentile(w, 90))))
R = pd.DataFrame(rows)
A = lambda S, n, st: np.asarray(S[base["proj"]["players"][n]["pid"]][st], float)
legs = {1: [("J.J. McCarthy", "pass_yds", ">=", 200), ("Malik Nabers", "rec_yds", ">=", 60)],
        3: [("Jayden Daniels", "pass_yds", "<", 200), ("Antonio Williams", "rec_yds", "<", 40)],
        4: [("Devin Singletary", "rec_rush_yds", ">=", 40)], 5: [("Malachi Fields", "rec_yds", ">=", 30)],
        6: [("Austin Ekeler", "rush_yds", "<", 30)], 7: [("Cam Skattebo", "rush_yds", "<", 60)],
        8: [("Devin Singletary", "rush_yds", ">=", 20), ("Malachi Fields", "rec", ">=", 2)], 9: [("Cam Skattebo", "rec", ">=", 2)],
        10: [("Malik Nabers", "rec", ">=", 6)],
        11: [("Antonio Williams", "rec", "<", 5), ("Treylon Burks", "rec_yds", "<", 30), ("Stefon Diggs", "rec", "<", 5), ("Chig Okonkwo", "rec", "<", 5)],
        12: [("Antonio Williams", "rec", "<", 5), ("Chig Okonkwo", "rec_yds", "<", 40), ("Isaiah Likely", "rec", ">=", 4), ("Stefon Diggs", "rec", "<", 5)]}
def get(S, n, st):
    if st == "rec_rush_yds":
        return A(S, n, "rec_yds") + A(S, n, "rush_yds")
    return A(S, n, st)
picks = []
for k, L in legs.items():
    hit = {lab: np.logical_and.reduce([(get(S, n, st) >= x) if op == ">=" else (get(S, n, st) < x) for n, st, op, x in L]).mean()
           for lab, S in (("model", B), ("rain", W))}
    picks.append(dict(pick=k, model=round(float(hit["model"]), 3), rain=round(float(hit["rain"]), 3)))
out = {"rain_constants_2019_25": RP, "players": R.round(1).to_dict("records"), "picks": picks,
       "score_note": "team scores come from the consensus-anchored score sim (rain not applied there; the market total already prices weather)"}
json.dump(out, open("analysis/2026_wk10_WAS_at_NYG_rain_scenario.json", "w"), indent=1, default=float)
pd.set_option("display.width", 200)
show = R[R.player.isin(["J.J. McCarthy", "Jayden Daniels", "Malik Nabers", "Isaiah Likely", "Malachi Fields", "Stefon Diggs", "Chig Okonkwo",
                        "Antonio Williams", "Treylon Burks", "Cam Skattebo", "Devin Singletary", "Rachaad White", "Austin Ekeler"]) &
         R.stat.isin(["pass_att", "pass_yds", "rec", "rec_yds", "rush_att", "rush_yds"])]
show = show[~((show.stat.isin(["rush_att", "rush_yds"])) & (show.model < 3)) & ~((show.stat.isin(["rec", "rec_yds"])) & show.player.isin(["J.J. McCarthy", "Jayden Daniels"]))]
print("rain constants (fit 2019-25):", {k: round(v, 3) for k, v in RP.items()})
print(show[["player", "stat", "model", "rain", "book", "best", "best_rain"]].to_string(index=False))
print(pd.DataFrame(picks).to_string(index=False))
