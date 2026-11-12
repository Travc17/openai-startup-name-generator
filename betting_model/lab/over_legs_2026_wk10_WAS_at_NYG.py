"""WAS at NYG: 90% alt-rung OVER legs (rec, rec_yds, rush_yds), strong-to-neutral matchups, Kalshi YES prices,
then tickets priced 10-25c. Joint hit rates from the replayed pass-1 sims (official) and the McCarthy volume scenarios.
Stage 1 caches sims + leg table; stage 2 searches tickets."""
import sys, io, contextlib, itertools, pickle, os
sys.path.insert(0, "simcast"); sys.path.insert(0, ".")
import numpy as np, pandas as pd
SP = "/tmp/claude-0/-home-user-openai-startup-name-generator/1abb259b-39fb-5226-92ba-1d60a674cc9b/scratchpad"
CACHE = f"{SP}/wasnyg_sims.pkl"
PROJ = "projections/2026_wk10_WAS_at_NYG.json"
FEE = 0.024
STATS = ("rec", "rec_yds", "rush_yds")

if not os.path.exists(CACHE):
    from rerun import rerun, check
    from nflmodel import game as G
    def replay(f):
        orig = G.GameModel._team_mu
        if f != 1.0:
            G.GameModel._team_mu = lambda self, team, opp, k, col: orig(self, team, opp, k, col) * (f if (team == "NYG" and col == "targets") else 1.0)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                r = rerun(PROJ)
        finally:
            G.GameModel._team_mu = orig
        return r
    off = replay(1.0)
    bad = check(off)
    assert not bad, bad[:3]
    keep = lambda S: {pid: {s: np.asarray(v[s]) for s in STATS if s in v} for pid, v in S.items()}
    sims = {"official": keep(off["sim"]["players"]), "x0.922": keep(replay(0.922)["sim"]["players"]),
            "x0.844": keep(replay(0.844)["sim"]["players"])}
    # matchup + season record + role, from the floor tool's helpers
    import floor_legs as FL
    m, key = off["model"], off["key"]
    D = FL.defense(m, key // 100, key)
    info = {}
    for name, pl in off["proj"]["players"].items():
        if pl["pos"] == "QB":
            continue
        g = FL.game_logs(m, pl["pid"], pl["pos"], key // 100, key)
        role = {}
        for kd, col in (("rec", "t_share"), ("rush", "c_share")):
            if len(g):
                s, l4 = g[col].mean(), g[col].tail(4).mean()
                role[kd] = (l4, s)
        info[name] = dict(g={s: g[s].astype(float).round().tolist() for s in STATS if s in g}, role=role)
    pickle.dump(dict(sims=sims, proj=off["proj"], D={k: (v[0].to_dict(), v[1].to_dict()) for k, v in D.items()}, info=info),
                open(CACHE, "wb"))
C = pickle.load(open(CACHE, "rb"))
sims, proj, D, info = C["sims"], C["proj"], C["D"], C["info"]
from nflmodel.market import name_key
blind = set(proj["meta"]["adjustments"].get("blind") or [])
P = {n: v for n, v in proj["players"].items() if v["pos"] != "QB" and n not in blind}
byk = {name_key(n): n for n in P}
opp = {"WAS": "NYG", "NYG": "WAS"}

q = pd.read_csv("markets/2026_wk10_WAS_at_NYG_kalshi_open.csv")
noq = q[q.side == "no"].set_index(["player", "stat", "line"]).price
q = q[q.stat.isin(STATS) & (q.side == "yes")].copy()
q["name"] = q.player.map(lambda s: byk.get(name_key(s)))
q = q[q.name.notna()]
b = pd.read_csv("markets/2026_wk10_WAS_at_NYG_books_open.csv")
main = b[b.stat.isin(STATS)].groupby(["player", "stat"]).line.median()
imp = lambda p: 100 / (p + 100) if p > 0 else -p / (-p + 100)
alt = pd.read_csv("markets/2026_wk10_WAS_at_NYG_books_alt_open.csv").query("side == 'over'")
altp = alt.assign(p=alt.price.map(imp)).groupby(["player", "stat", "line"]).p.median()

rows = []
for r in q.itertuples():
    x, pl = int(round(r.line)), P[r.name]
    pid, pos, team = pl["pid"], pl["pos"], pl["team"]
    kd = "rush" if r.stat == "rush_yds" else "rec"
    ratio, rank = D[(pos, kd)]
    mo, rk = ratio.get(opp[team], np.nan), rank.get(opp[team], np.nan)
    vals = info[r.name]["g"].get(r.stat, [])
    l4, s = info[r.name]["role"].get(kd, (np.nan, np.nan))
    h = {k: (sims[k][pid][r.stat] >= x) for k in sims}
    rows.append(dict(name=r.name, team=team, pos=pos, stat=r.stat, x=x, kalshi=r.price, no=noq.get((r.player, r.stat, r.line)),
                     book_main=main.get((r.player, r.stat)), book_alt=altp.get((r.player, r.stat, x - 0.5)),
                     sim=h["official"].mean(), sim92=h["x0.922"].mean(), sim84=h["x0.844"].mean(),
                     season=f"{sum(v >= x for v in vals)}/{len(vals)}", last4=f"{sum(v >= x for v in vals[-4:])}/{min(4, len(vals))}",
                     matchup=round(mo, 2), mrank=int(rk) if rk == rk else None,
                     mband="strong" if mo >= 1.05 else ("neutral" if mo >= 0.95 else "tough"),
                     role=f"{l4:.2f} vs {s:.2f}", shrinking=bool(l4 < 0.9 * s) if s == s else False))
L = pd.DataFrame(rows)
L.to_csv("markets/2026_wk10_WAS_at_NYG_over_legs_open.csv", index=False)
# rung of choice: highest posted rung with official sim >= 90% (per player and stat)
c = L[(L.sim >= 0.90)].sort_values("x").groupby(["name", "stat"]).tail(1)
pd.set_option("display.width", 250)
cols = ["name", "team", "stat", "x", "kalshi", "no", "book_main", "book_alt", "sim", "sim92", "sim84", "season", "last4", "matchup", "mrank", "mband", "role", "shrinking"]
print("90% RUNG OF CHOICE, every player (official sim >= 90%, highest posted rung)")
print(c.sort_values(["mband", "team"])[cols].round(3).to_string(index=False))
c.to_csv(f"{SP}/wasnyg_90legs.csv", index=False)
