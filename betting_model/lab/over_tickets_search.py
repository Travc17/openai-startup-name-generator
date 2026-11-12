"""Ticket search over any rungs (one rung per player+stat; per player one receiving stat + rushing), Kalshi asks
multiplied, ticket LO-HI cents. Args: min_sim bands(comma) LO HI tag"""
import sys, pickle, math
sys.path.insert(0, ".")
import numpy as np, pandas as pd
SP = "/tmp/claude-0/-home-user-openai-startup-name-generator/1abb259b-39fb-5226-92ba-1d60a674cc9b/scratchpad"
C = pickle.load(open(f"{SP}/wasnyg_sims.pkl", "rb"))
sims, proj = C["sims"], C["proj"]
FEE = 0.024
min_sim, bands, LO, HI, tag = float(sys.argv[1]), sys.argv[2].split(","), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
L = pd.read_csv("markets/2026_wk10_WAS_at_NYG_over_legs_open.csv")
L = L[(L.sim >= min_sim) & L.mband.isin(bands) & (L.kalshi <= 97)].sort_values(["name", "stat", "x"]).reset_index(drop=True)
H = {k: [sims[k][proj["players"][r.name]["pid"]][r.stat] >= r.x for r in L.itertuples()] for k in sims}
lp = np.log(L.kalshi.values / 100)
groups = [g.index.tolist() for _, g in L.groupby(["name", "stat"])]
names = [L.loc[g[0], "name"] for g in groups]
stats = [L.loc[g[0], "stat"] for g in groups]
out = []
def dfs(gi, chosen, s, used):
    if gi == len(groups):
        if len(chosen) >= 2 and math.log(LO) <= s <= math.log(HI):
            j = {k: float(np.logical_and.reduce([H[k][i] for i in chosen]).mean()) for k in sims}
            rows = L.loc[chosen]
            bk = rows.book_alt.values
            out.append(dict(n=len(chosen), price=math.exp(s), hit=j["official"], hit92=j["x0.922"], hit84=j["x0.844"],
                            books=float(np.prod(bk)) if not np.isnan(bk).any() else np.nan,
                            legs=" + ".join(f"{r.name} {r.x}+ {r.stat} ({r.kalshi}c, {r.sim:.0%}, {r.mband})" for r in rows.itertuples())))
        return
    if s < math.log(LO):
        return
    dfs(gi + 1, chosen, s, used)                                   # skip this group
    nm, st = names[gi], stats[gi]
    u = used.get(nm, set())
    if st != "rush_yds" and (u - {"rush_yds"}):
        return                                                     # one receiving stat per player
    for i in groups[gi]:
        dfs(gi + 1, chosen + [i], s + lp[i], {**used, nm: u | {st}})
dfs(0, [], 0.0, {})
O = pd.DataFrame(out)
print(f"[{tag}] rungs {len(L)}, groups {len(groups)}, tickets {LO*100:.0f}-{HI*100:.0f}c: {len(O)}")
if len(O):
    for k in ("", "92", "84"):
        O["edge" + k] = O["hit" + k] - O.price - FEE
    O.sort_values("edge", ascending=False).to_csv(f"markets/2026_wk10_WAS_at_NYG_over_tickets_{tag}.csv", index=False)
    pd.set_option("display.width", 400); pd.set_option("display.max_colwidth", 400)
    for lab, k in (("BEST EDGE", "edge"), ("BEST x0.922 EDGE", "edge92"), ("HIGHEST HIT", "hit")):
        print(f"  {lab}")
        print(O.sort_values(k, ascending=False).head(5)[["n", "price", "hit", "hit92", "hit84", "books", "edge", "edge92", "legs"]].round(3).to_string(index=False))
