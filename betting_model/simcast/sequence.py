"""Turn one simulated game's box score into a play by play broadcast.

What comes from the model (never changed here): every player's targets, catches, receiving yards,
carries, rushing yards; each QB's attempts, completions, yards, passing TDs, interceptions; the final
score. What this file adds, because the model does not simulate it: the order of plays, how a
player's yards split across his touches, drives, downs, field position, kicks, and the clock.

Method: start from a random layout of every touch into drives, then search (simulated annealing)
for a layout where every drive is legal football: a punt comes on 4th down, a field goal is kicked
from range, a touchdown play ends exactly on the goal line, an interception ends its drive, field
position chains from one possession to the next, and the box score totals are untouched. A play's
yards can only move to another touch by the same player of the same kind, so totals never drift.
"""
from __future__ import annotations

import math
import random

import numpy as np

RUN, CATCH, INC, INT, THROW = "run", "catch", "inc", "int", "throw"
YARD_BOUNDS = {RUN: (-5, 75), CATCH: (-3, 85)}
DUR = {RUN: 37.0, CATCH: 33.0, INC: 6.0, THROW: 6.0, INT: 9.0, "kickoff": 6.0, "punt": 9.0, "fg": 5.0,
       "xp": 0.0, "two": 0.0, "safety": 6.0, "tod": 0.0, "end": 0.0}
SIZE_PRIOR = {"TD": 8.0, "FG": 7.0, "PUNT": 4.2, "INT": 5.0, "SAFETY": 3.0}


# ---------------- touches ----------------
def int_split(vals: np.ndarray, total: int) -> list[int]:
    """Whole numbers that add up to `total`, as close to `vals` (which already sum to total) as possible."""
    fl = np.floor(vals).astype(int)
    rem = int(total - fl.sum())
    order = np.argsort(-(vals - fl))
    fl[order[:rem]] += 1
    return [int(x) for x in fl]


def split_yards(rng: np.random.Generator, total: int, n: int, kind: str) -> list[int]:
    """n plays that add up to `total` yards, shaped like real catches (skewed) or runs (mostly short)."""
    if n == 0:
        return []
    if n == 1:
        return [int(total)]
    m = total / n
    if kind == CATCH and total >= 3 * n:
        w = rng.gamma(1.6, 1.0, n)
        vals = total * w / w.sum()
    else:
        base = rng.normal(0, 3.0, n) + rng.exponential(2.0, n)
        vals = m + base - base.mean()
    out = int_split(vals, int(total))
    lo, hi = YARD_BOUNDS[kind]
    for _ in range(200):   # pull anything out of bounds back in, keeping the sum
        bad = [i for i, v in enumerate(out) if v < lo or v > hi]
        if not bad:
            break
        i = bad[0]
        j = int(rng.integers(n))
        if i == j:
            continue
        step = 1 if out[i] < lo else -1
        out[i] += step
        out[j] -= step
    return out


def build_touches(team: dict, rng: np.random.Generator) -> list[dict]:
    """Every offensive play for one team, from its box score.
    team = {"abbr", "qb": {pid, name, att, cmp, yds, td, int, rush_att, rush_yds},
            "players": [{pid, name, pos, targets, rec, rec_yds, rush_att, rush_yds}], "others": [...same...]}"""
    t = []
    qb = team["qb"]
    for p in team["players"] + team["others"]:
        for y in split_yards(rng, p["rec_yds"], p["rec"], CATCH):
            t.append({"kind": CATCH, "pid": p["pid"], "yards": y})
        for _ in range(p["targets"] - p["rec"]):
            t.append({"kind": INC, "pid": p["pid"], "yards": 0})
        for y in split_yards(rng, p["rush_yds"], p["rush_att"], RUN):
            t.append({"kind": RUN, "pid": p["pid"], "yards": y})
    for y in split_yards(rng, qb["rush_yds"], qb["rush_att"], RUN):
        t.append({"kind": RUN, "pid": qb["pid"], "yards": y})
    targets = sum(p["targets"] for p in team["players"] + team["others"])
    for _ in range(qb["att"] - targets):
        t.append({"kind": THROW, "pid": None, "yards": 0})
    # interceptions: turn targeted incompletions into picks (the intended receiver keeps his target)
    incs = [i for i, x in enumerate(t) if x["kind"] == INC]
    for i in rng.choice(incs, size=min(qb["int"], len(incs)), replace=False) if incs else []:
        t[int(i)]["kind"] = INT
    for x in t:
        x["team"] = team["abbr"]
    return t


