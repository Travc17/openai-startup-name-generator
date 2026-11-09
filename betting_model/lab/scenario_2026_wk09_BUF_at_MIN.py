"""Scenario pass (NOT the prediction of record): pass-1 inputs + zone fit + Wentz target profile, shrunk 50%."""
import sys, json, argparse, io, contextlib, warnings; sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, nfl
from nflmodel import data
from nflmodel.game import Player
SHRINK = 0.5
cols = ["game_id", "week", "season_type", "posteam", "defteam", "play_type", "sack", "air_yards", "pass_location", "yards_gained", "receiver_player_id", "passer_player_name"]
def load(y):
    d = pd.read_parquet(data.DATA_DIR / f"pbp_{y}.parquet", columns=cols); d = d[d.season_type == "REG"]
    return d[(d.play_type == "pass") & d.air_yards.notna() & (d.sack != 1)].assign(
        zone=lambda x: np.where(x.air_yards <= 0, "screen", np.where(x.pass_location == "middle", np.where(x.air_yards >= 10, "mid10", "midshort"), np.where(x.air_yards >= 20, "outdeep", "out"))))
t26 = load(2026); t26 = t26[t26.week < 9]; t25 = load(2025)
lg = t26.groupby("zone").yards_gained.mean(); lg_all = t26.yards_gained.mean()
def zratio(d):
    dz = t26[t26.defteam == d]
    return (dz.groupby("zone").yards_gained.mean() / lg), dz.yards_gained.mean() / lg_all
zr = {"BUF": zratio("BUF"), "MIN": zratio("MIN")}
m = nfl.build_model()
key = 202609
a = argparse.Namespace(team_a="MIN", team_b="BUF", home="MIN", away="BUF", out=["Kyler Murray", "Demond Claiborne", "Jauan Jennings", "Josh Palmer"],
                       mult=[], catch=[], players=None, qb=[], wind=None)
with contextlib.redirect_stdout(io.StringIO()):
    roster = nfl.roster_for(m, a, key, [])
qbs = {"MIN": nfl.lookup(m, "Carson Wentz")[0], "BUF": nfl.lookup(m, "Josh Allen")[0]}
wentz = pd.concat([t25, t26]); wentz = wentz[(wentz.posteam == "MIN") & (wentz.passer_player_name == "C.Wentz")]
notes, base_roster = [], [Player(p.pid, p.team, p.share_mult, p.carry_mult, p.catch_rate, p.yds_mult, p.ypc_mult) for p in roster]
# A. zone fit -> yds_mult
for p in roster:
    opp = "BUF" if p.team == "MIN" else "MIN"
    src = wentz if (p.team == "MIN" and (wentz.receiver_player_id == p.pid).sum() >= 20) else t26[t26.posteam == p.team]
    mine = src[src.receiver_player_id == p.pid]
    if len(mine) < 10:
        continue
    mix = mine.zone.value_counts(normalize=True)
    ratio, overall = zr[opp]
    fit = float(sum(mix.get(z, 0) * ratio.get(z, 1.0) for z in mix.index) / overall)
    p.yds_mult = float(np.clip(1 + SHRINK * (fit - 1), 0.85, 1.15))
    notes.append((nfl.name_of(p.pid), "yds/target", round(p.yds_mult, 3), f"{len(mine)} tgts, {'Wentz-era' if src is wentz else '2026'} zone mix"))
# B. Wentz target split among MIN's big three + RBs (group total unchanged)
with contextlib.redirect_stdout(io.StringIO()):
    s0 = m.simulate("MIN", "BUF", key, base_roster, n_sims=4000, seed=7, exp_margin_a=-3.0, qbs=qbs)
