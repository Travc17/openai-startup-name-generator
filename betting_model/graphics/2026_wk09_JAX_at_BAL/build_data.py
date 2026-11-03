"""Build box score + lines/ladder tables for JAX@BAL from sims and saved captures. Numbers only, no judgment."""
import json, statistics as st, sys
import pandas as pd
S = sys.argv[1]; BM = sys.argv[2]   # scratchpad, betting_model dir
proj = json.load(open(f"{BM}/projections/2026_wk09_JAX_at_BAL.json"))
P = proj["players"]
books = pd.read_csv(f"{BM}/markets/2026_wk09_JAX_at_BAL_books_open_alt.csv")
kal = pd.read_csv(f"{BM}/markets/2026_wk09_JAX_at_BAL_kalshi_open.csv")
imp = lambda a: 100 / (a + 100) if a > 0 else -a / (-a + 100)
key = lambda s: " ".join(s.lower().replace(".", "").replace("'", "").replace(" jr", "").split())
pk = {key(n): n for n in P}
def is_blind(n, stat):
    b = P[n].get("blind"); return bool(b) and (b == "all" or stat in b)
def ge(n, stat, x):
    g = P[n]["stats"][stat]["ge"]; ks = sorted(float(k) for k in g)
    if x <= ks[0]: return 1.0 if x <= ks[0] else None
    if x > ks[-1]: return 0.0
    return g.get(f"{x:g}")
def med(n, stat): return P[n]["stats"][stat]["q"][2] if stat in P[n]["stats"] else None
def rng(n, stat): q = P[n]["stats"][stat]["q"]; return q[0], q[4]

# ---------- box score ----------
box = []
for n, v in P.items():
    s = v["stats"]
    row = {"team": v["team"], "pos": v["pos"], "player": n, "blind": "all" if v.get("blind") == "all" else (",".join(sorted(v["blind"])) if v.get("blind") else "")}
    if v["pos"] == "QB":
        row.update(pass_cmp=med(n, "pass_cmp"), pass_att=med(n, "pass_att"), pass_yds=med(n, "pass_yds"), pass_yds_10=rng(n, "pass_yds")[0],
                   pass_yds_90=rng(n, "pass_yds")[1], pass_td=med(n, "pass_td"), int=med(n, "int"), rush_yds=med(n, "rush_yds"))
    else:
        for k in ("targets", "rec", "rec_yds", "rush_att", "rush_yds", "rec_rush_yds"):
            row[k] = med(n, k) if k in s else 0
            row[k + "_mean"] = s[k]["mean"] if k in s else 0
        a, b = rng(n, "rec_rush_yds"); row["tot_10"], row["tot_90"] = a, b
    box.append(row)
box = pd.DataFrame(box)
order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}
box["o"] = box.pos.map(order); box = box.sort_values(["team", "o", "rec_rush_yds_mean"], ascending=[False, True, False]).drop(columns="o")
box.to_csv(f"{S}/canva/box.csv", index=False)

# ---------- main lines: book vs Kalshi vs model ----------
main = books[~books.venue.str.endswith(" alt")]
alt = books[books.venue.str.endswith(" alt")]
STAT_LABEL = {"pass_yds": "Pass yds", "pass_att": "Pass att", "pass_cmp": "Completions", "rush_yds": "Rush yds", "rush_att": "Carries",
              "rec_yds": "Rec yds", "rec": "Receptions", "rec_rush_yds": "Rush+rec yds"}
lines = []
for (pl, stat), g in main.groupby(["player", "stat"]):
    if stat not in STAT_LABEL: continue
    two = g.pivot_table(index=["venue", "line"], columns="side", values="price", aggfunc="first").dropna().reset_index()
    if two.empty: continue
    L = st.mode(two.line); t = two[two.line == L]
    novig = st.mean(imp(o) / (imp(o) + imp(u)) for o, u in zip(t.over, t.under))
    o_med, u_med = st.median(t.over), st.median(t.under)
    rung = L + 0.5
    k = kal[(kal.player.map(key) == key(pl)) & (kal.stat == stat)]
    kr = sorted(k.line.unique())
    kx = rung if rung in kr else (min(kr, key=lambda x: (abs(x - rung), x)) if kr else None)
    ky = k[(k.line == kx) & (k.side == "yes")].price; kn = k[(k.line == kx) & (k.side == "no")].price
    n = pk.get(key(pl))
    mp = ge(n, stat, rung) if n and stat in P[n]["stats"] else None
    lines.append({"player": pl, "team": P[n]["team"] if n else "", "stat": STAT_LABEL[stat], "stat_key": stat, "book_line": L, "n_books": len(t),
                  "book_over": int(o_med), "book_under": int(u_med), "book_over_pct": round(novig * 100),
                  "kalshi_rung": kx, "kalshi_yes": int(ky.iloc[0]) if len(ky) else None, "kalshi_no": int(kn.iloc[0]) if len(kn) else None,
                  "model_median": med(n, stat) if n and stat in P[n]["stats"] else None,
                  "model_over_pct": None if mp is None else round(mp * 100),
                  "blind": bool(n) and is_blind(n, stat), "simulated": bool(n and stat in P[n]["stats"])})
lines = pd.DataFrame(lines)
lines["lean"] = lines.model_over_pct - lines.book_over_pct
lines = lines.sort_values(["simulated", "team", "player", "stat"], ascending=[False, False, True, True])
lines.to_csv(f"{S}/canva/main_lines.csv", index=False)

# ---------- alt ladders: every posted rung inside the sim's range ----------
lad = []
for n, v in P.items():
    for stat in v["stats"]:
        if stat not in STAT_LABEL: continue
        g = v["stats"][stat]["ge"]; ks = sorted(float(x) for x in g); lo, hi = ks[0], ks[-1]
        k = kal[(kal.player.map(key) == key(n)) & (kal.stat == stat)]
        a = alt[(alt.player.map(key) == key(n)) & (alt.stat == stat) & (alt.side == "over")].copy()
        a["rung"] = a.line + 0.5
        rungs = sorted(set(k.line) | set(a.rung))
        for r in rungs:
            if r < lo or r > hi: continue
            ky = k[(k.line == r) & (k.side == "yes")].price; kn = k[(k.line == r) & (k.side == "no")].price
            ar = a[a.rung == r]
            best = ar.loc[ar.price.astype(float).idxmax()] if len(ar) else None
            mp = ge(n, stat, r)
            lad.append({"team": v["team"], "player": n, "stat": STAT_LABEL[stat], "stat_key": stat, "rung": r,
                        "model_pct": None if mp is None else round(mp * 100, 1),
                        "kalshi_yes": int(ky.iloc[0]) if len(ky) else None, "kalshi_no": int(kn.iloc[0]) if len(kn) else None,
                        "book_best": None if best is None else int(best.price), "book_best_name": None if best is None else best.venue.replace(" alt", ""),
                        "book_best_pct": None if best is None else round(imp(float(best.price)) * 100), "n_books": int(ar.venue.nunique()),
                        "blind": is_blind(n, stat)})
lad = pd.DataFrame(lad).sort_values(["team", "player", "stat", "rung"], ascending=[False, True, True, True])
lad.to_csv(f"{S}/canva/ladders.csv", index=False)
print(f"box rows {len(box)}, main lines {len(lines)} ({lines.simulated.sum()} simulated), ladder rungs {len(lad)} "
      f"across {lad.groupby(['player','stat']).ngroups} player-stats")
print(lad.groupby(["player", "stat"]).size().to_string())