# ---------------- the search ----------------
class Layout:
    def __init__(self, teams: list[str], touches: list[dict], outcomes: dict[str, list[str]],
                 pass_td: dict[str, int], receive_first: str, seed: int):
        self.teams = teams
        self.T = touches
        self.kind = [x["kind"] for x in touches]
        self.pid = [x["pid"] for x in touches]
        self.team_of = [x["team"] for x in touches]
        self.y = [x["yards"] for x in touches]
        self.want_ptd = pass_td
        self.rng = random.Random(seed)
        other = {teams[0]: teams[1], teams[1]: teams[0]}
        # possession order: alternate within each half; the other team receives the second half
        n_team = {t: len(outcomes[t]) for t in teams}
        h1 = (n_team[receive_first] + n_team[other[receive_first]]) // 2
        first_half_counts = {receive_first: (h1 + 1) // 2, other[receive_first]: h1 // 2}
        self.order = []
        cnt = {t: 0 for t in teams}
        for half, starter in ((1, receive_first), (2, other[receive_first])):
            seq = []
            t = starter
            while True:
                need_more = (cnt[t] < first_half_counts[t]) if half == 1 else (cnt[t] < n_team[t])
                if not need_more:
                    if half == 1 and cnt[other[t]] < first_half_counts[other[t]]:
                        t = other[t]
                        continue
                    if half == 2 and cnt[other[t]] < n_team[other[t]]:
                        t = other[t]
                        continue
                    break
                seq.append((t, cnt[t], half))
                cnt[t] += 1
                t = other[t]
            for i, (t_, k, h) in enumerate(seq):
                self.order.append({"team": t_, "k": k, "half": h, "first": i == 0, "last": i == len(seq) - 1})
        self.outc = {t: list(outcomes[t]) for t in teams}
        # fixed per possession, so the search sees a stable target: touchback or a return, punt length, pick return
        self.u = [(self.rng.random(), self.rng.random()) for _ in self.order]
        self.rng.shuffle(self.outc[teams[0]])
        self.rng.shuffle(self.outc[teams[1]])
        self._initial_layout()

    def _initial_layout(self):
        self.drives = {}
        for t in self.teams:
            ids = [i for i in range(len(self.T)) if self.team_of[i] == t]
            ints = [i for i in ids if self.kind[i] == INT]
            rest = [i for i in ids if self.kind[i] != INT]
            self.rng.shuffle(rest)
            oc = self.outc[t]
            w = np.array([SIZE_PRIOR[o] for o in oc])
            n_free = len(rest)
            sizes = int_split(w / w.sum() * n_free, n_free)
            sizes = [max(1, s) for s in sizes]
            while sum(sizes) > n_free:
                j = int(np.argmax(sizes))
                sizes[j] -= 1
            drives, pos = [], 0
            for o, s in zip(oc, sizes):
                d = rest[pos:pos + s]
                pos += s
                if o == "INT":
                    d = d + [ints.pop()]
                drives.append(d)
            drives[-1].extend(rest[pos:])
            self.drives[t] = drives

    # ----- scoring a layout -----
    def evaluate(self, detail: bool = False):
        cost, hard = 0.0, 0
        why = []
        prev_evt, prev_E = None, None
        ptd = {t: 0 for t in self.teams}
        out = []
        for si, slot in enumerate(self.order):
            u1, u2 = self.u[si]
            t, k = slot["team"], slot["k"]
            plays, oc = self.drives[t][k], self.outc[t][k]
            y = [self.y[i] for i in plays]
            # where can this possession start, given how the last one ended?
            if slot["first"] or prev_evt in ("TD", "FG"):
                lo, hi, pref = 20, 45, (35 if u1 < 0.65 else 24 + int(u2 * 15))
            elif prev_evt == "SAFETY":
                lo, hi, pref = 30, 50, 40
            elif prev_evt == "PUNT":
                lo = max(5, 45 - prev_E)
                hi = max(lo, 70 - prev_E)
                if prev_E >= 45:
                    hi = max(hi, 20)
                pref = min(max(100 - prev_E - (36 + int(u1 * 14)), lo), hi)
            elif prev_evt == "INT":
                lo, hi = max(5, 60 - prev_E), min(90, 120 - prev_E)
                pref = min(max(100 - prev_E - 20 + int(u1 * 25), lo), hi)
            elif prev_evt == "TOD":
                lo = hi = pref = 100 - prev_E
            else:
                lo, hi, pref = 20, 45, 35
            if not plays:
                hard += 1
                why.append('empty drive')
                cost += 200
                prev_evt, prev_E = "PUNT", 30
                continue
            pre = list(np.cumsum(y))
            D = pre[-1]
            dlo = max(1, 1 - min(pre))
            dhi = 99 - (max(pre[:-1]) if len(pre) > 1 else 0)
            if oc == "TD":
                dlo, dhi = max(dlo, 100 - D), min(dhi, 100 - D)
            elif oc == "FG":
                dlo, dhi = max(dlo, 62 - D), min(dhi, 98 - D)
            elif oc == "PUNT":
                dhi = min(dhi, (99 if slot["last"] else 65) - D)
            elif oc == "SAFETY":
                dhi = min(dhi, 8 - D)
            else:
                dhi = min(dhi, 99 - D)
            dhi = min(dhi, 99)
            if dlo > dhi:
                hard += 1
                why.append('drive cannot fit anywhere')
                cost += 100 + 10 * (dlo - dhi)
                S = int(min(max(pref, lo), hi))
            else:
                a, b = max(lo, dlo), min(hi, dhi)
                if a <= b:
                    S = int(min(max(pref, a), b))
                else:
                    S = int(dhi if dhi < lo else dlo)
                    hard += 1
                    why.append('start does not chain from last possession')
                    cost += 100 + 10 * (a - b)
            cost += 0.03 * abs(S - pref)
            # downs
            pos, down, togo, conv4 = S, 1, min(10, 100 - S), 0
            rows = []
            for i, g in enumerate(y):
                last = i == len(y) - 1
                kd = self.kind[plays[i]]
                rows.append((down, togo, pos))
                if kd == INT and not (last and oc == "INT"):
                    hard += 1
                    why.append('interception not last')
                    cost += 100
                if not last and pos + g >= 100:
                    hard += 1
                    why.append('scored before last play')
                    cost += 50
                if down == 4 and not last:
                    conv4 += 1
                pos += g
                if g >= togo:
                    down, togo = 1, min(10, 100 - pos)
                else:
                    down += 1
                    togo -= g
                if down == 5 and not last:
                    hard += 1
                    why.append('failed 4th down mid-drive')
                    cost += 100
            E = pos
            lk = self.kind[plays[-1]]
            evt = oc
            if oc == "TD":
                if lk not in (RUN, CATCH) or E != 100:
                    hard += 1
                    why.append('TD drive does not end on goal line')
                    cost += 100
                if lk == CATCH:
                    ptd[t] += 1
            elif oc == "INT":
                if lk != INT:
                    hard += 1
                    why.append('INT drive without INT')
                    cost += 100
            elif oc == "FG":
                if down == 4:
                    pass
                elif down < 4 and slot["last"]:
                    cost += 1
                else:
                    hard += 1
                    why.append('FG not on 4th down')
                    cost += 60
            elif oc == "PUNT":
                if down == 4:
                    pass
                elif down == 5:
                    evt = "TOD"
                    cost += 3 + 0.4 * max(0, 60 - E)
                elif slot["last"]:
                    evt = "END"
                else:
                    hard += 1
                    why.append('punt not on 4th down')
                    cost += 60
            cost += 4 * conv4 + sum(0.02 * max(0, abs(g) - 30) for g in y)
            for i, g in zip(plays, y):   # real runs rarely lose more than 2; catches rarely lose yards
                if self.kind[i] == RUN and g < -2:
                    cost += 0.25 * (-2 - g)
                elif self.kind[i] == CATCH and g < 0:
                    cost += 0.3 * -g
            for i in plays:
                if self.kind[i] in YARD_BOUNDS:
                    lo_, hi_ = YARD_BOUNDS[self.kind[i]]
                    if not lo_ <= self.y[i] <= hi_:
                        hard += 1
                        why.append('yards out of range')
                        cost += 50
            if detail:
                out.append({**slot, "outcome": evt, "S": S, "E": E, "plays": list(plays), "rows": rows})
            prev_evt, prev_E = evt, E
        for t in self.teams:
            if ptd[t] != self.want_ptd[t]:
                hard += 1
                why.append('passing TD count')
                cost += 60 * abs(ptd[t] - self.want_ptd[t])
        self.why = why
        return (cost, hard, out) if detail else (cost, hard)

    # ----- moves -----
    def _move(self):
        r = self.rng
        t = r.choice(self.teams)
        D = self.drives[t]
        m = r.random()
        if m < 0.30:      # move one touch to another drive
            a, b = r.randrange(len(D)), r.randrange(len(D))
            if a == b or len(D[a]) <= 1:
                return None
            i = r.randrange(len(D[a]))
            if self.kind[D[a][i]] == INT:
                return None
            old = (list(D[a]), list(D[b]))
            x = D[a].pop(i)
            D[b].insert(r.randrange(len(D[b]) + 1), x)
            return lambda: (D.__setitem__(a, old[0]), D.__setitem__(b, old[1]))
        if m < 0.50:      # swap two touches between drives
            a, b = r.randrange(len(D)), r.randrange(len(D))
            if a == b:
                return None
            i, j = r.randrange(len(D[a])), r.randrange(len(D[b]))
            D[a][i], D[b][j] = D[b][j], D[a][i]
            return lambda: self._swap_back(D, a, i, b, j)
        if m < 0.65:      # reorder inside a drive
            a = r.randrange(len(D))
            if len(D[a]) < 2:
                return None
            i, j = r.randrange(len(D[a])), r.randrange(len(D[a]))
            D[a][i], D[a][j] = D[a][j], D[a][i]
            return lambda: self._swap_back(D, a, i, a, j)
        if m < 0.93:      # move yards between two touches by the same player, same kind
            ids = [i for d in D for i in d if self.kind[i] in (RUN, CATCH)]
            if not ids:
                return None
            p = r.choice(ids)
            mates = [i for i in ids if i != p and self.pid[i] == self.pid[p] and self.kind[i] == self.kind[p]]
            if not mates:
                return None
            q = r.choice(mates)
            k = r.choice((1, 1, 2, 3, 5, 8, 13))
            yp, yq = self.y[p], self.y[q]
            lo_, hi_ = YARD_BOUNDS[self.kind[p]]
            if not (lo_ <= yp - k <= hi_ and lo_ <= yq + k <= hi_):
                return None
            self.y[p] -= k
            self.y[q] += k
            return lambda: (self.y.__setitem__(p, yp), self.y.__setitem__(q, yq))
        a, b = r.randrange(len(D)), r.randrange(len(D))   # swap two drives' outcomes
        O = self.outc[t]
        if a == b or O[a] == O[b] or "INT" in (O[a], O[b]):
            return None
        O[a], O[b] = O[b], O[a]
        return lambda: self._swap_back(O, a, None, b, None)

    @staticmethod
    def _swap_back(D, a, i, b, j):
        if i is None:
            D[a], D[b] = D[b], D[a]
        else:
            D[a][i], D[b][j] = D[b][j], D[a][i]

    def anneal(self, iters: int = 60000, t0: float = 30.0, t1: float = 0.05):
        cost, hard = self.evaluate()
        best = (cost, hard, self._snapshot())
        for it in range(iters):
            T = t0 * (t1 / t0) ** (it / iters)
            undo = self._move()
            if undo is None:
                continue
            c2, h2 = self.evaluate()
            if c2 <= cost or self.rng.random() < math.exp((cost - c2) / T):
                cost, hard = c2, h2
                if cost < best[0]:
                    best = (cost, hard, self._snapshot())
                    if hard == 0 and cost < 2:
                        break
            else:
                undo()
        self._restore(best[2])
        return best[0], best[1]

    def _snapshot(self):
        return ({t: [list(d) for d in self.drives[t]] for t in self.teams},
                {t: list(self.outc[t]) for t in self.teams}, list(self.y))

    def _restore(self, s):
        self.drives = {t: [list(d) for d in s[0][t]] for t in self.teams}
        self.outc = {t: list(s[1][t]) for t in self.teams}
        self.y = list(s[2])


def solve(teams, touches, outcomes, pass_td, receive_first, seed, tries=12, iters=60000):
    best = None
    for k in range(tries):
        lay = Layout(teams, touches, outcomes, pass_td, receive_first, seed * 1000 + k)
        cost, hard = lay.anneal(iters=iters)
        if best is None or (hard, cost) < (best[1], best[0]):
            best = (cost, hard, lay)
        if hard == 0 and cost < 8:
            break
    return best
