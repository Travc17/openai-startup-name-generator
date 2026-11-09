"""Grade every game we projected against the real box scores (GRADE_PROMPT.md). No sims are rerun.

    python grade_week.py --week 9                 # every 2026 week 9 game we projected
    python grade_week.py --week all               # every projected game already in the data
    python grade_week.py --week 9 --simcast       # also attach scorecards to the SizzleSims game files
    python grade_week.py --week 9 --league        # also grade the live model on EVERY game that week

The prediction of record is the SAVED pre-kickoff projections file plus its SizzleSims game file (predicted
score, win chance, book line, 20/80 best estimate). A rerun after `nfl.py update` cannot match it exactly:
nflverse and PFF revise earlier weeks' data (2026-11-08 test: removing the week's own rows changed nothing).
Actuals come from nflverse play by play (player game logs and QB passing); cross-check the QB lines against
an ESPN box score before publishing (GRADE_PROMPT.md step 2).

Writes reviews/<season>_wk<NN>_grades.csv (one row per prediction), reviews/<season>_wk<NN>_grade.md, and
merges every row into reviews/grades_log.csv so patterns can be counted across games and weeks.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "simcast"))

import nfl  # noqa: E402
from export import actuals, predictions  # noqa: E402

REV = HERE / "reviews"
LOG = REV / "grades_log.csv"
COUNT_STATS = {"rec", "targets", "rush_att", "pass_cmp", "pass_att", "pass_td", "int"}


def ge(st: dict, x: float) -> float:
    """P(stat >= x) from the saved half-unit grid."""
    g = st["ge"]
    k = f"{x:g}"
    if k in g:
        return float(g[k])
    ks = sorted(float(v) for v in g)
    return 1.0 if x <= ks[0] else 0.0


def pit(st: dict, y: float) -> float:
    """Mid-PIT for a whole-number result: 0.5 = the result sat at the model's median, 0.05 = far below."""
    return float(1 - (ge(st, y) + ge(st, y + 0.5)) / 2)


INJ = re.compile(r"([A-Z]{2,3})-\d+-([A-Z][A-Za-z.'\- ]*?) was injured during the play")
BACK = re.compile(r"([A-Z]{2,3})-\d+-([A-Z][A-Za-z.'\- ]*?) has returned to the game")


def abbr_match(abbr: str, full: str) -> bool:
    """'R.Stevenson' or 'Ja.Chase' vs 'Rhamondre Stevenson' / "Ja'Marr Chase"."""
    if "." not in abbr:
        return False
    ini, last = abbr.split(".", 1)
    f = full.replace("'", "").split()
    sfx = {"Jr.", "Sr.", "II", "III", "IV", "V"}
    f = [w for w in f if w not in sfx]
    return len(f) >= 2 and f[-1].lower() == last.strip().replace("'", "").lower() and f[0].lower().startswith(ini.lower())


def in_game(game_id: str, season: int) -> tuple[dict, list]:
    """Last touch per player (quarter, clock) and the in-game injury notes from the play-by-play text."""
    pb = pd.read_parquet(nfl.data.DATA_DIR / f"pbp_{season}.parquet",
                         columns=["game_id", "qtr", "time", "game_seconds_remaining", "rusher_player_id", "receiver_player_id", "desc"])
    g = pb[pb.game_id == game_id]
    last = {}
    for col in ("rusher_player_id", "receiver_player_id"):
        for pid, d in g[g[col].notna()].groupby(col):
            r = d.loc[d.game_seconds_remaining.idxmin()]
            if pid not in last or r.game_seconds_remaining < last[pid][2]:
                last[pid] = (int(r.qtr), str(r.time), float(r.game_seconds_remaining))
    notes = []
    for r in g[g.desc.str.contains("injured during the play|has returned to the game", na=False)].itertuples():
        for m_ in INJ.finditer(r.desc):
            notes.append(dict(team=m_.group(1), abbr=m_.group(2).strip(), qtr=int(r.qtr), time=str(r.time), kind="injured"))
        for m_ in BACK.finditer(r.desc):
            notes.append(dict(team=m_.group(1), abbr=m_.group(2).strip(), qtr=int(r.qtr), time=str(r.time), kind="returned"))
    return last, notes


