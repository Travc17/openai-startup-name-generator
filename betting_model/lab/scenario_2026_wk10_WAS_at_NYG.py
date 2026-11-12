"""Scenario (NOT the prediction of record): NYG pass volume from J.J. McCarthy's starts instead of the team's season
(Winston-era games inflate it). Same roster, QBs, spread and seed as pass 1; only NYG's team target mean is scaled.
Shrunk: (2 x 27 + 2 x 32.0) / 4 = 29.5 -> x0.922; full: 27 / 32.0 -> x0.844 (team weighted average 32.0, 2026-11-12)."""
import sys, argparse, contextlib, io, json
sys.path.insert(0, ".")
import numpy as np, nfl
m = nfl.build_model(); key = 202610
a = argparse.Namespace(team_a="NYG", team_b="WAS", home="NYG", away="WAS", out=["Colson Yankoff", "Jaxson Dart", "Tyrone Tracy Jr.", "Jeremy McNichols", "Dyami Brown"],
                       mult=[], catch=[], players=None, qb=[], wind=None, date=None, leaders_only=False)
with contextlib.redirect_stdout(io.StringIO()):
    roster = nfl.roster_for(m, a, key, [])
qbs = {"NYG": nfl.lookup(m, "J.J. McCarthy")[0], "WAS": nfl.lookup(m, "Jayden Daniels")[0]}
for t, q in qbs.items():
    if q not in [p.pid for p in roster]:
        roster.append(nfl.Player(q, t))
orig = m._team_mu
def run(f):
    m._team_mu = lambda team, opp, k, col: orig(team, opp, k, col) * (f if (team == "NYG" and col == "targets") else 1.0)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return m.simulate("NYG", "WAS", key, roster, n_sims=25000, seed=7, exp_margin_a=2.5, qbs=qbs)
    finally:
        m._team_mu = orig
R = {"pass 1 (official)": run(1.0), "shrunk x0.92": run(0.922), "full McCarthy x0.84": run(0.844)}
show = [("J.J. McCarthy", "pass_att"), ("J.J. McCarthy", "pass_cmp"), ("J.J. McCarthy", "pass_yds"), ("Malik Nabers", "rec"), ("Malik Nabers", "rec_yds"),
        ("Isaiah Likely", "rec"), ("Isaiah Likely", "rec_yds"), ("Malachi Fields", "rec_yds"), ("Darnell Mooney", "rec_yds"), ("Cam Skattebo", "rush_yds"), ("Cam Skattebo", "rec_yds")]
out = {}
print(f"{'player':16s}{'stat':9s} | " + " | ".join(f"{k:>24s}" for k in R))
for nm, st in show:
    pid = nfl.lookup(m, nm)[0]
    cells = []
    for k, s in R.items():
        v = np.asarray(s["players"][pid][st], float)
        cells.append(f"{np.median(v):6.1f} ({np.percentile(v, 10):5.0f}-{np.percentile(v, 90):4.0f})")
        out.setdefault(f"{nm} {st}", {})[k] = [float(np.median(v)), float(np.percentile(v, 10)), float(np.percentile(v, 90))]
    print(f"{nm[:16]:16s}{st:9s} | " + " | ".join(f"{c:>24s}" for c in cells))
json.dump(out, open("analysis/2026_wk10_WAS_at_NYG_scenario.json", "w"), indent=1)
