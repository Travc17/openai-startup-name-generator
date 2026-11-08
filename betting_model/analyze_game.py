"""Game analysis without prices (ANALYZE_PROMPT.md): hit-rate alt ladders for every skill player + matchups.

    python analyze_game.py projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json [--out analysis/<file>.md]

Reads the projections file written by `nfl.py report --proj` (the sims) and prints:
1. The score, win chance and the median box score inputs.
2. For each player and stat: the highest alt rung (x+) the sims hit at least 80%, 70%, 60% and 50% of the time.
3. Matchups: the opponent's yards allowed per target (receiving), per carry (rushing) or per attempt (QB) vs the
   league (1.00 = average, higher = softer), its rank (32 = allows the most), and the player's role trend (last 4
   games' share vs his season). No prices, no edges, no bets.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nfl  # noqa: E402
from floor_legs import defense, game_logs  # noqa: E402

RUNGS = {"rec": range(1, 13), "targets": range(1, 16), "rec_yds": range(10, 201, 5), "rush_att": range(2, 31),
         "rush_yds": range(10, 201, 5), "rec_rush_yds": range(20, 251, 5), "pass_yds": range(100, 401, 10),
         "pass_cmp": range(8, 36), "pass_att": range(15, 51)}
LABEL = {"rec": "catches", "targets": "targets", "rec_yds": "rec yds", "rush_att": "carries", "rush_yds": "rush yds",
         "rec_rush_yds": "rush+rec yds", "pass_yds": "pass yds", "pass_cmp": "completions", "pass_att": "attempts"}
TIERS = (0.80, 0.70, 0.60, 0.50)
SHOW = {"QB": ("pass_yds", "pass_cmp", "pass_att"), "RB": ("rush_att", "rush_yds", "rec", "rec_yds"),
        "WR": ("rec", "rec_yds"), "TE": ("rec", "rec_yds")}


def p_ge(st: dict, x: float) -> float:
    ge = st["ge"]
    key = f"{x:g}"
    if key in ge:
        return float(ge[key])
    ks = sorted(float(k) for k in ge)
    return 1.0 if x <= ks[0] else 0.0


def ladder(st: dict, stat: str) -> list:
    out = []
    for t in TIERS:
        ok = [x for x in RUNGS[stat] if p_ge(st, x) >= t]
        out.append(max(ok) if ok else None)
    return out


def main(a):
    P = json.load(open(a.proj))
    key, season = int(P["key"]), int(P["key"]) // 100
    away, home = P["game"].split("@")
    opp = {away: home, home: away}
    m = nfl.build_model()
    D = defense(m, season, key)
    lines = [f"# {away} at {home}: {P['sims']:,} sims (no prices)", "",
             f"Line used for game script: {P['meta']['fav']} -{P['meta']['spread']:g}, total {P['meta']['total']:g}.", ""]
    # 1. hit-rate ladders
    lines += ["## Alt-line hit rates (highest rung hit at least 80 / 70 / 60 / 50% of sims)", "",
              "| Team | Player | Stat | Median | 80% | 70% | 60% | 50% | Flag |", "|---|---|---|---|---|---|---|---|---|"]
    order = sorted(P["players"].items(), key=lambda kv: (kv[1]["team"] != away, ["QB", "WR", "TE", "RB"].index(kv[1]["pos"]) if kv[1]["pos"] in ("QB", "WR", "TE", "RB") else 9, -kv[1]["stats"].get("targets", kv[1]["stats"].get("rush_att", {"mean": 0}))["mean"]))
    rows = []
    for name, pl in order:
        pos, team, blind = pl["pos"], pl["team"], pl.get("blind")
        for stat in SHOW.get(pos, ()):
            st = pl["stats"].get(stat)
            if not st or st["q"][2] <= 0 and stat not in ("rec",):
                continue
            lad = ladder(st, stat)
            if all(v is None for v in lad):
                continue
            flag = "blind spot (low trust)" if blind == "all" or (blind and stat in blind) else ""
            f = lambda v: "-" if v is None else f"{v:g}+"
            lines.append(f"| {team} | {name} | {LABEL[stat]} | {st['q'][2]:g} | {' | '.join(f(v) for v in lad)} | {flag} |")
            rows.append(dict(team=team, player=name, pos=pos, stat=stat, median=st["q"][2], l80=lad[0], l70=lad[1], l60=lad[2], l50=lad[3], blind=bool(flag)))
    # 2. matchups
    lines += ["", "## Matchups (opponent allowed vs league; 1.00 = average, higher = softer; rank 32 = allows the most)", "",
              "| Team | Player | Matchup | Opp. vs league | Opp. rank (32 = softest) | Role last 4 vs season | Last 4 |", "|---|---|---|---|---|---|---|"]
    mrows = []
    for name, pl in order:
        pos, team = pl["pos"], pl["team"]
        g = game_logs(m, pl["pid"], pos, season, key)
        if len(g) < 2:
            continue
        few = len(g) < 4
        kinds = [("pass", "pass_yds")] if pos == "QB" else ([("rush", "rush_yds"), ("rec", "rec_yds")] if pos == "RB" else [("rec", "rec_yds")])
        for kind, stat in kinds:
            r, rk = D[(pos if pos in ("WR", "TE", "RB") else "QB", kind)]
            ratio, rank = float(r.get(opp[team], np.nan)), int(rk.get(opp[team], 0))
            if pos == "QB":
                role, big = "starter", True
            else:
                col = "c_share" if kind == "rush" else "t_share"
                s_, l4 = g[col].mean(), g[col].tail(4).mean()
                role = f"{l4:.0%} vs {s_:.0%} ({'up' if l4 > s_ * 1.1 else 'down' if l4 < s_ * 0.9 else 'steady'})"
                big = l4 >= (0.25 if kind == "rush" else 0.10)  # a real role: 25%+ of carries or 10%+ of targets
                if l4 < (0.10 if kind == "rush" else 0.05):  # depth player: too small a role to read a matchup
                    continue
            if few:
                role += f", {len(g)} games"
            last4 = " ".join(str(int(v)) for v in g[stat].tail(4))
            mrows.append((ratio, team, name, kind, rank, role, last4, pl.get("blind"), big))
    for ratio, team, name, kind, rank, role, last4, blind, big in sorted(mrows, key=lambda r: -r[0]):
        lab = {"pass": "passing", "rush": "rushing", "rec": "receiving"}[kind]
        lines.append(f"| {team} | {name}{' (blind spot)' if blind == 'all' else ''} | {lab} | {ratio:.2f}x | {rank} | {role} | {last4} |")
    best = [r for r in sorted(mrows, key=lambda r: -r[0]) if r[0] >= 1.05 and r[7] != "all" and r[8] and "down" not in r[5]][:6]
    tough = [r for r in sorted(mrows, key=lambda r: r[0]) if r[0] <= 0.90 and r[7] != "all" and r[8]][:4]
    lines += ["", "**Best matchups** (opponent 5%+ softer than league, real role, role not shrinking): " +
              ("; ".join(f"{r[2]} {('passing', 'rushing', 'receiving')[('pass', 'rush', 'rec').index(r[3])]} ({r[0]:.2f}x, rank {r[4]})" for r in best) or "none"),
              "", "**Toughest matchups** (10%+ tougher than league): " +
              ("; ".join(f"{r[2]} {('passing', 'rushing', 'receiving')[('pass', 'rush', 'rec').index(r[3])]} ({r[0]:.2f}x, rank {r[4]})" for r in tough) or "none"),
              "", "Matchup rates are context, not a model input beyond what the sims already use (defense-vs-position tested",
              "neutral as an extra lever). Blind spots: the model's numbers are least reliable there."]
    txt = "\n".join(lines) + "\n"
    print(txt)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(txt)
        print(f"saved -> {a.out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--out")
    main(ap.parse_args())
