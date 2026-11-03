"""Pick the single most typical simulated game out of the 25,000.

"Most typical" = the simulation whose numbers sit closest to the middle on every stat at once.
For each stat, every simulation gets a percentile (0 to 1, ties share the middle rank); the distance
from the median is (percentile - 0.5)^2; the typical game has the smallest sum across all stats.

The score and the player stats come from two separate simulations in this model (the score is
anchored to the market spread and total; player stats come from the player simulation), so each
gets its own most typical pick. Nothing here changes a number: it only chooses an index.
"""
from __future__ import annotations

import numpy as np

PLAYER_STATS = ("targets", "rec", "rec_yds", "rush_att", "rush_yds")
QB_STATS = ("pass_att", "pass_cmp", "pass_yds", "pass_td", "int")


def midrank_pct(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, float)
    order = np.sort(v)
    lo = np.searchsorted(order, v, side="left")
    hi = np.searchsorted(order, v, side="right")
    return (lo + hi) / 2 / len(v)


def typical_players(run: dict) -> tuple[int, list[str]]:
    """Index of the most typical player simulation, and the stats that were scored."""
    sim, saved = run["sim"]["players"], run["proj"]["players"]
    used, dist = [], None
    for name, pl in saved.items():
        s = sim[pl["pid"]]
        for st in pl["stats"]:
            if st not in PLAYER_STATS + QB_STATS or st not in s:
                continue
            d = (midrank_pct(s[st]) - 0.5) ** 2
            dist = d if dist is None else dist + d
            used.append(f"{name}:{st}")
    return int(np.argmin(dist)), used


def typical_score(run: dict) -> int:
    gs = run["score"]
    h, a = np.asarray(gs["home"]), np.asarray(gs["away"])
    d = (midrank_pct(h) - 0.5) ** 2 + (midrank_pct(a) - 0.5) ** 2
    best = d.min()
    cand = np.flatnonzero(np.isclose(d, best))
    # ties: the exact score that came up most often, then the first index
    pairs = [(int(h[i]), int(a[i])) for i in cand]
    counts = {p: int(((h == p[0]) & (a == p[1])).sum()) for p in set(pairs)}
    top = max(counts, key=lambda p: (counts[p], -pairs.index(p)))
    return int(cand[pairs.index(top)])


# ---------------- scoring plays that add up to a final score ----------------
# (points, label, rarity cost). A touchdown is 6 plus the try: kick good (+1), two-point good (+2),
# or try failed (+0). Lower total cost = more ordinary way to reach the score.
_SCORE_PIECES = [(7, "TD", 0.0), (3, "FG", 0.0), (8, "TD+2", 1.0), (6, "TD-try", 1.5), (2, "SAF", 3.0)]
# NFL teams average about 2.4 TDs and 1.7 FGs a game, so a 5th or 6th field goal is rarer than a two-point try
_EXTRA_FG = (0.0, 0.0, 0.0, 0.6, 1.2, 2.5, 4.0, 6.0, 8.0, 10.0)


def decompose(points: int, max_items: int = 9) -> list[tuple[float, list[str]]]:
    """Every way to build `points` from scoring plays, cheapest first: [(cost, ['TD','FG',...]), ...]."""
    out = []

    def go(rem, start, items, cost):
        if rem == 0:
            fg = items.count("FG")
            out.append((cost + 0.15 * len(items) + sum(_EXTRA_FG[:fg + 1]), list(items)))
            return
        if len(items) >= max_items:
            return
        for k in range(start, len(_SCORE_PIECES)):
            pts, lab, c = _SCORE_PIECES[k]
            if pts <= rem:
                items.append(lab)
                go(rem - pts, k, items, cost + c)
                items.pop()

    go(int(points), 0, [], 0.0)
    return sorted(out, key=lambda x: x[0])


def n_td(items: list[str]) -> int:
    return sum(1 for x in items if x.startswith("TD"))


def best_decomposition(points: int, pass_td: int) -> list[str] | None:
    """Cheapest way to reach `points` with at least `pass_td` touchdowns (the QB's passing TDs)."""
    for cost, items in decompose(points):
        if n_td(items) >= pass_td and cost <= 3.5:
            return items
    return None