group = {"Justin Jefferson": "JJ", "Jordan Addison": "JA", "T.J. Hockenson": "TH"}
rb_pids = [p.pid for p in roster if p.team == "MIN" and m.pg[m.pg.pid == p.pid].pos.iloc[-1] == "RB"]
model_t = {g: float(np.mean(s0["players"][nfl.lookup(m, n)[0]]["targets"])) for n, g in group.items()}
model_t["RB"] = float(sum(np.mean(s0["players"][q]["targets"]) for q in rb_pids))
pos = m.pg.drop_duplicates("pid", keep="last").set_index("pid").pos
wz = wentz.assign(pos=wentz.receiver_player_id.map(pos))
w_t = {"JJ": int((wz.receiver_player_id == nfl.lookup(m, "Justin Jefferson")[0]).sum()), "JA": int((wz.receiver_player_id == nfl.lookup(m, "Jordan Addison")[0]).sum()),
       "TH": int((wz.receiver_player_id == nfl.lookup(m, "T.J. Hockenson")[0]).sum()), "RB": int((wz.pos == "RB").sum())}
tot_m, tot_w = sum(model_t.values()), sum(w_t.values())
mult = {g: 1 + SHRINK * ((w_t[g] / tot_w) / (model_t[g] / tot_m) - 1) for g in model_t}
norm = tot_m / sum(model_t[g] * mult[g] for g in model_t)
mult = {g: v * norm for g, v in mult.items()}
for p in roster:
    nm = nfl.name_of(p.pid)
    g = group.get(nm) or ("RB" if p.pid in rb_pids else None)
    if g:
        p.share_mult *= mult[g]
        notes.append((nm, "target share", round(mult[g], 3), f"Wentz-era {w_t[g]}/{tot_w} vs model {model_t[g]:.1f}/{tot_m:.1f}"))
def run(rost, vol=1.0):
    orig = m._team_mu
    if vol != 1.0:
        m._team_mu = lambda team, opp, k, col: orig(team, opp, k, col) * (vol if (team == "MIN" and col == "targets") else 1.0)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return m.simulate("MIN", "BUF", key, rost, n_sims=25000, seed=7, exp_margin_a=-3.0, qbs=qbs)
    finally:
        m._team_mu = orig
S = {"pass 1": run(base_roster), "scenario A": run(roster), "scenario B (+6% MIN pass volume)": run(roster, 1.06)}
legs = [("Justin Jefferson", "rec", 5), ("Justin Jefferson", "rec_yds", 50), ("Jordan Addison", "rec", 2), ("Jordan Addison", "rec_yds", 20), ("T.J. Hockenson", "rec", 2),
        ("T.J. Hockenson", "rec_yds", 25), ("Aaron Jones", "rec_yds", 10), ("Carson Wentz", "pass_yds", 200), ("Khalil Shakir", "rec", 2), ("Khalil Shakir", "rec_yds", 20),
        ("Dalton Kincaid", "rec_yds", 20), ("Keon Coleman", "rec", 2), ("DJ Moore", "rec_yds", 20), ("Ty Johnson", "rec_yds", 10), ("James Cook", "rush_yds", 60), ("Josh Allen", "pass_yds", 200)]
out = {"notes": notes, "rows": []}
for nm, st, x in legs:
    pid = nfl.lookup(m, nm)[0]
    row = [nm, st, x]
    for lab, s in S.items():
        v = np.asarray(s["players"][pid][st])
        row += [float(np.median(v)), float(np.percentile(v, 10)), float(np.percentile(v, 90)), float((v >= x).mean())]
    out["rows"].append(row)
json.dump(out, open("analysis/2026_wk09_BUF_at_MIN_scenario.json", "w"))
print("ADJUSTMENTS"); [print("  ", *n) for n in notes]
print(f"\n{'player/stat':30s} | pass 1 med (10-90) P  | scen A med (10-90) P  | scen B med (10-90) P")
for r in out["rows"]:
    print(f"{r[0][:18]:18s} {r[1]:8s} {r[2]:>3}+ | " + " | ".join(f"{r[3+4*i]:6.1f} ({r[4+4*i]:.0f}-{r[5+4*i]:.0f}) {r[6+4*i]:4.0%}" for i in range(3)))