def files_for(week: str, season: int) -> list[Path]:
    pat = f"{season}_wk*_*_at_*.json" if week == "all" else f"{season}_wk{int(week):02d}_*_at_*.json"
    return sorted((HERE / "projections").glob(pat))


def grade_game(m, path: Path) -> tuple[list[dict], dict] | None:
    P = json.load(open(path))
    key, (away, home) = int(P["key"]), P["game"].split("@")
    act = actuals({"model": m, "key": key, "home": home, "away": away})
    if act is None:
        return None
    gfile = HERE / "simcast" / "games" / f"{path.stem}.json"
    G = json.load(open(gfile)) if gfile.exists() else {}
    preds = G.get("pred") or predictions({"proj": P})
    by_pid = {pl["pid"]: pl for pl in P["players"].values()}
    gid = m.pg[(m.pg.key == key) & (m.pg.posteam.isin([home, away]))].game_id.iloc[0]
    last, notes = in_game(gid, key // 100)
    snaps_in = bool(m.pg[m.pg.game_id == gid].offense_pct.notna().any())
    # early exit: last touch before halftime for a player the model gave 4+ touches (targets + carries medians)
    exited = set()
    for pl in P["players"].values():
        st_ = pl["stats"]
        touches = st_.get("targets", {"q": [0, 0, 0]})["q"][2] + st_.get("rush_att", {"q": [0, 0, 0]})["q"][2]
        if pl["pos"] != "QB" and touches >= 4 and pl["pid"] in last and last[pl["pid"]][2] > 1800:
            exited.add(pl["pid"])
    inj = {}
    for pl_name, pl in P["players"].items():
        hits = [n for n in notes if n["team"] == pl["team"] and abbr_match(n["abbr"], pl_name)]
        if hits:
            hurt = [n for n in hits if n["kind"] == "injured"]
            back = [n for n in hits if n["kind"] == "returned"]
            if hurt:
                h = hurt[0]
                inj[pl["pid"]] = f"injured Q{h['qtr']} {h['time']}" + (", returned" if back else ", did not return")
    resim = bool(P.get("meta", {}).get("resim")) or "resim" in path.stem
    rows, dnp = [], []
    for r in preds:
        y = act["stats"].get(r["pid"], {}).get(r["stat"])
        if y is None:
            dnp.append(f"{r['name']} {r['stat']}")
            continue
        st = by_pid.get(r["pid"], {}).get("stats", {}).get(r["stat"])
        book, best = r.get("book"), r.get("best")
        row = dict(game=path.stem, resim=resim, team=r["team"], name=r["name"], pos=r["pos"], stat=r["stat"],
                   grade=r["grade"], median=r["median"], lo=r["lo"], hi=r["hi"], book=book, best=best, actual=y,
                   inside=bool(r["lo"] <= y <= r["hi"]), side="in" if r["lo"] <= y <= r["hi"] else ("below" if y < r["lo"] else "above"),
                   pit=round(pit(st, y), 3) if st and "ge" in st else np.nan, err_model=abs(y - r["median"]),
                   last_touch=f"Q{last[r['pid']][0]} {last[r['pid']][1]}" if r["pid"] in last else "",
                   injury=inj.get(r["pid"], ""),
                   early_exit=bool(r["pid"] in exited))
        if book is not None:
            row.update(err_book=abs(y - book), err_best=abs(y - best))
            lean = np.sign(round(r["median"] - book, 6))
            row["lean"] = {1: "over", -1: "under", 0: "even"}[int(lean)]
            row["lean_right"] = None if lean == 0 or y == book else bool(np.sign(y - book) == lean)
        rows.append(row)
    fin = act["final"]
    meta = P.get("meta", {})
    fav, spread, total = meta.get("fav"), meta.get("spread"), meta.get("total")
    pred_fin = G.get("final") or {}
    hurt_team = sorted({f"{nm} ({p['team']} {p['pos']}): {inj[p['pid']]}" for nm, p in P["players"].items() if p["pid"] in inj})
    exits = sorted({f"{r['name']} (last touch {r['last_touch']})" for r in rows if r["early_exit"] and not r["injury"]})
    score = dict(game=path.stem, away=away, home=home, actual=fin, predicted=pred_fin, win=G.get("win"),
                 fav=fav, spread=spread, total=total, dnp=dnp, resim=resim, injuries=hurt_team, exits=exits,
                 snaps=snaps_in, other_injuries=[f"{n['team']} {n['abbr']} Q{n['qtr']} {n['time']}" for n in notes
                                                 if n["kind"] == "injured" and not any(abbr_match(n["abbr"], k) for k in P["players"])])
    if pred_fin:
        am, pm = fin[home] - fin[away], pred_fin[home] - pred_fin[away]
        lm = (spread if fav == home else -spread) if spread is not None else None
        score.update(winner_right=bool(np.sign(am) == np.sign(pm)) if am else None, margin_err_model=abs(am - pm),
                     margin_err_line=abs(am - lm) if lm is not None else None,
                     total_err_model=abs(sum(fin.values()) - sum(pred_fin.values())),
                     total_err_line=abs(sum(fin.values()) - total) if total is not None else None)
    if G:
        G["_grade_rows"] = rows
    return rows, score


def attach_simcast(path: Path, rows: list[dict], score: dict) -> None:
    gfile = HERE / "simcast" / "games" / f"{path.stem}.json"
    if not gfile.exists():
        return
    G = json.load(open(gfile))
    look = {(r["name"], r["stat"]): r for r in rows}
    card = {"A": [0, 0], "B": [0, 0], "C": [0, 0]}
    for p in G.get("pred", []):
        r = look.get((p["name"], p["stat"]))
        if r is None:
            continue
        p["actual"], p["in_range"] = r["actual"], r["inside"]
        card[p["grade"]][0] += r["inside"]
        card[p["grade"]][1] += 1
    G["actual"] = {"final": score["actual"], "card": card,
                   "source": f"nflverse play by play (graded {datetime.now(timezone.utc):%Y-%m-%d})"}
    gfile.write_text(json.dumps(G, separators=(",", ":"), default=int))


def pct(a, b):
    return f"{a / b:.0%} ({a}/{b})" if b else "n/a"


def summary(df: pd.DataFrame, scores: list[dict], title: str) -> list[str]:
    L = [f"# {title}", "", f"Graded {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from the saved pre-kickoff files "
         "(no reruns). Actuals: nflverse play by play.", ""]
    live = df[~df.resim]
    L += ["## Scores", "", "| Game | Predicted | Actual | Win chance | Winner | Margin miss: model / line | Total miss: model / line |",
          "|---|---|---|---|---|---|---|"]
    for s in scores:
        a, h = s["away"], s["home"]
        pf, af = s["predicted"], s["actual"]
        w = s.get("win") or {}
        L.append(f"| {a} at {h}{' (resim)' if s['resim'] else ''} | {a} {pf.get(a, '?')}, {h} {pf.get(h, '?')} | {a} {af[a]}, {h} {af[h]} | "
                 f"{a} {w.get(a, float('nan')):.0%} | {'right' if s.get('winner_right') else 'wrong'} | "
                 f"{s.get('margin_err_model', '?')} / {s.get('margin_err_line', '?')} | {s.get('total_err_model', '?')} / {s.get('total_err_line', '?')} |")
    L += ["", "## In-game injuries and early exits (play-by-play text; confirm each with a news link)", ""]
    for s_ in scores:
        if s_["injuries"] or s_["exits"]:
            L.append(f"* {s_['away']} at {s_['home']}: " + "; ".join(s_["injuries"] + [f"early exit, no injury note: {e}" for e in s_["exits"]]))
    if not any(s_["injuries"] or s_["exits"] for s_ in scores):
        L.append("* none found")
    L += ["", "Rows for a player injured in-game who did not return are graded as usual (the model does not simulate it) and",
          "also shown without them below, so an injury does not hide a real model miss.", ""]
    nosnap = [s_["game"] for s_ in scores if not s_["snaps"]]
    if nosnap:
        L += [f"SNAP COUNTS NOT POSTED for {', '.join(nosnap)}: players who played without a touch are missing (not graded as 0).",
              "Regrade after nflverse posts snap counts (usually 1 to 2 days).", ""]
    L += ["", "## Inside the 80% range (about 80% = calibrated)", "", "| Grade | Inside | Below range | Above range |", "|---|---|---|---|"]
    for g in ("A", "B", "C"):
        d = live[live.grade == g]
        L.append(f"| {g} | {pct(int(d.inside.sum()), len(d))} | {int((d.side == 'below').sum())} | {int((d.side == 'above').sum())} |")
    d = live[live.grade.isin(["A", "B"])]
    L.append(f"| A+B | {pct(int(d.inside.sum()), len(d))} | {int((d.side == 'below').sum())} | {int((d.side == 'above').sum())} |")
    c = d[~d.injury.str.contains("did not return", na=False) & ~d.early_exit]
    L.append(f"| A+B without players hurt or out early | {pct(int(c.inside.sum()), len(c))} | {int((c.side == 'below').sum())} | {int((c.side == 'above').sum())} |")
    L += ["", "## By stat (A and B grades; mean PIT 0.50 = no bias, above = model too LOW, below = too HIGH)", "",
          "| Stat | n | Inside 80% | Mean PIT | Actual minus median (median of rows) | Model miss | Book miss | Best miss |",
          "|---|---|---|---|---|---|---|---|"]
    for st, d in live[live.grade.isin(["A", "B"])].groupby("stat"):
        b = d[d.book.notna()]
        L.append(f"| {st} | {len(d)} | {d.inside.mean():.0%} | {d.pit.mean():.2f} | {(d.actual - d['median']).median():+.1f} | "
                 f"{d.err_model.mean():.1f} | {b.err_book.mean() if len(b) else float('nan'):.1f} | {b.err_best.mean() if len(b) else float('nan'):.1f} |")
    b = live[live.book.notna() & live.grade.isin(["A", "B"])]
    L += ["", "## Model vs book vs best estimate (A and B rows with a book line)", ""]
    if len(b):
        L += [f"* Mean miss: model {b.err_model.mean():.2f}, book {b.err_book.mean():.2f}, best (20/80) {b.err_best.mean():.2f} (n={len(b)}).",
              f"* Closest to the result: model {int((b.err_model < b.err_book).sum())}, book {int((b.err_book < b.err_model).sum())}, tie {int((b.err_model == b.err_book).sum())}."]
        lr = b[b.lean_right.notna()]
        for side in ("under", "over"):
            d = lr[lr.lean == side]
            L.append(f"* Model {side} the book: actual landed on the model's side {pct(int(d.lean_right.sum()), len(d))}.")
    L += ["", "## Biggest misses (outside the 80% range, A and B, farthest first)", "",
          "| Game | Player | Stat | Median | 80% range | Book | Actual | PIT | In-game |", "|---|---|---|---|---|---|---|---|---|"]
    miss = live[(~live.inside) & live.grade.isin(["A", "B"])].assign(dist=lambda x: (x.pit - 0.5).abs()).sort_values("dist", ascending=False)
    for r in miss.head(15).itertuples():
        L.append(f"| {r.game.split('_', 2)[2]} | {r.name} | {r.stat} | {r.median:g} | {r.lo:g} to {r.hi:g} | "
                 f"{'' if pd.isna(r.book) else f'{r.book:g}'} | {r.actual:g} | {r.pit:.2f} | {r.injury or ('last touch ' + r.last_touch if r.early_exit else '')} |")
    dnp = [f"{s['game']}: {', '.join(s['dnp'])}" for s in scores if s["dnp"]]
    if dnp:
        L += ["", "Predicted but no stat line (inactive or no snaps; check the news file): " + "; ".join(dnp)]
    if df.resim.any():
        L += ["", "Resim games (re-simulated after the fact with pre-game inputs) are listed in the scores table and the CSV",
              "but left out of every percentage above."]
    return L


def league(m, season: int, week: int) -> list[str]:
    import regression_check as rc
    raw = rc.run(season, [week], sims=2000, m=m, raw=True)
    base = json.loads(rc.BASELINE.read_text())["stats"] if rc.BASELINE.exists() else {}
    L = ["", f"## Every game of {season} week {week} (live model, real starting QBs, closing spread, players who played)", "",
         "Calibrated reads 10 / 50 / 90. Baseline = regression sample (2025 weeks 10-13).", "",
         "| Stat | n | under p10 | under p50 | under p90 | baseline p10 / p50 / p90 |", "|---|---|---|---|---|---|"]
    for st, d in raw.groupby("stat", sort=False):
        b = base.get(st, {})
        L.append(f"| {st} | {len(d)} | {(d.pit < .1).mean():.0%} | {(d.pit < .5).mean():.0%} | {(d.pit < .9).mean():.0%} | "
                 f"{b.get('cov10', '?')} / {b.get('cov50', '?')} / {b.get('cov90', '?')} |")
    L += ["", "under p50 above 50% = results came in BELOW the model's median more often than they should (model high);",
          "below 50% = model low. One week of about 14 games moves these by several points on noise alone."]
    return L


def main(a) -> int:
    m = nfl.build_model()
    rows, scores = [], []
    paths = files_for(a.week, a.season)
    for p in paths:
        g = grade_game(m, p)
        if g is None:
            print(f"{p.stem}: not in the data yet (run `python nfl.py update`)")
            continue
        rows += g[0]
        scores.append(g[1])
        if a.simcast:
            attach_simcast(p, *g)
        print(f"{p.stem}: {len(g[0])} predictions graded")
    if not rows:
        print("Nothing to grade.")
        return 1
    df = pd.DataFrame(rows)
    tag = f"{a.season}_wk{int(a.week):02d}" if a.week != "all" else f"{a.season}_all"
    REV.mkdir(exist_ok=True)
    df.to_csv(REV / f"{tag}_grades.csv", index=False)
    old = pd.read_csv(LOG) if LOG.exists() else pd.DataFrame()
    log = pd.concat([old[~old.game.isin(df.game)] if len(old) else old, df.assign(graded_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d"))])
    log.to_csv(LOG, index=False)
    title = f"Grades: {a.season} week {a.week}" if a.week != "all" else f"Grades: every projected {a.season} game"
    L = summary(df, scores, title)
    if a.league and a.week != "all":
        L += league(m, a.season, int(a.week))
    txt = "\n".join(L) + "\n"
    (REV / f"{tag}_grade.md").write_text(txt)
    print(txt)
    print(f"saved -> reviews/{tag}_grades.csv, reviews/{tag}_grade.md, reviews/grades_log.csv ({len(log)} rows)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", default="all", help="week number or 'all'")
    ap.add_argument("--season", type=int, default=nfl.CURRENT_SEASON)
    ap.add_argument("--simcast", action="store_true", help="attach actuals + scorecard to simcast/games/*.json")
    ap.add_argument("--league", action="store_true", help="also grade the live model on every game of the week")
    sys.exit(main(ap.parse_args()))
