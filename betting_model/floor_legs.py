"""Floor and ceiling legs (FLOOR_PROMPT.md): season consistency + matchup + sim + price, as a table.

    python floor_legs.py --proj projections/<file>.json --quotes markets/<file>_kalshi_<when>.csv \\
        [--news news/<file>.json] [--base "Derrick Henry:rush_yds:under:80:63" ...] [--singles "Colby Parkinson:rec_yds" ...] \\
        [--out markets/<file>_floor_legs.csv]

For each projected player and each stat the venue posts rungs for:
  FLOOR rung     highest posted x+ he reached in EVERY game this season (over leg)
  CONSISTENCY    highest posted x+ reached in all but one game (over leg)
  CEILING        lowest posted x+ he never reached (under leg, "NO x+")
then matchup in that direction, role and news checks, the sim's rate tonight, a blend of season record and sim (sim
worth --k games), the venue price plus fee, and a verdict. With --base legs, the qualifying legs are tested on top of
that parlay using the replayed sims (joint hit rate, correlation included).
A 7-for-7 season is not 100%: the blend and the price decide, never the streak alone.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nfl  # noqa: E402
from nflmodel.market import name_key  # noqa: E402

NO_STATS = {"pass_td", "int"}                 # never bet (CLAUDE.md)
REC = {"targets", "rec", "rec_yds"}
RUSH = {"rush_att", "rush_yds"}
INJ = re.compile(r"questionable|doubtful|\bout\b|game-time", re.I)


def game_logs(m, pid: str, pos: str, season: int, key: int) -> pd.DataFrame:
    if pos == "QB":
        p = m.qbm.p[(m.qbm.p.passer_player_id == pid) & (m.qbm.p.key // 100 == season) & (m.qbm.p.key < key)]
        g = p.groupby(["key", "game_id", "posteam"]).agg(pass_att=("yards", "size"), pass_cmp=("complete", "sum"),
                                                          pass_yds=("yards", "sum")).reset_index()
        g["offense_pct"] = np.nan
        return g.sort_values("key")
    g = m.pg[(m.pg.pid == pid) & (m.pg.key // 100 == season) & (m.pg.key < key)]
    g = g[(g.offense_pct.fillna(0) > 0) | (g.targets > 0) | (g.rush_att > 0)].copy()
    g["rec_rush_yds"] = g.rec_yds + g.rush_yds
    return g.sort_values("key")


def defense(m, season: int, key: int):
    """Opponent rate allowed vs league, per position: yards per target (receiving), per carry (rushing),
    per pass attempt (QB), plus rank (1 = allows the least)."""
    pg = m.pg[(m.pg.key // 100 == season) & (m.pg.key < key)]
    pp = m.qbm.p[(m.qbm.p.key // 100 == season) & (m.qbm.p.key < key)]
    out = {}
    for pos in ("WR", "TE", "RB"):
        d = pg[pg.pos == pos]
        t = d.groupby("defteam").agg(tg=("targets", "sum"), ry=("rec_yds", "sum"), ca=("rush_att", "sum"), rr=("rush_yds", "sum"))
        ypt, ypc = t.ry / t.tg.clip(lower=1), t.rr / t.ca.clip(lower=1)
        lypt, lypc = d.rec_yds.sum() / max(d.targets.sum(), 1), d.rush_yds.sum() / max(d.rush_att.sum(), 1)
        out[(pos, "rec")] = (ypt / lypt, ypt.rank())
        out[(pos, "rush")] = (ypc / lypc, ypc.rank())
    t = pp.groupby("defteam").agg(att=("yards", "size"), yds=("yards", "sum"))
    ypa = t.yds / t.att.clip(lower=1)
    out[("QB", "pass")] = (ypa / (pp.yards.sum() / max(len(pp), 1)), ypa.rank())
    return out


def kind(stat: str) -> str:
    return "pass" if stat.startswith("pass") else ("rush" if stat in RUSH else "rec")


def main(a):
    proj = json.load(open(a.proj))
    key, season = int(proj["key"]), int(proj["key"]) // 100
    away, home = proj["game"].split("@")
    opp = {away: home, home: away}
    qbs = proj["meta"].get("qbs", {})
    news = json.load(open(a.news)) if a.news else []
    # latest status per player (the news file is appended in time order, so a later "Playing" clears an earlier flag)
    latest = {}
    for it in news:
        for n in re.split(r"\s*[/,]\s*", it.get("player", "")):
            latest[name_key(n)] = (it.get("status", ""), it.get("team", ""), n)
    flagged = {k for k, (st, _, _) in latest.items() if INJ.search(st)}
    singles = {(name_key(s.split(":")[0]), s.split(":")[1]) for s in a.singles}
    q = pd.read_csv(a.quotes)
    q["k"] = q.player.map(name_key)
    main_line = {}
    if a.books:                                   # big-book MAIN lines (nfl.py odds without --alt): median per player+stat
        b = pd.read_csv(a.books)
        b = b[~b.venue.str.contains("alt", case=False, na=False)]
        main_line = b.assign(k=b.player.map(name_key)).groupby(["k", "stat"]).line.median().to_dict()
    m = nfl.build_model()
    D = defense(m, season, key)
    rows = []
    for name, pl in proj["players"].items():
        blind = pl.get("blind")
        if blind == "all":
            continue
        pid, pos, team = pl["pid"], pl["pos"], pl["team"]
        g = game_logs(m, pid, pos, season, key)
        if len(g) < a.min_games:
            continue
        # role: last 4 games' share vs the season (receiving uses target share, rushing carry share)
        role = {}
        if pos != "QB":
            for st_kind, col in (("rec", "t_share"), ("rush", "c_share")):
                s, l4 = g[col].mean(), g[col].tail(4).mean()
                role[st_kind] = (l4 >= 0.9 * s, f"{col} last4 {l4:.2f} vs season {s:.2f}")
        # QB in the sample: tonight's QB must have thrown most of this team's passes in his games
        qb_ok = True
        if pos != "QB" and team in qbs:
            qid = nfl.lookup(m, qbs[team])[0]
            pp = m.qbm.p[m.qbm.p.game_id.isin(g.game_id) & (m.qbm.p.posteam == team)]
            qb_ok = len(pp) > 0 and (pp.passer_player_id == qid).mean() >= 0.5
        injured = name_key(name) in flagged
        # under legs assume his usual share; a same-position teammate questionable or out can grow it (Tuten -> Rodriguez)
        mates = [n for n, t in proj["players"].items() if t["team"] == team and t["pos"] == pos and n != name and name_key(n) in flagged]
        mates += [disp for k, (st, tm, disp) in latest.items() if k in flagged and tm.upper() == f"{team} {pos}" and k != name_key(name)
                  and k not in {name_key(n) for n in mates}]
        for stat in pl["stats"]:
            if stat in NO_STATS or (blind and stat in blind) or stat not in g.columns:
                continue
            if pos == "QB" and stat == "rush_yds":
                continue                                            # QB rushing: never tested
            grid = sorted(q[(q.k == name_key(name)) & (q.stat == stat)].line.unique())
            if not grid:
                continue
            vals = g[stat].astype(float).round().tolist()
            n = len(vals)
            srt = sorted(vals)
            cands = []
            fl = [x for x in grid if x <= srt[0]]
            if fl:
                cands.append(("FLOOR", "over", max(fl)))
            cs = [x for x in grid if x <= srt[1]] if n > 1 else []
            if cs and (not fl or max(cs) > max(fl)):
                cands.append(("CONSISTENCY", "over", max(cs)))
            ce = [x for x in grid if x > srt[-1]]
            if ce:
                cands.append(("CEILING", "under", min(ce)))
            ratio, rank = D[(pos if pos in ("WR", "TE", "RB") else "QB", kind(stat))]
            r_opp, rk = float(ratio.get(opp[team], np.nan)), int(rank.get(opp[team], 0))
            ge = pl["stats"][stat]["ge"]
            for label, side, x in cands:
                hits = sum(v >= x for v in vals) if side == "over" else sum(v < x for v in vals)
                last4 = sum((v >= x) if side == "over" else (v < x) for v in vals[-4:])
                gx = ge.get(f"{x:g}", 1.0 if x <= min(map(float, ge)) else 0.0)
                sim = gx if side == "over" else 1 - gx
                blend = (hits + a.k * sim) / (n + a.k)
                px = q[(q.k == name_key(name)) & (q.stat == stat) & (q.line == x) & (q.side == ("yes" if side == "over" else "no"))].price
                price = float(px.iloc[0]) if len(px) else None
                cost = None if price is None else price / 100 + a.fee_single
                match_ok = (r_opp >= 1.0) if side == "over" else (r_opp < 1.0)
                role_ok = True if pos == "QB" else role.get(kind(stat), (True, ""))[0]
                why = []
                if not match_ok: why.append(f"matchup wrong way ({r_opp:.2f}x league, rank {rk})")
                if not role_ok: why.append("role shrinking (" + role[kind(stat)][1] + ")")
                if not qb_ok and kind(stat) == "rec": why.append("different QB tonight")
                if injured: why.append("injury designation")
                if side == "under" and mates: why.append("teammate " + ", ".join(mates) + " questionable/out: role may grow")
                if (name_key(name), stat) in singles: why.append("repeats a single")
                ml = main_line.get((name_key(name), stat))
                if side == "over" and a.books and (ml is None or x >= ml):
                    why.append("over not below the book line" if ml is not None else "no book line to compare")
                if side == "under" and pos == "QB" and stat == "pass_yds": why.append("no QB pass-yds unders")
                if price is None: why.append("no price posted")
                elif blend < cost: why.append("hit rate high, price too high" if blend >= 0.8 else "blend below price")
                rows.append(dict(player=name, team=team, stat=stat, leg=f"{'' if side == 'over' else 'NO '}{x:g}+", rung_type=label,
                                 book_line=ml,
                                 side=side, rung=x, season=f"{hits}/{n}", last4=f"{last4}/{min(4, n)}", values=" ".join(f"{v:g}" for v in vals),
                                 sim=round(sim, 3), blend=round(blend, 3), matchup=f"{r_opp:.2f}x lg, rank {rk}",
                                 price_c=price, cost=None if cost is None else round(cost, 3),
                                 value=None if cost is None else round(blend - cost, 3),
                                 verdict=("ADD (low-rung over, untested)" if side == "over" else "ADD") if not why else "skip: " + "; ".join(why)))
    R = pd.DataFrame(rows)
    if R.empty:
        print("No floor or ceiling candidates with posted rungs."); return
    R = R.sort_values(["verdict", "value"], ascending=[True, False], key=lambda s: s.str.startswith("skip") if s.name == "verdict" else s)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    print(R[["player", "stat", "leg", "rung_type", "season", "last4", "sim", "blend", "matchup", "price_c", "value", "verdict"]].to_string(index=False))
    if a.out:
        R.to_csv(a.out, index=False); print(f"\nsaved {len(R)} candidates -> {a.out}")
    adds = R[R.verdict.str.startswith("ADD")]
    if a.base:
        parlays(a, proj, R, adds)


def parlays(a, proj, R, adds):
    """Base parlay alone, then base + each qualifying leg, then base + the best two: joint rate from the replayed sims."""
    sys.path.insert(0, str(HERE / "simcast"))
    from rerun import check, rerun
    run = rerun(a.proj)
    if check(run):
        sys.exit("Replay does not match the saved projections; parlay rates not trusted.")
    sim, names = run["sim"]["players"], run["names"]
    pid = {name_key(v): k for k, v in names.items()}
    def hits(player, stat, side, x):
        v = np.asarray(sim[pid[name_key(player)]][stat])
        return v >= x if side == "over" else v < x
    base = []
    for spec in a.base:
        pl, st, side, x, price = (spec.split(":") + [None])[:5]
        base.append((f"{'NO ' if side == 'under' else ''}{pl} {float(x):g}+ {st}", hits(pl, st, side, float(x)), float(price) if price else None))
    def show(legs):
        j = np.logical_and.reduce([h for _, h, _ in legs]).mean()
        ind = np.prod([h.mean() for _, h, _ in legs])
        prices = [p for _, _, p in legs]
        combo = None if any(p is None for p in prices) else np.prod([p / 100 for p in prices])
        cost = None if combo is None else combo + a.fee_combo
        print(f"  {' + '.join(lb for lb, _, _ in legs):<95} sim hit {j:6.1%}  lift {j / ind:4.2f}"
              + ("" if cost is None else f"  price ~{combo * 100:4.1f}c  cost {cost:5.1%}  edge {j - cost:+6.1%}  max {max(j - a.fee_combo - a.min_edge, 0) * 100:4.1f}c"))
    print("\nParlays (joint sim hit rate from the replayed sims; price = legs multiplied unless quoted):")
    show(base)
    in_base = {name_key(b.split(':')[0]) for b in a.base}
    extra, seen = [], set()
    for r in adds.sort_values("value", ascending=False).itertuples():
        if name_key(r.player) in in_base:
            continue
        lab = f"{'NO ' if r.side == 'under' else ''}{r.player} {r.rung:g}+ {r.stat}"
        extra.append((lab, hits(r.player, r.stat, r.side, r.rung), r.price_c, name_key(r.player)))
    for e in extra[:6]:
        show(base + [e[:3]])
    # best two legs from different players (max 2 floor or ceiling legs per parlay, FLOOR_PROMPT.md step 6)
    two = []
    for e in extra:
        if e[3] not in seen:
            two.append(e[:3]); seen.add(e[3])
        if len(two) == 2:
            break
    if len(two) == 2:
        show(base + two)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proj", required=True)
    ap.add_argument("--quotes", required=True, help="venue ladder quotes (kalshi_quotes.py format: cents, yes/no on x+ rungs)")
    ap.add_argument("--news")
    ap.add_argument("--base", nargs="*", default=[], help='parlay legs "Player:stat:over|under:x[:price_cents]"')
    ap.add_argument("--books", help="big-book main lines CSV (nfl.py odds): over legs must sit BELOW the book line")
    ap.add_argument("--min-edge", type=float, default=0.10, help="parlay edge required (CLAUDE.md 2026-11-05: 10%%)")
    ap.add_argument("--singles", nargs="*", default=[], help='"Player:stat" already bet as singles (no parlay leg repeats a single)')
    ap.add_argument("--out")
    ap.add_argument("--k", type=float, default=10.0, help="games the sim counts for in the blend")
    ap.add_argument("--min-games", type=int, default=4)
    ap.add_argument("--fee-single", type=float, default=0.015, help="observed 2026-11-05: 1.5c per contract")
    ap.add_argument("--fee-combo", type=float, default=0.024, help="observed 2026-11-05: about 2.4c per contract")
    main(ap.parse_args())
