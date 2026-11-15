"""Tight ranges with confidence (RANGES_PROMPT.md; Travis 2026-11-15).

    python ranges.py projections/<season>_wk<NN>_<AWAY>_at_<HOME>.json [--out analysis/<game>_ranges.md]

For every skill player and stat (QB pass yds and attempts; receivers' catches and yards; rushers' yards):
* PREDICTION of record (best estimate where a book line exists, else the model's median) from the SizzleSims file.
* Tight windows from the replayed sims (50% and 70% central windows) with a CONFIDENCE: how often that window type
  actually held in the backtest (nflmodel/window_calibration.json: 43,489 production-model predictions, 2024-26).
* RATING (High / Medium / Low) and a RANK (confidence first, then tightness relative to the prediction).
* CONTEXT LANDING (untested, Travis: "don't pull them out"): the prediction moved by every context factor, each shown:
  matchup (yards allowed to his position vs league, half weight), role trend (last 4 games' share vs season, half weight),
  history vs this opponent (shrunk by games: n / (n + 6)), home/away split this season (shrunk n / (n + 8)). Scheme context
  (PFF pressure, coverage, run blocking) and weather are listed beside it. The context landing is a SCENARIO graded every
  week beside the record; it is never the prediction of record until a MODEL_LAB test says so.
PFF numbers (routes, grades) print to the console only; the saved file keeps qualitative labels (PFF data is licensed).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "simcast"))
from floor_legs import defense, game_logs  # noqa: E402

CAL = json.loads((HERE / "nflmodel/window_calibration.json").read_text())["types"]
STATS = {"QB": ["pass_yds", "pass_att"], "WR": ["rec", "rec_yds"], "TE": ["rec", "rec_yds"], "RB": ["rush_yds", "rec", "rec_yds"]}
LABEL = {"pass_yds": "pass yds", "pass_att": "attempts", "rec": "catches", "rec_yds": "rec yds", "rush_yds": "rush yds"}


def tier(pos, stat, season_logs):
    if pos == "QB":
        return "qb"
    if stat == "rush_yds":
        return "leader" if season_logs.c_share.mean() >= 0.30 else "depth"
    return "leader" if season_logs.t_share.mean() >= 0.12 else "depth"


def rating(c70):
    return "High" if c70 >= 0.685 else ("Medium" if c70 >= 0.668 else "Low")


def shrink(ratio, n, k):
    return 1.0 + (ratio - 1.0) * n / (n + k) if np.isfinite(ratio) and n else 1.0


def main(a) -> int:
    from rerun import rerun, check
    with contextlib.redirect_stdout(io.StringIO()):
        run = rerun(a.proj)
    bad = check(run)
    if bad:
        sys.exit("STOP: projections cannot be reproduced:\n" + "\n".join(bad[:5]))
    m, proj, key = run["model"], run["proj"], run["key"]
    season = key // 100
    away, home = run["away"], run["home"]
    opp = {home: away, away: home}
    S = run["sim"]["players"]
    gfile = HERE / "simcast/games" / (Path(a.proj).stem + ".json")
    pred = {(p["name"], p["stat"]): p for p in json.loads(gfile.read_text())["pred"]} if gfile.exists() else {}
    blind, blind_stats = set(), {}
    for b in proj["meta"].get("adjustments", {}).get("blind") or []:
        if ":" in b:
            nm_, st_ = b.split(":", 1)
            blind_stats.setdefault(nm_, set()).update(st_.split(","))
        else:
            blind.add(b)
    D = defense(m, season, key)
    pffm = getattr(m, "pffm", None)
    if pffm is None:
        try:
            from nflmodel.pff_matchups import PFFMatchups
            with contextlib.redirect_stdout(io.StringIO()):
                pffm = PFFMatchups(m)
        except Exception as e:                      # scheme context is optional
            print(f"(scheme context unavailable: PFF defensive facets not in data/pff on this machine: {e})")
            pffm = None
    from nflmodel.market import name_key
    rr = getattr(m, "route_role", None)
    snaps = pd.read_parquet(HERE / f"data/snap_counts_{season}.parquet", columns=["week", "player", "team", "offense_pct"])
    snaps["k"] = snaps.player.map(name_key)
    meta = proj["meta"]
    rows, ctx_lines, console = [], {}, []
    for name, pl in proj["players"].items():
        pid, pos, team = pl["pid"], pl["pos"], pl["team"]
        if pos not in STATS or pid not in S:
            continue
        grades = {p_["grade"] for (n_, s_), p_ in pred.items() if n_ == name}
        rl = m.pg[(m.pg.pid == pid) & (m.pg.key // 100 == season) & (m.pg.key < key)]
        real_role = pos == "QB" or (len(rl) and (rl.t_share.mean() >= 0.12 or rl.c_share.mean() >= 0.30))
        blind_flag = name in blind or not (grades & {"A", "B"})
        if blind_flag and not real_role:
            continue                                   # depth players: no tight ranges
        # blind spots with a real role (new QB, return from IR) stay in, rated Low (blind spot)
        g_all = game_logs(m, pid, pos, season, key)
        hist = m.pg[(m.pg.pid == pid) & (m.pg.key < key) & (m.pg.key // 100 >= season - 2)] if pos != "QB" else None
        if pos == "QB":
            qp = m.qbm.p[(m.qbm.p.passer_player_id == pid) & (m.qbm.p.key < key) & (m.qbm.p.key // 100 >= season - 2)]
            hist = qp.groupby(["key", "game_id", "posteam"]).agg(pass_att=("yards", "size"), pass_yds=("yards", "sum")).reset_index()
            hist["defteam"] = [gid.split("_")[2] if gid.split("_")[3] == t else gid.split("_")[3] for gid, t in zip(hist.game_id, hist.posteam)]
            hist["home"] = [gid.split("_")[3] == t for gid, t in zip(hist.game_id, hist.posteam)]
        else:
            hist = hist.assign(home=[gid.split("_")[3] == t for gid, t in zip(hist.game_id, hist.posteam)])
        this = hist[hist.key // 100 == season]
        is_home = team == home
        # role, snaps, routes (last 4 vs season)
        role = ""
        if pos != "QB" and len(this):
            ts4, ts = this.t_share.tail(4).mean(), this.t_share.mean()
            cs4, cs = this.c_share.tail(4).mean(), this.c_share.mean()
            sn = snaps[(snaps.k == name_key(name)) & (snaps.team == team)].sort_values("week").offense_pct.tail(4).tolist()
            role = f"snaps last 4: {', '.join(f'{100 * x:.0f}%' for x in sn) or 'n/a'}; target share last 4 {100 * ts4:.0f}% vs season {100 * ts:.0f}%"
            if pos == "RB":
                role += f"; carry share last 4 {100 * cs4:.0f}% vs season {100 * cs:.0f}%"
            if rr is not None and pid in rr._by:
                rp = rr._by[pid]
                rp = rp[rp.key < key]
                if len(rp):
                    r3, rs = rp.rp.tail(3).mean(), rp[rp.key // 100 == season].rp.mean()
                    trend = "rising" if r3 > 1.1 * rs else ("falling" if r3 < 0.9 * rs else "steady")
                    role += f"; routes trend {trend}"
                    console.append(f"  [PFF, console only] {name}: route participation last 3 {100 * r3:.0f}% vs season {100 * rs:.0f}%")
        scheme = []
        if pffm is not None:
            try:
                if pos in ("QB", "WR", "TE"):
                    xp = pffm.x_pass_pro(team, opp[team], key)
                    scheme.append("pressure matchup " + ("tough" if xp > 0.15 else ("soft" if xp < -0.15 else "neutral")))
                    console.append(f"  [PFF, console only] {name}: pass-pro x {xp:+.2f}")
                if pos in ("WR", "TE", "RB"):
                    xc = pffm.x_coverage(opp[team], key, pos)
                    scheme.append(f"coverage vs {pos} " + ("strong" if xc > 2 else ("weak" if xc < -2 else "average")))
                    console.append(f"  [PFF, console only] {name}: coverage grade vs league {xc:+.1f}")
                if pos == "RB":
                    xr = pffm.x_run_block(team, opp[team], key)
                    scheme.append("run blocking vs run D " + ("edge offense" if xr > 2 else ("edge defense" if xr < -2 else "even")))
            except Exception:
                pass
        for st in STATS[pos]:
            if st not in S[pid]:
                continue
            x = np.asarray(S[pid][st], float)
            p = pred.get((name, st), {})
            pv = p.get("best") if p.get("best") is not None else float(np.median(x))
            tr = tier(pos, st, this) if len(this) else "depth"
            cal = CAL.get(f"{tr}:{st}") or CAL.get(f"{tr}:rec_yds")
            # windows keep the sims' spread but are centered on the record (best estimate), so the prediction and its
            # windows agree; a shift bigger than half the 50% window = model and market disagree (flagged)
            med = float(np.median(x))
            shift = pv - med
            w50, w70 = (np.percentile(x, 25) + shift, np.percentile(x, 75) + shift), (np.percentile(x, 15) + shift, np.percentile(x, 85) + shift)
            w50, w70 = (max(0.0, w50[0]), w50[1]), (max(0.0, w70[0]), w70[1])
            gap = abs(shift) > 0.5 * (np.percentile(x, 75) - np.percentile(x, 25)) and abs(shift) >= 1
            if st in ("rec", "pass_att"):                  # counts: whole numbers, and the window holds the prediction
                w50 = (min(np.floor(pv), round(w50[0])), max(np.ceil(pv), round(w50[1])))
                w70 = (min(w50[0], round(w70[0])), max(w50[1], round(w70[1])))
            if pv < (0.5 if st == "rec" else 3):
                continue                                   # no real role in this stat tonight
            sb = blind_flag or st in blind_stats.get(name, set()) or (st in ("rec", "rec_yds") and "targets" in blind_stats.get(name, set()))
            # context factors (untested)
            kind = "rush" if st == "rush_yds" else ("pass" if pos == "QB" else "rec")
            dk = (pos if pos in ("WR", "TE", "RB") else "QB", kind)
            ratio, rank = D[dk]
            mr = float(ratio.get(opp[team], np.nan)); rk = int(rank.get(opp[team], 0))
            f_m = 1 + 0.5 * (mr - 1) if np.isfinite(mr) and st != "pass_att" and st != "rec" else 1.0
            f_r = 1.0
            if pos != "QB" and len(this) >= 3:
                col = "c_share" if st == "rush_yds" else "t_share"
                s_all = this[col].mean()
                f_r = 1 + 0.5 * (this[col].tail(4).mean() / s_all - 1) if s_all > 0 else 1.0
            vs = hist[hist.defteam == opp[team]][st] if st in hist.columns else pd.Series(dtype=float)
            base = hist[st].mean() if st in hist.columns and len(hist) else np.nan
            f_h = shrink(vs.mean() / base, len(vs), 6) if len(vs) and base and base > 0 else 1.0
            side = this[this.home == is_home][st] if st in this.columns else pd.Series(dtype=float)
            sbase = this[st].mean() if st in this.columns and len(this) else np.nan
            f_ha = shrink(side.mean() / sbase, len(side), 8) if len(side) and sbase and sbase > 0 else 1.0
            ctx = pv * f_m * f_r * f_h * f_ha
            lean = "up" if ctx > 1.05 * pv else ("down" if ctx < 0.95 * pv else "even")
            rows.append(dict(player=name, team=team, pos=pos, stat=st, pred=pv, w50=w50, w70=w70, c50=cal["50"], c70=cal["70"],
                             rating="Low (blind spot)" if sb else rating(cal["70"]), rel=(w70[1] - w70[0]) / max(pv, 1), ctx=ctx, lean=lean,
                             f_m=f_m, mr=mr, rk=rk, f_r=f_r, f_h=f_h, n_h=len(vs), f_ha=f_ha, n_ha=len(side),
                             model=med, gap=gap))
        ctx_lines[name] = (team, pos, role, scheme, is_home)
    R = pd.DataFrame(rows)
    R["_b"] = R.rating.str.startswith("Low (blind")
    R = R.sort_values(["_b", "c70", "rel"], ascending=[True, False, True]).drop(columns="_b").reset_index(drop=True)
    R.index += 1
    fmt = lambda v, st: f"{v:.0f}" if st in ("pass_yds", "rec_yds", "rush_yds", "pass_att") else f"{v:.1f}"
    g = json.loads(gfile.read_text()) if gfile.exists() else {}
    wx = [f"wind {meta['wind']:g} mph (in the sims)" if meta.get("wind") else "no wind input",
          "rain ON (in the sims)" if meta.get("rain") else "no rain input"]
    L = [f"# Tight ranges: {away} at {home} (week {key % 100}, {season})", "",
         f"Record: {away} {g.get('final', {}).get(away, '?')}, {home} {g.get('final', {}).get(home, '?')}; win {g.get('win', {})}; "
         f"line {meta.get('fav')} -{meta.get('spread')}, total {meta.get('total')}. Weather: {', '.join(wx)}. {home} at home.", "",
         "Confidence = how often that window type held in the backtest (43,489 predictions, 2024-26). Prediction = the record.",
         "Context landing = the record moved by matchup, role trend, history vs this team and home/away (UNTESTED scenario,",
         "graded weekly beside the record).", "",
         "Windows: the sims' spread, centered on the prediction of record. GAP = the model's own median sits far from the",
         "market (model median shown); trust the market side more (it has beaten the model on every stat).", "",
         "| Rank | Player | Stat | Prediction | 50% window (conf) | 70% window (conf) | Rating | Context landing | Lean | Flag |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in R.iterrows():
        L.append(f"| {i} | {r.player} ({r.team}) | {LABEL[r.stat]} | {fmt(r.pred, r.stat)} | {fmt(r.w50[0], r.stat)}-{fmt(r.w50[1], r.stat)} ({r.c50:.0%}) | "
                 f"{fmt(r.w70[0], r.stat)}-{fmt(r.w70[1], r.stat)} ({r.c70:.0%}) | {r.rating} | {fmt(r.ctx, r.stat)} | {r.lean} | "
                 f"{'GAP: model ' + fmt(r.model, r.stat) if r.gap else ''} |")
    L += ["", "## Context behind each landing (untested factors, each shown)", ""]
    for name, (team, pos, role, scheme, is_home) in ctx_lines.items():
        sub = R[R.player == name]
        if sub.empty:
            continue
        parts = []
        for _, r in sub.iterrows():
            mtxt = f"matchup {r.mr:.2f}x lg (rank {r.rk}) x{r.f_m:.2f}" if np.isfinite(r.mr) and r.f_m != 1.0 else "matchup n/a"
            parts.append(f"{LABEL[r.stat]}: {mtxt}; role x{r.f_r:.2f}; vs {opp[team]} {r.n_h} games x{r.f_h:.2f}; "
                         f"{'home' if is_home else 'away'} {r.n_ha} games x{r.f_ha:.2f}")
        L.append(f"* **{name}** ({team} {pos}, {'home' if is_home else 'away'}): {role or 'QB'}" + (f"; scheme: {', '.join(scheme)}" if scheme else ""))
        for ptxt in parts:
            L.append(f"  * {ptxt}")
    txt = "\n".join(L) + "\n"
    if a.out:
        Path(a.out).write_text(txt)
        cols = ["player", "team", "pos", "stat", "pred", "model", "gap", "ctx", "lean", "c50", "c70", "rating", "f_m", "f_r", "f_h", "n_h", "f_ha", "n_ha"]
        C = R[cols].assign(w50_lo=[w[0] for w in R.w50], w50_hi=[w[1] for w in R.w50], w70_lo=[w[0] for w in R.w70], w70_hi=[w[1] for w in R.w70])
        C.to_csv(Path(a.out).with_suffix(".csv"), index_label="rank")   # graded after the game (record vs context landing)
    print(txt)
    print("\n".join(console))
    if a.out:
        print(f"saved -> {a.out} (PFF numbers above are console only)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--out")
    sys.exit(main(ap.parse_args()))
