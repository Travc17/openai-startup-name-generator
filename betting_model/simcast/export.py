"""Export the most typical simulated game as a play by play JSON for the SimCast viewer.

    python simcast/export.py projections/2026_wk09_JAX_at_BAL.json [--out simcast/games/...json]

Steps: rerun the exact 25,000 games behind the projections file (and prove it matches), pick the most
typical internally consistent game, lay its box score out as plays (sequence.py), then check that
replaying every play gives back the box score exactly. Fails loudly if any total is off.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from rerun import check, rerun  # noqa: E402
from sequence import CATCH, DUR, INC, INT, RUN, THROW, build_touches, int_split, solve  # noqa: E402
from typical import best_decomposition, typical_consistent  # noqa: E402

COLORS = {  # primary, secondary (team colors, no logos)
    "ARI": ("#97233F", "#FFB612"), "ATL": ("#A71930", "#000000"), "BAL": ("#241773", "#9E7C0C"),
    "BUF": ("#00338D", "#C60C30"), "CAR": ("#0085CA", "#101820"), "CHI": ("#0B162A", "#C83803"),
    "CIN": ("#FB4F14", "#000000"), "CLE": ("#311D00", "#FF3C00"), "DAL": ("#003594", "#869397"),
    "DEN": ("#FB4F14", "#002244"), "DET": ("#0076B6", "#B0B7BC"), "GB": ("#203731", "#FFB612"),
    "HOU": ("#03202F", "#A71930"), "IND": ("#002C5F", "#A2AAAD"), "JAX": ("#006778", "#D7A22A"),
    "KC": ("#E31837", "#FFB81C"), "LV": ("#000000", "#A5ACAF"), "LAC": ("#0080C6", "#FFC20E"),
    "LA": ("#003594", "#FFA300"), "MIA": ("#008E97", "#FC4C02"), "MIN": ("#4F2683", "#FFC62F"),
    "NE": ("#002244", "#C60C30"), "NO": ("#101820", "#D3BC8D"), "NYG": ("#0B2265", "#A71930"),
    "NYJ": ("#125740", "#FFFFFF"), "PHI": ("#004C54", "#A5ACAF"), "PIT": ("#101820", "#FFB612"),
    "SF": ("#AA0000", "#B3995D"), "SEA": ("#002244", "#69BE28"), "TB": ("#D50A0A", "#34302B"),
    "TEN": ("#0C2340", "#4B92DB"), "WAS": ("#5A1414", "#FFB612"),
}
RUN_DIR = ["left end", "left tackle", "left guard", "up the middle", "up the middle", "right guard",
           "right tackle", "right end"]
SIDES = ["left", "middle", "right"]


def short(name: str) -> str:
    parts = name.split()
    if len(parts) < 2:
        return name
    return f"{parts[0][0]}. {' '.join(parts[1:])}"


def spot_text(pos: int, off: str, de: str) -> str:
    if pos == 50:
        return "50"
    return f"{off} {pos}" if pos < 50 else f"{de} {100 - pos}"


def r1(x) -> int:
    return int(np.rint(float(x)))


def other_receivers(run: dict, team: str, listed: set[str], n_tg: int, n_rec: int, yds: int,
                    rng: np.random.Generator) -> list[dict]:
    """Split the 'everyone else' targets across the team's real other receivers from its last games
    (that is the pool the model resamples them from). Marked not individually projected."""
    if n_tg <= 0:
        return []
    model, key = run["model"], run["key"]
    t = model.t
    recent = t[(t.posteam == team) & (t.key < key)]
    keys = sorted(recent.key.unique())
    last2 = set(recent[recent.key.isin(keys[-2:])].receiver_player_id)
    pool = recent[recent.key.isin(keys[-6:]) & ~recent.receiver_player_id.isin(listed)
                  & recent.receiver_player_id.isin(last2)]
    cnt = pool.receiver_player_id.value_counts().head(3)
    if cnt.empty:
        names, w = [None], np.array([1.0])
    else:
        names, w = list(cnt.index), cnt.to_numpy(float) / cnt.sum()
    tg = rng.multinomial(n_tg, w)
    rec = np.zeros(len(names), int)
    for _ in range(n_rec):   # catches only where there are targets left
        room = tg - rec
        j = int(rng.choice(np.flatnonzero(room > 0), p=room[room > 0] / room[room > 0].sum()))
        rec[j] += 1
    yd = int_split(rec / max(rec.sum(), 1) * yds, yds) if rec.sum() else [0] * len(names)
    out = []
    for pid, a, b, c in zip(names, tg, rec, yd):
        if a == 0:
            continue
        nm = run["names"].get(pid) if pid in run["names"] else None
        if nm is None:
            import nfl
            nm = nfl.name_of(pid) if pid else f"Other {team} receivers"   # sim volume no modeled player took
        pos = run["model"].pos.get(pid, "WR") if pid else "WR"
        out.append({"pid": pid or f"{team}-other", "name": nm, "pos": pos, "targets": int(a), "rec": int(b),
                    "rec_yds": int(c), "rush_att": 0, "rush_yds": 0, "projected": False})
        if out[-1]["pos"] not in ("WR", "TE", "RB", "FB"):
            out[-1]["pos"] = "WR"   # two-way players (e.g. a CB who also plays receiver) listed by their offensive role
    return out


def team_box(run: dict, i: int, team: str, rng: np.random.Generator) -> dict:
    sim, info, names = run["sim"]["players"], run["sim"]["info"], run["names"]
    pids = [p for p in sim if info[p]["team"] == team]
    qb_pid = next(p for p in pids if "pass_yds" in sim[p])
    q = sim[qb_pid]
    players = []
    for p in pids:
        if p == qb_pid:
            continue
        s = sim[p]
        row = {"pid": p, "name": names[p], "pos": info[p].get("pos", "WR"), "targets": r1(s["targets"][i]),
               "rec": r1(s["rec"][i]), "rec_yds": r1(s["rec_yds"][i]), "rush_att": r1(s["rush_att"][i]),
               "rush_yds": r1(s["rush_yds"][i]), "projected": True}
        players.append(row)
    qb = {"pid": qb_pid, "name": names[qb_pid], "att": r1(q["pass_att"][i]), "cmp": r1(q["pass_cmp"][i]),
          "yds": r1(q["pass_yds"][i]), "td": r1(q["pass_td"][i]), "int": r1(q["int"][i]),
          "rush_att": r1(q["rush_att"][i]), "rush_yds": r1(q["rush_yds"][i])}
    o_cmp = qb["cmp"] - sum(p["rec"] for p in players)
    o_yds = qb["yds"] - sum(p["rec_yds"] for p in players)
    room = qb["att"] - sum(p["targets"] for p in players)
    o_tg = min(room, max(o_cmp, int(round(o_cmp / 0.68)))) if o_cmp > 0 else 0
    if o_cmp == 0:
        qb["yds_model"] = qb["yds"]
        qb["yds"] -= o_yds   # at most 3 yards, rounding between separately calibrated stats
        o_yds = 0
    others = other_receivers(run, team, set(pids), o_tg, o_cmp, o_yds, rng)
    return {"abbr": team, "qb": qb, "players": players, "others": others}


def build_events(lay, slots, teams, boxes, tries, names, receive_first):
    away, home = teams
    opp = {away: home, home: away}
    score = {away: 0, home: 0}
    ev = []
    rng = random.Random(7)
    pos_of = {}
    for t in teams:
        pos_of[boxes[t]["qb"]["pid"]] = "QB"
        for p in boxes[t]["players"] + boxes[t]["others"]:
            pos_of[p["pid"]] = p["pos"]
    qb_of = {t: boxes[t]["qb"]["pid"] for t in teams}

    cur = {"drive": 0}

    def add(**k):
        k.setdefault("box", [])
        k["score"] = dict(score)
        k["drive"] = cur["drive"]
        ev.append(k)

    def x_abs(team, pos):   # field position from the away team's goal line (away attacks right)
        return pos if team == away else 100 - pos

    try_i = {t: 0 for t in teams}
    for n, s in enumerate(slots):
        cur["drive"] = n
        t, d = s["team"], opp[s["team"]]
        nxt = slots[n + 1] if n + 1 < len(slots) else None
        prev = slots[n - 1] if n else None
        if s["first"] or (prev and prev["outcome"] in ("TD", "FG", "SAFETY")):
            free = prev is not None and prev["outcome"] == "SAFETY" and not s["first"]
            how = "Free kick" if free else "Kickoff"
            txt = (f"{d} {how.lower()}, touchback. {t} ball at the {spot_text(s['S'], t, d)}."
                   if s["S"] == 35 and not free else f"{d} {how.lower()} returned to the {spot_text(s['S'], t, d)}.")
            add(type="kickoff", half=s["half"], off=t, text=txt, x0=x_abs(t, 100 - 35 if not free else 80), x1=x_abs(t, s["S"]))
        for j, pid in enumerate(s["plays"]):
            down, togo, pos = s["rows"][j]
            g = lay.y[pid]
            kd = lay.kind[pid]
            who = lay.pid[pid]
            last = j == len(s["plays"]) - 1
            td = last and s["outcome"] == "TD"
            qbn = short(names[qb_of[t]])
            box = []
            if kd == RUN:
                ppos = pos_of.get(who, "RB")
                if ppos == "QB":
                    verb = f"scrambles {rng.choice(['left', 'right', 'up the middle'])}"
                elif ppos in ("WR", "TE"):
                    verb = f"jet sweep {rng.choice(['left', 'right'])}"
                else:
                    verb = f"rush {rng.choice(RUN_DIR)}"
                yd = f"for {g} yard{'s' if abs(g) != 1 else ''}" if g else "for no gain"
                txt = f"{short(names[who])} {verb} {yd}"
                box = [[who, "rush_att", 1], [who, "rush_yds", g]] + ([[who, "rush_td", 1]] if td else [])
            elif kd == CATCH:
                depth = "deep" if g >= 18 else "short"
                txt = f"{qbn} pass {depth} {rng.choice(SIDES)} to {short(names[who])} for {g} yard{'s' if abs(g) != 1 else ''}"
                box = [[qb_of[t], "att", 1], [qb_of[t], "cmp", 1], [qb_of[t], "pass_yds", g],
                       [who, "targets", 1], [who, "rec", 1], [who, "rec_yds", g]]
                if td:
                    box += [[qb_of[t], "pass_td", 1], [who, "rec_td", 1]]
            elif kd == INC:
                txt = f"{qbn} pass incomplete {rng.choice(['short', 'short', 'deep'])} {rng.choice(SIDES)} intended for {short(names[who])}"
                box = [[qb_of[t], "att", 1], [who, "targets", 1]]
            elif kd == THROW:
                txt = f"{qbn} pass incomplete, thrown away"
                box = [[qb_of[t], "att", 1]]
            else:   # interception
                S2 = nxt["S"] if nxt and not nxt["first"] else None
                ret = f" {d} ball at the {spot_text(S2, d, t)}." if S2 else ""
                txt = f"{qbn} pass intended for {short(names[who])} INTERCEPTED by {d}.{ret}"
                box = [[qb_of[t], "att", 1], [qb_of[t], "int", 1], [who, "targets", 1]]
            if td:
                score[t] += 6
                txt += ". TOUCHDOWN"
            elif kd in (RUN, CATCH):
                newpos = pos + g
                if g >= togo:
                    txt += ", FIRST DOWN" if newpos < 100 else ""
            add(type=kd, half=s["half"], off=t, down=down, togo=togo, goal=pos + togo >= 100, spot=pos,
                fd=bool(kd in (RUN, CATCH) and g >= togo), who=who,
                spotText=spot_text(pos, t, d), yards=g, td=td, text=txt + ("" if txt.endswith(".") else "."), box=box,
                x0=x_abs(t, pos), x1=x_abs(t, min(pos + g, 100)) if kd in (RUN, CATCH) else x_abs(t, pos))
        oc, E = s["outcome"], s["E"]
        if oc == "TD":
            kind = tries[t][try_i[t]] if try_i[t] < len(tries[t]) else "xp"
            try_i[t] += 1
            if kind == "xp":
                score[t] += 1
                add(type="xp", half=s["half"], off=t, text="Extra point is GOOD.", x0=x_abs(t, 85), x1=x_abs(t, 100))
            elif kind == "two":
                score[t] += 2
                add(type="two", half=s["half"], off=t, text="Two-point try is GOOD.", x0=x_abs(t, 98), x1=x_abs(t, 100))
            else:
                add(type="xp", half=s["half"], off=t, text="Extra point is NO GOOD.", x0=x_abs(t, 85), x1=x_abs(t, 85))
        elif oc == "FG":
            dist = 100 - E + 17
            score[t] += 3
            add(type="fg", half=s["half"], off=t, text=f"{dist}-yard field goal is GOOD.", spot=E,
                spotText=spot_text(E, t, d), x0=x_abs(t, E - 7), x1=x_abs(t, 100))
        elif oc == "PUNT":
            if nxt and not nxt["first"]:
                land = 100 - nxt["S"]
                net = land - E
                txt = (f"{t} punts, touchback. {d} ball at the {spot_text(nxt['S'], d, t)}."
                       if nxt["S"] == 20 and E >= 45 else f"{t} punts {net} yards. {d} ball at the {spot_text(nxt['S'], d, t)}.")
            else:
                land, txt = min(E + 42, 95), f"{t} punts."
            add(type="punt", half=s["half"], off=t, text=txt, spot=E, spotText=spot_text(E, t, d),
                x0=x_abs(t, E), x1=x_abs(t, land))
        elif oc == "TOD":
            add(type="tod", half=s["half"], off=t, text=f"Stopped on 4th down. Turnover on downs, {d} takes over.",
                x0=x_abs(t, E), x1=x_abs(t, E))
        elif oc == "SAFETY":
            score[d] += 2
            add(type="safety", half=s["half"], off=t, text=f"Holding in the end zone. SAFETY, 2 points {d}.",
                x0=x_abs(t, E), x1=x_abs(t, 0))
        if s["last"]:
            add(type="end", half=s["half"], off=t, text="End of 1st half." if s["half"] == 1 else "FINAL.",
                x0=x_abs(t, E if oc not in ("TD",) else 100), x1=x_abs(t, E if oc not in ("TD",) else 100))
    return ev


def add_clock(ev: list[dict]) -> None:
    """Spread 30:00 of game clock over each half in proportion to typical play lengths."""
    for half in (1, 2):
        ids = [i for i, e in enumerate(ev) if e["half"] == half]
        dur = np.array([DUR.get(ev[i]["type"], 6.0) for i in ids])
        el = np.concatenate([[0], np.cumsum(dur)])[:-1] * (1800 / dur.sum())
        for i, t in zip(ids, el):
            q2 = t >= 900
            left = 900 - (t - 900 if q2 else t)
            left = int(round(left))
            ev[i]["q"] = (1 if half == 1 else 3) + int(q2)
            ev[i]["clock"] = f"{left // 60}:{left % 60:02d}"
            ev[i]["el"] = round(float(t + (half - 1) * 1800), 1)
        last = ids[-1]
        ev[last]["q"] = 2 if half == 1 else 4
        ev[last]["clock"] = "0:00"


def replay_box(ev: list[dict]) -> dict:
    tot = {}
    for e in ev:
        for pid, st, v in e["box"]:
            tot.setdefault(pid, {}).setdefault(st, 0)
            tot[pid][st] += v
    return tot


def verify(ev, boxes, final) -> list[str]:
    got, bad = replay_box(ev), []
    for t, b in boxes.items():
        q = b["qb"]
        g = got.get(q["pid"], {})
        for st, want in (("att", q["att"]), ("cmp", q["cmp"]), ("pass_yds", q["yds"]), ("pass_td", q["td"]),
                         ("int", q["int"]), ("rush_att", q["rush_att"]), ("rush_yds", q["rush_yds"])):
            if g.get(st, 0) != want:
                bad.append(f"{t} QB {st}: replay {g.get(st, 0)} vs box {want}")
        for p in b["players"] + b["others"]:
            g = got.get(p["pid"], {})
            for st in ("targets", "rec", "rec_yds", "rush_att", "rush_yds"):
                if g.get(st, 0) != p[st]:
                    bad.append(f"{p['name']} {st}: replay {g.get(st, 0)} vs box {p[st]}")
    if ev[-1]["score"] != final:
        bad.append(f"final score {ev[-1]['score']} vs {final}")
    return bad


def export(proj_path: str, seed: int | None = None) -> dict:
    run = rerun(proj_path)
    bad = check(run)
    if bad:
        sys.exit("Rerun does not match the saved projections:\n" + "\n".join(bad))
    pick = typical_consistent(run)
    i, j = pick["player_idx"], pick["score_idx"]
    away, home = run["away"], run["home"]
    teams = [away, home]
    final = {away: int(run["score"]["away"][j]), home: int(run["score"]["home"][j])}
    seed = seed if seed is not None else run["key"] * 7 + sum(map(ord, away + home))
    rng = np.random.default_rng(seed)
    boxes = {t: team_box(run, i, t, rng) for t in teams}

    outcomes, tries, ptd = {}, {}, {}
    plan = {}
    for t in teams:
        plan[t] = best_decomposition(final[t], boxes[t]["qb"]["td"])
        if plan[t] is None:
            sys.exit(f"No sensible way to score {final[t]} with {boxes[t]['qb']['td']} passing TDs for {t}.")
    touches = []
    for t in teams:
        touches += build_touches(boxes[t], rng)
    n_plays = {t: sum(1 for x in touches if x["team"] == t) for t in teams}
    n_poss = int(np.clip(round(sum(n_plays.values()) / 2 / 5.4), 9, 13))
    for t in teams:
        o = teams[1] if t == teams[0] else teams[0]
        oc = ["TD" if x.startswith("TD") else "FG" for x in plan[t] if x != "SAF"]
        oc += ["SAFETY"] * plan[o].count("SAF")
        oc += ["INT"] * boxes[t]["qb"]["int"]
        oc += ["PUNT"] * max(0, n_poss - len(oc))
        outcomes[t] = oc
        tr = [{"TD": "xp", "TD+2": "two", "TD-try": "miss"}[x] for x in plan[t] if x.startswith("TD")]
        random.Random(seed).shuffle(tr)
        tries[t] = tr
        ptd[t] = boxes[t]["qb"]["td"]
    n_poss = max(len(v) for v in outcomes.values())
    for t in teams:
        outcomes[t] += ["PUNT"] * (n_poss - len(outcomes[t]))
    receive_first = teams[seed % 2]
    cost, hard, lay = solve(teams, touches, outcomes, ptd, receive_first, seed)
    if hard:
        sys.exit(f"Could not lay out a legal game (cost {cost:.1f}, {hard} problems). Try another --seed.")
    _, _, slots = lay.evaluate(detail=True)
    names = dict(run["names"])
    for t in teams:
        for p in boxes[t]["others"]:
            names[p["pid"]] = p["name"]
    ev = build_events(lay, slots, teams, boxes, tries, names, receive_first)
    add_clock(ev)
    bad = verify(ev, boxes, final)
    if bad:
        sys.exit("Play by play does not add back up to the box score:\n" + "\n".join(bad))

    meta = run["proj"]["meta"]
    fav, spread, total = meta.get("fav"), meta.get("spread"), meta.get("total")
    gs = run["score"]
    same = int(((gs["home"] == gs["home"][j]) & (gs["away"] == gs["away"][j])).sum())
    return {
        "game": f"{away} at {home}", "away": away, "home": home, "key": run["key"],
        "season": run["key"] // 100, "week": run["key"] % 100,
        "colors": {t: COLORS.get(t, ("#333333", "#999999")) for t in teams},
        "final": final, "plan": plan, "tries": tries,
        "line": {"fav": fav, "spread": spread, "total": total},
        "qbs": meta.get("qbs"), "made_utc": run["proj"]["made_utc"],
        "typical": {"sims": pick["n"], "player_sim": i + 1, "score_sim": j + 1, "consistent": pick["n_consistent"],
                    "score_count": same, "stats_scored": pick["stats_scored"], "rank": pick["rank"]},
        "box": boxes, "events": ev, "seed": seed, "cost": round(cost, 2), "n_poss": n_poss,
        "drives": [{"team": s["team"], "half": s["half"], "outcome": s["outcome"], "start": s["S"], "end": s["E"],
                    "plays": len(s["plays"])} for s in slots],
        "medians": {"away": float(np.median(gs["away"])), "home": float(np.median(gs["home"]))},
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("proj")
    ap.add_argument("--out")
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    g = export(a.proj, a.seed)
    out = a.out or str(HERE / "games" / (Path(a.proj).stem + ".json"))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(g, separators=(",", ":"), default=int))
    print(f"{g['game']}: final {g['away']} {g['final'][g['away']]}, {g['home']} {g['final'][g['home']]} | "
          f"{len(g['events'])} events | layout cost {g['cost']} | wrote {out}")