def consistent_mask(run: dict, score_idx: int) -> tuple[np.ndarray, dict]:
    """True where one simulated game's numbers agree with each other and with the chosen final score."""
    sim, info = run["sim"]["players"], run["sim"]["info"]
    n = len(next(iter(sim.values()))["targets"])
    ok = np.ones(n, bool)
    why = {}

    def fail(label, m):
        why[label] = int((~m & ok).sum())
        return ok & m

    teams = {}
    for pid, s in sim.items():
        t = info[pid]["team"]
        teams.setdefault(t, []).append(pid)
        tg, rec = np.asarray(s["targets"]), np.asarray(s["rec"])
        ry, ra, rr = np.rint(s["rec_yds"]), np.asarray(s["rush_att"]), np.rint(s["rush_yds"])
        ok = fail("catches > targets", rec <= tg)
        ok = fail("receiving yards with no catch", (rec > 0) | (ry == 0))
        ok = fail("rushing yards with no carry", (ra > 0) | (rr == 0))
        ok = fail("receiving yards per catch out of range", (rec == 0) | ((ry >= -3 * rec) & (ry <= 75 * rec)))
        ok = fail("rushing yards per carry out of range", (ra == 0) | ((rr >= -6 * ra) & (rr <= 70 * ra)))
    gs = run["score"]
    pts = {run["home"]: int(gs["home"][score_idx]), run["away"]: int(gs["away"][score_idx])}
    for t, pids in teams.items():
        qb = [p for p in pids if "pass_yds" in sim[p]]
        if not qb:
            continue
        q = sim[qb[0]]
        rec = sum(np.asarray(sim[p]["rec"]) for p in pids)
        tg = sum(np.asarray(sim[p]["targets"]) for p in pids)
        ry = sum(np.rint(sim[p]["rec_yds"]) for p in pids)
        o_cmp = np.asarray(q["pass_cmp"]) - rec
        o_yds = np.rint(q["pass_yds"]) - ry
        ok = fail(f"{t}: QB completions below receivers' catches", o_cmp >= 0)
        ok = fail(f"{t}: QB attempts below targets", np.asarray(q["pass_att"]) - tg >= np.maximum(o_cmp, 0))
        ok = fail(f"{t}: other receivers' yards don't fit", np.where(o_cmp == 0, np.abs(o_yds) <= 3,
                                                                   (o_yds >= -2 * o_cmp) & (o_yds <= 35 * o_cmp)))
        ok = fail(f"{t}: interceptions above incompletions", np.asarray(q["int"]) <= np.asarray(q["pass_att"]) - np.asarray(q["pass_cmp"]))
        max_td = max((n_td(it) for c, it in decompose(pts[t]) if c <= 3.5), default=0)
        ok = fail(f"{t}: passing TDs above TDs the score allows", np.asarray(q["pass_td"]) <= max_td)
    return ok, why


def typical_consistent(run: dict) -> dict:
    j = typical_score(run)
    ok, why = consistent_mask(run, j)
    sim, saved = run["sim"]["players"], run["proj"]["players"]
    dist = None
    for name, pl in saved.items():
        s = sim[pl["pid"]]
        for st in pl["stats"]:
            if st in PLAYER_STATS + QB_STATS and st in s:
                d = (midrank_pct(s[st]) - 0.5) ** 2
                dist = d if dist is None else dist + d
    n_stats = sum(1 for pl in saved.values() for st in pl["stats"] if st in PLAYER_STATS + QB_STATS and st in sim[pl["pid"]])
    d_ok = np.where(ok, dist, np.inf)
    i = int(np.argmin(d_ok))
    return {"player_idx": i, "score_idx": j, "n_consistent": int(ok.sum()), "n": int(len(ok)), "rejected_by": why,
            "distance": float(dist[i]), "distance_unfiltered_best": float(dist.min()),
            "distance_pct": float((dist <= dist[i]).mean()), "rank": int((dist < dist[i]).sum()) + 1,
            "stats_scored": n_stats}
