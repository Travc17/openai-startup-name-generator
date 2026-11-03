"""Game report: news, score prediction, game lines, full box score, top singles,
top parlays, best bet. Produces a JSON-able dict and a self-contained HTML page.

Inputs
  news.json : [{"player","team","status","detail","source","url"}]  (gathered from trusted sources)
  board.csv : kind,name,stat,line,price
      prop  , Zay Flowers , rec_yds , 60  , 55    -> Zay Flowers 60+ receiving yards at 55c (Yes)
      spread, JAX         ,         , -8.5, 51    -> JAX -8.5 at 51c
      total , over|under  ,         , 43.5, 50
      ml    , JAX         ,         ,     , 78
      tt    , BAL         ,         , 17.5, 48    -> BAL team total over 17.5
      book  , Zay Flowers , rec_yds , 64.5, -115, -105, DraftKings -> big-book O/U line (+ optional prices)
"""
from __future__ import annotations

import csv
import html
import itertools
import json
from datetime import date

import numpy as np

from . import scores
from .game import STAT_LABEL, american

DISC = 1.0           # combo price assumed = product of legs (observed 0.93-0.99 on 2 tickets: be conservative)
STAT_SHORT = {"rec": "catches", "rec_yds": "rec yds", "rush_yds": "rush yds", "rush_att": "carries",
              "targets": "targets", "rec_rush_yds": "rush+rec yds", "pass_yds": "pass yds", "pass_att": "pass att",
              "pass_cmp": "completions", "pass_td": "pass TDs", "int": "INTs"}


def load_board(path):
    if not path:
        return []
    with open(path) as f:
        return [{k.strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def load_news(path):
    if not path:
        return []
    with open(path) as f:
        return json.load(f)


def _kelly_stake(p, cost, bankroll, min_bet=50, frac=0.25, cap=0.10):
    edge = p - cost
    if edge < 0.02:
        return 0
    if edge < 0.04:
        return min_bet
    b = (1 - cost) / cost
    k = (p * b - (1 - p)) / b
    return int(max(min_bet, min(round(bankroll * cap / 5) * 5, round(bankroll * k * frac / 5) * 5)))


def hit_rate_parlays(usable, fee, min_legs=3, max_legs=6, lo=0.05, hi=0.40, beam=300, n=10):
    """Alt-line parlays ranked by simulated hit rate (Travis: hit rate first, edge second).
    Ticket = product of leg prices (no combo discount), kept between lo and hi.
    Same player only as rushing + receiving (never catches + receiving yards). Beam search on joint hit rate."""
    pool = [l for l in usable if l["p"] >= 0.5 and l.get("price")]
    kind = lambda l: (l["player"], "rush" if l["stat"] in ("rush_yds", "rush_att") else "recv")
    level = [((i,), pool[i]["_hit"], pool[i]["price"]) for i in range(len(pool))]
    found = []
    for size in range(2, max_legs + 1):
        nxt, seen = [], set()
        for idx, hit, price in level:
            used = {kind(pool[i]) for i in idx}
            for j in range(idx[-1] + 1, len(pool)):
                if kind(pool[j]) in used:
                    continue
                key = idx + (j,)
                if key in seen:
                    continue
                seen.add(key)
                h = hit & pool[j]["_hit"]
                nxt.append((key, h, price * pool[j]["price"], float(h.mean())))
        nxt.sort(key=lambda t: -t[3])
        level = [(k, h, pr) for k, h, pr, _ in nxt[:beam]]
        if size >= min_legs:
            found += [(k, p_, pr) for k, _, pr, p_ in nxt if lo <= pr <= hi]
    found.sort(key=lambda t: -t[1])
    out, used_sets, player_sets = [], [], []
    for k, p_, pr in found:
        legs = [pool[i] for i in k]
        labels = [l["label"] for l in legs]
        players = frozenset(l["player"] for l in legs)
        if any(len(set(labels) & u) >= len(labels) - 1 for u in used_sets) or player_sets.count(players) >= 2:
            continue  # keep the list varied: max 2 tickets per player combination
        used_sets.append(set(labels))
        player_sets.append(players)
        out.append({"legs": labels, "legs_data": [[l["pid"], l["stat"], l["x"]] + (["no"] if l["side"] == "no" else []) for l in legs],
                    "p": p_, "ticket": pr, "cost": pr + fee, "edge": p_ - pr - fee, "fair": american(p_)})
        if len(out) == n:
            break
    return out


def build(model, name_of, lookup, roster, home, away, key, n_sims, board, news, bankroll, fee,
          fav=None, spread=None, total=None, model_line=None, blind=(), qbs=None, wind=None):
    margin_home = (spread if fav == home else -spread) if (fav and spread is not None) else None
    sim = model.simulate(home, away, key, roster, n_sims=n_sims, seed=7, exp_margin_a=margin_home, qbs=qbs, wind=wind)
    # blind spots: "Name" excludes every prop for that player; "Name:rec,rec_yds" excludes only those stats
    blind_stats = {}
    for b in blind:
        nm_, _, sts = b.partition(":")
        blind_stats[nm_.strip()] = {x.strip() for x in sts.split(",") if x.strip()} or None

    def is_blind(nm_, stat=None):
        if nm_ not in blind_stats:
            return False
        st_ = blind_stats[nm_]
        return st_ is None or (stat is not None and stat in st_)
    blind_txt = sorted(nm_ if st_ is None else f"{nm_} ({', '.join(STAT_LABEL.get(x, x) for x in sorted(st_))})"
                       for nm_, st_ in blind_stats.items())
    rep = {"home": home, "away": away, "date": date.today().isoformat(), "sims": n_sims, "news": news,
           "bankroll": bankroll, "fee": fee, "blind": blind_txt}

    # ---------- score ----------
    if fav and spread is not None and total is not None:
        g, _ = scores.load_games(sorted({key // 100 - i for i in range(5)}))
        resid = scores.market_residuals(g, key // 100 + 1)
        spread_line = spread if fav == home else -spread
        gs = scores.market_simulate(spread_line, total, resid, n=n_sims)
        M, T, H, A = gs["margin"], gs["total"], gs["home"], gs["away"]
        vals, cnt = np.unique(M, return_counts=True)
        top = sorted(zip(cnt, vals), reverse=True)[:3]
        fm = M if fav == home else -M
        rep["score"] = {
            "fav": fav, "spread": spread, "total": total,
            "home_pts": float(np.median(H)), "away_pts": float(np.median(A)),
            "home_win": float((M > 0).mean()), "away_win": float((M < 0).mean()), "tie": float((M == 0).mean()),
            "common": [{"margin": int(v), "pct": float(c / len(M))} for c, v in top],
            "alt_spreads": [{"line": l, "win": float((fm + l > 0).mean()), "push": float((fm + l == 0).mean())}
                            for l in (-10.5, -7.5, -spread, -3.5, -2.5, 2.5, 3.5, 7.5)],
            "alt_totals": [{"line": total + k, "over": float((T > total + k).mean())} for k in (-7, -3, 0, 3, 7)],
            "team_totals": {home: float(np.median(H)), away: float(np.median(A))},
            "model_line": model_line,
        }
    else:
        gs = None

    # ---------- box score ----------
    box = {home: [], away: []}
    rep["qbs"] = {}
    for pid, s in sim["players"].items():
        if "pass_yds" in s:
            info = sim["info"][pid]
            rep["qbs"][info["team"]] = {"name": name_of(pid), "blind": is_blind(name_of(pid)),
                                        "yds_mult": info.get("qb_yds_mult", 1.0), "cmp_mult": info.get("qb_cmp_mult", 1.0),
                                        "stats": {st: [float(np.percentile(s[st], q)) for q in (10, 25, 50, 75, 90)]
                                                  for st in ("pass_att", "pass_cmp", "pass_yds", "pass_td", "int", "rush_yds")},
                                        "p": {"2+ TD": float((s["pass_td"] >= 2).mean()), "1+ INT": float((s["int"] >= 1).mean())}}
    for p in roster:
        s, info = sim["players"][p.pid], sim["info"][p.pid]
        if s["targets"].mean() < 0.8 and s["rush_att"].mean() < 1.5:
            continue
        row = {"name": name_of(p.pid), "pos": info["pos"], "blind": is_blind(name_of(p.pid)), "stats": {}}
        for st in ("targets", "rec", "rec_yds", "rush_att", "rush_yds"):
            v = s[st]
            if (st in ("targets", "rec", "rec_yds") and s["targets"].mean() >= 0.8) or \
               (st in ("rush_att", "rush_yds") and s["rush_att"].mean() >= 1.5):
                row["stats"][st] = [float(np.percentile(v, q)) for q in (10, 25, 50, 75, 90)]
        box[info["team"]].append(row)
    for t in box:
        box[t].sort(key=lambda r: -(r["stats"].get("rec_yds", [0, 0, 0])[2] + r["stats"].get("rush_yds", [0, 0, 0])[2]))
    rep["box"] = box
    rep["volume"] = {t: {"targets": float(v[0]), "rushes": float(v[1])} for t, v in sim["team_mu"].items()}

    # ---------- price the board ----------
    legs, lines = [], []
    pid_cache = {}
    book = []
    for r in board:
        kind = r["kind"].lower()
        if kind == "book":
            nm = r["name"]
            if nm not in pid_cache:
                try:
                    pid_cache[nm] = lookup(nm)
                except SystemExit:
                    pid_cache[nm] = None   # no history in the data: can't price
                    rep.setdefault("unpriced", []).append(nm)
            pid = pid_cache[nm]
            if pid not in sim["players"]:
                continue
            v = sim["players"][pid][r["stat"]]
            x = float(r["line"])
            po = float((v > x).mean())
            row = {"player": nm, "stat": r["stat"], "line": x, "median": float(np.median(v)), "p_over": po,
                   "src": r.get("book", ""), "blind": is_blind(nm, r["stat"])}
            for side, key_, pp in (("over", "price", po), ("under", "price2", 1 - po)):
                a_ = r.get(key_, "")
                if a_:
                    a_ = float(a_)
                    be = -a_ / (-a_ + 100) if a_ < 0 else 100 / (a_ + 100)
                    row[f"{side}_odds"], row[f"{side}_edge"] = a_, pp - be
            book.append(row)
            continue
        price = float(r["price"]) / 100 if str(r.get("price", "")).strip() else None
        cost = price + fee if price is not None else None
        if kind == "prop":
            nm = r["name"]
            if nm not in pid_cache:
                try:
                    pid_cache[nm] = lookup(nm)
                except SystemExit:
                    pid_cache[nm] = None   # no history in the data: can't price
                    rep.setdefault("unpriced", []).append(nm)
            pid = pid_cache[nm]
            if pid not in sim["players"]:
                continue
            x = float(r["line"])
            hit = sim["players"][pid][r["stat"]] >= x
            if price is not None:
                legs.append({"label": f"{nm} {x:g}+ {STAT_SHORT[r['stat']]}", "player": nm, "pid": pid, "x": x, "stat": r["stat"],
                             "side": "yes", "p": float(hit.mean()), "price": price, "cost": cost, "edge": float(hit.mean() - cost),
                             "blind": is_blind(nm, r["stat"]), "_hit": hit})
            if str(r.get("price2", "")).strip():   # Robinhood "No" price on the same rung: wins if he stays UNDER x
                p2 = float(r["price2"]) / 100
                miss = ~hit
                legs.append({"label": f"{nm} NO {x:g}+ {STAT_SHORT[r['stat']]} (under {x - 0.5:g})", "player": nm, "pid": pid,
                             "x": x, "stat": r["stat"], "side": "no", "p": float(miss.mean()), "price": p2, "cost": p2 + fee,
                             "edge": float(miss.mean() - p2 - fee), "blind": is_blind(nm, r["stat"]), "_hit": miss})
        elif gs is not None:
            if kind == "spread":
                team, x = r["name"].upper(), float(r["line"])
                fmm = gs["margin"] if team == home else -gs["margin"]
                win, push = (fmm + x > 0).mean(), (fmm + x == 0).mean()
                p, lab = win / (1 - push) if push < 1 else win, f"{team} {x:+g}"
            elif kind == "total":
                side, x = r["name"].lower(), float(r["line"])
                win = (gs["total"] > x).mean() if side == "over" else (gs["total"] < x).mean()
                push = (gs["total"] == x).mean()
                p, lab = win / (1 - push) if push < 1 else win, f"{side.title()} {x:g}"
            elif kind == "ml":
                team = r["name"].upper()
                fmm = gs["margin"] if team == home else -gs["margin"]
                p, lab = (fmm > 0).mean(), f"{team} to win"
            elif kind == "tt":
                team, x = r["name"].upper(), float(r["line"])
                pts = gs["home"] if team == home else gs["away"]
                p, lab = (pts > x).mean(), f"{team} team total over {x:g}"
            else:
                continue
            lines.append({"label": lab, "p": float(p), "price": price, "cost": cost, "edge": float(p - cost)})
    for l in lines:
        l["stake"] = _kelly_stake(l["p"], l["cost"], bankroll)
    rep["lines"] = sorted(lines, key=lambda l: -l["edge"])
    rep["book"] = sorted(book, key=lambda b: -abs(b["p_over"] - 0.5))
    # Robinhood "main line" per player+stat: the ladder rung priced closest to 50c (the market's own line)
    ladders = {}
    for l in legs:
        if l["side"] == "yes":
            ladders.setdefault((l["player"], l["stat"]), []).append(l)
    market = []
    for (nm, st), rungs in ladders.items():
        r = min(rungs, key=lambda l: (abs(l["price"] - 0.5), l["x"]))
        v = sim["players"][r["pid"]][st]
        market.append({"player": nm, "stat": st, "line": r["x"], "price": r["price"], "p_model": r["p"],
                       "median": float(np.median(v)), "blind": r["blind"],
                       "team": sim["info"][r["pid"]]["team"]})
    rep["market"] = sorted(market, key=lambda m: -m["p_model"])   # highest hit rate first
    # full book: every rung on the board (Yes and No), highest hit rate first
    rep["full_book"] = sorted(({"player": l["player"], "team": sim["info"][l["pid"]]["team"], "stat": l["stat"],
                                "line": l["x"], "side": l["side"], "price": l["price"], "p": l["p"], "edge": l["edge"],
                                "median": float(np.median(sim["players"][l["pid"]][l["stat"]])), "blind": l["blind"]}
                               for l in legs), key=lambda r: (-r["p"], r["player"]))
    for t in box:
        for row in box[t]:
            row["book"] = {b["stat"]: b["line"] for b in book if b["player"] == row["name"]}

    usable = [l for l in legs if not l["blind"]]
    for l in usable:
        l["stake"] = _kelly_stake(l["p"], l["cost"], bankroll)
    singles, seen = [], set()
    for l in sorted(usable, key=lambda l: -l["edge"]):
        k = (l["player"], l["stat"])
        if k in seen:
            continue
        seen.add(k)
        singles.append({k2: v for k2, v in l.items() if k2 != "_hit"})
        if len(singles) == 10:
            break
    rep["singles"] = singles

    # ---------- parlays ----------
    pool = [l for l in usable if l["p"] >= 0.5 and l["edge"] >= -0.035]
    pool = sorted(pool, key=lambda l: -l["edge"])[:28]
    combos = []
    for size in (2, 3, 4, 5):
        for c in itertools.combinations(pool, size):
            seen_k = set()
            ok = True
            for l in c:
                kk = (l["player"], "rush" if l["stat"] == "rush_yds" else "recv")
                if kk in seen_k:
                    ok = False
                    break
                seen_k.add(kk)
            if not ok:
                continue
            ticket = float(np.prod([l["price"] for l in c]) * DISC)
            if not 0.05 <= ticket <= 0.60:
                continue
            joint = float(np.logical_and.reduce([l["_hit"] for l in c]).mean())
            cost = ticket + fee
            combos.append({"legs": [l["label"] for l in c], "legs_data": [[l["pid"], l["stat"], l["x"]] + (["no"] if l["side"] == "no" else []) for l in c],
                           "p": joint, "ticket": ticket, "cost": cost,
                           "edge": joint - cost, "fair": american(joint)})
    combos.sort(key=lambda x: -x["edge"])
    top, used = [], []
    for c in combos:
        if any(len(set(c["legs"]) & set(u)) >= len(c["legs"]) - 1 for u in used):
            continue  # keep the list varied
        c["stake"] = _kelly_stake(c["p"], c["cost"], bankroll)
        top.append(c)
        used.append(c["legs"])
        if len(top) == 10:
            break
    rep["parlays"] = top

    # ---------- hit-rate parlays (alt lines, ranked by hit rate, edge shown but not required) ----------
    rep["hit_parlays"] = hit_rate_parlays(usable, fee)

    # ---------- best bet ----------
    cands = [("single", s["label"], s) for s in singles if s["stake"]] + \
            [("parlay", " + ".join(p["legs"]), p) for p in top if p["stake"]] + \
            [("game line", l["label"], l) for l in rep["lines"] if l["stake"]]
    from .pricing import plan_game

    def legs_of(kind, d):
        if kind == "single":
            return [(d["pid"], d["stat"])]
        if kind == "parlay":
            return [(leg[0], leg[1]) for leg in d["legs_data"]]
        return []
    plan = plan_game([{"kind": kind, "label": label, "p": d["p"], "cost": d["cost"], "edge": d["edge"],
                       "stake": d["stake"], "legs": legs_of(kind, d)} for kind, label, d in cands], bankroll)
    rep["plan"] = plan
    rep["best"] = plan["bets"][0] if plan["bets"] else None
    return rep


# ======================= CANVA =======================
_LBL = {"pass_att": "pass attempts", "pass_cmp": "completions", "pass_yds": "pass yds", "rush_yds": "rush yds",
        "rec_yds": "rec yds", "rec": "receptions"}
def canva_brief(rep: dict, title: str) -> str:
    """Multi-page Canva brief written ONLY from the report's numbers (no retyping).
    After Canva builds it, read the design back and check every number against this brief."""
    A, H = rep["away"], rep["home"]
    med = lambda v: v[2]
    S = lambda st: _LBL.get(st, STAT_SHORT.get(st, st))
    out = ["A premium sports-analytics Instagram carousel for an NFL game simulation, with exactly the pages listed below, "
           "in order. Dark navy background, teal accents, bold condensed scoreboard typography, clean tables with aligned columns. "
           "Do NOT use NFL or team logos or trademarked imagery; team abbreviations as text only. Use every number EXACTLY as "
           "written; do not round, add, drop, or invent any number or row. Every word must be live, editable text: never bake "
           "text or tables into background images, never duplicate any text, and leave clear space so nothing overlaps. "
           "Keep each table small enough that every row fits on its page. Put this footer on every page, once: "
           '"Simulation projections, not guarantees. Bet responsibly. 21+. 1-800-GAMBLER."']
    # page 1: summary
    out.append(f'PAGE 1 (summary). Title: "{title}"')
    sc = rep.get("score")
    if sc:
        out.append(f'Headline: "{rep["sims"]:,} SIMULATIONS: {A} {sc["away_pts"]:.0f}, {H} {sc["home_pts"]:.0f}"')
        out.append(f'Sub line: "{A} win {sc["away_win"]:.0%} of sims. Big books: {sc["fav"]} -{sc["spread"]:g}, total {sc["total"]:g}."')
    pl = rep.get("plan") or {}
    if pl.get("bets"):
        out.append(f'Section "Bet plan" (total ${pl["total"]:.0f}):')
        out += [f'- {b["label"]}: hits {b["p"]:.0%} in sims, {b["cost"]*100:.0f}c with fee, edge {b["edge"]*100:+.1f} pts, stake ${b["stake"]:.0f}'
                for b in pl["bets"]]
    else:
        out.append('Banner: "Model verdict: PASS. Nothing on the board clears our 2% edge rule."')
    if rep.get("blind"):
        out.append('Small note: "Not bet (model blind spots): ' + "; ".join(rep["blind"]) + '."')
    # pages 2-3: full box score per team
    page = 2
    for t in (A, H):
        rows = rep["box"].get(t, [])
        out.append(f'PAGE {page} (full box score). Title: "{t} projected box score (median of {rep["sims"]:,} sims)". '
                   'Table columns: Player | Targets | Rec | Rec yds | Carries | Rush yds. One row per player, exactly these rows:')
        q = (rep.get("qbs") or {}).get(t)
        if q:
            st = q["stats"]
            out.append(f'- QB {q["name"]}: {med(st["pass_cmp"]):.0f}/{med(st["pass_att"]):.0f}, {med(st["pass_yds"]):.0f} pass yds, '
                       f'{med(st["pass_td"]):.0f} TD, {med(st["int"]):.0f} INT' + (" (third-string QB: low confidence)" if q.get("blind") else ""))
        for r in rows:
            if r["pos"] == "QB":
                continue
            st = r["stats"]
            g = lambda k: f'{med(st[k]):.0f}' if k in st else "0"
            out.append(f'- {r["name"]} ({r["pos"]}) | {g("targets")} | {g("rec")} | {g("rec_yds")} | {g("rush_att")} | {g("rush_yds")}')
        page += 1
    # hit-rate parlays page
    hp = rep.get("hit_parlays") or []
    if hp:
        out.append(f'PAGE {page} (parlays). Title: "Highest hit-rate parlays". Subtitle: "Alt lines, ranked by how often every leg '
                   'hits in the sims. Not model bets unless edge is +2 or more." Exactly these tickets, in this order:')
        for k, t in enumerate(hp[:5], 1):
            out.append(f'- #{k}: ' + " + ".join(t["legs"]) + f' | hits {t["p"]:.0%} | ticket {t["ticket"]*100:.0f}c | edge {t["edge"]*100:+.1f}')
        page += 1
    # book / market line vs prediction, highest hit rate first
    book = rep.get("book", [])
    mk = rep.get("market", [])
    if book:
        out.append(f'PAGE {page} (book line vs prediction). Title: "Big-book lines vs our projection". '
                   'Table columns: Player | Stat | Line | Source | Our probability | Our median. Exactly these rows:')
        for b in sorted(book, key=lambda b: -max(b["p_over"], 1 - b["p_over"])):
            side, pr = ("over", b["p_over"]) if b["p_over"] >= 0.5 else ("under", 1 - b["p_over"])
            out.append(f'- {b["player"]} | {S(b["stat"])} | {side} {b["line"]:g} | {b["src"] or "big book"} | '
                       f'{pr:.0%} {side} | {b["median"]:.0f}' + (" | blind spot" if b.get("blind") else ""))
        page += 1
    per = -(-len(mk) // max(1, -(-len(mk) // 16))) if mk else 1   # even pages, at most 16 rows each
    for c in range(0, len(mk), per):
        out.append(f'PAGE {page} (Robinhood lines vs prediction, highest hit rate first). Title: "Robinhood lines vs our projection"'
                   + (' (continued)' if c else '') + '. Table columns: Player | Stat | Line | Robinhood | Our probability | Our median. '
                   'Exactly these rows, in this order:')
        for m in mk[c:c + per]:
            out.append(f'- {m["player"]} ({m["team"]}) | {S(m["stat"])} | {m["line"]:g}+ | {m["price"]*100:.0f}c | '
                       f'{m["p_model"]:.0%} | {m["median"]:.0f}' + (" | blind spot" if m["blind"] else ""))
        out.append('Small note on this page: "Robinhood line = the rung priced closest to 50c. Our probability is before the 2c fee. '
                   'Blind spots are shown, never bet."')
        page += 1
    return "\n".join(out)


# ======================= HTML =======================
CSS = """
/* Layout: a single reading column; the predicted score is the masthead, then bet decisions, then evidence. */
:root{
  --bg:#f4f6f8; --panel:#ffffff; --ink:#14202b; --muted:#5a6878; --line:#d8dee6;
  --accent:#0d6e6a; --accent-soft:#d7eeec; --good:#15803d; --bad:#b4232a; --warn:#a15c07;
  --display:"Barlow Condensed","Arial Narrow",system-ui,sans-serif;
  --body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0e1418; --panel:#151d23; --ink:#e4ebf0; --muted:#93a3b2; --line:#26323c;
  --accent:#3cc0b6; --accent-soft:#16312f; --good:#4ade80; --bad:#f87171; --warn:#fbbf24; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0e1418; --panel:#151d23; --ink:#e4ebf0; --muted:#93a3b2; --line:#26323c;
  --accent:#3cc0b6; --accent-soft:#16312f; --good:#4ade80; --bad:#f87171; --warn:#fbbf24; color-scheme:dark}
body{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:15px;line-height:1.5;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:20px 48px}
.wrap{max-width:980px;margin:0 auto;display:grid;gap:28px}
h1,h2{font-family:var(--display);font-weight:600;letter-spacing:.01em;text-wrap:balance;margin:0}
h2{font-size:1.45rem;text-transform:uppercase;letter-spacing:.06em}
.eyebrow{font-family:var(--mono);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.mast{display:grid;gap:10px;border-bottom:2px solid var(--ink);padding-bottom:18px}
.score{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap;font-family:var(--display)}
.score .team{font-size:2.2rem;font-weight:600}
.score .pts{font-size:4.2rem;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
.score .at{color:var(--muted);font-size:1.4rem}
.winbar{display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--line);max-width:520px}
.winbar span{display:block}
.sub{color:var(--muted);font-size:.92rem;max-width:68ch}
section{display:grid;gap:12px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.best{border:2px solid var(--accent);background:var(--accent-soft)}
.best .big{font-family:var(--display);font-size:1.6rem;font-weight:600}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:.9rem}
th{font-family:var(--mono);font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);text-align:left;font-weight:500;padding:6px 8px;border-bottom:1px solid var(--line)}
td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td.num,th.num{text-align:right}
.pill{display:inline-block;font-family:var(--mono);font-size:.7rem;padding:1px 7px;border-radius:999px;border:1px solid currentColor;white-space:nowrap}
.good{color:var(--good)} .bad{color:var(--bad)} .warn{color:var(--warn)} .muted{color:var(--muted)}
.range{position:relative;height:8px;min-width:90px;background:var(--line);border-radius:4px}
.range .iq{position:absolute;top:0;bottom:0;background:var(--accent);opacity:.35;border-radius:4px}
.range .med{position:absolute;top:-3px;bottom:-3px;width:3px;background:var(--accent);border-radius:2px}
.range .bk{position:absolute;top:-5px;bottom:-5px;width:2px;background:var(--warn)}
.statcell{display:grid;gap:4px;min-width:110px}
.statcell b{font-variant-numeric:tabular-nums}
.news li{display:grid;grid-template-columns:auto 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)}
.news ul{list-style:none;margin:0;padding:0}
.news a{color:var(--accent)}
.legs{margin:0;padding-left:18px}
.note{font-size:.85rem;color:var(--muted);max-width:75ch}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
"""


def _pct(x):
    return f"{x * 100:.0f}%"


def _e(x):
    return html.escape(str(x))


def render(rep, title):
    H, A = rep["home"], rep["away"]
    out = [f'<title>{_e(title)}</title>\n<meta name="claude:viewport-fit-sides" content="cover">',
           '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;600&display=swap">',
           f"<style>{CSS}</style>", '<div class="wrap">']
    sc = rep.get("score")
    # masthead
    out.append('<header class="mast">')
    out.append(f'<div class="eyebrow">Game report · {_e(rep["date"])} · {rep["sims"]:,} simulated games</div>')
    if sc:
        out.append(f'<div class="score"><span class="team">{A}</span><span class="pts">{sc["away_pts"]:.0f}</span>'
                   f'<span class="at">at</span><span class="team">{H}</span><span class="pts">{sc["home_pts"]:.0f}</span></div>')
        aw, hw, tie = sc["away_win"], sc["home_win"], sc["tie"]
        out.append(f'<div class="winbar" role="img" aria-label="{A} wins {_pct(aw)}, {H} wins {_pct(hw)}">'
                   f'<span style="width:{aw*100:.1f}%;background:var(--accent)"></span>'
                   f'<span style="width:{tie*100:.1f}%;background:var(--muted)"></span>'
                   f'<span style="width:{hw*100:.1f}%;background:var(--ink)"></span></div>')
        common = ", ".join(f'{H if c["margin"] > 0 else A} by {abs(c["margin"])} ({_pct(c["pct"])})' for c in sc["common"] if c["margin"])
        out.append(f'<p class="sub">{A} win {_pct(aw)} · {H} win {_pct(hw)} · Most common finishes: {common}. '
                   f'Centered on the big-book line ({sc["fav"]} −{sc["spread"]:g}, total {sc["total"]:g}).</p>')
    else:
        out.append(f'<h1 style="font-size:2.4rem">{A} at {H}</h1>')
    out.append(f'<p class="sub">Bankroll ${rep["bankroll"]:,.2f} · stakes are quarter Kelly, $50 minimum, all bets on this game capped at 10% of bankroll combined · '
               f'every edge includes the {rep["fee"]*100:.0f}c per-contract fee.</p></header>')

    # best bet
    out.append('<section><h2>Best bet</h2>')
    b = rep.get("best")
    if b:
        out.append(f'<div class="panel best"><div class="eyebrow">{_e(b["kind"])}</div><div class="big">{_e(b["label"])}</div>'
                   f'<div>Hits {_pct(b["p"])} in the sims · costs {b["cost"]*100:.1f}c with fee · edge {b["edge"]*100:+.1f} pts · '
                   f'<b>stake ${b["stake"]}</b> · expected profit ${b["ev"]:.0f}</div></div>')
    else:
        msg = "Send Robinhood's board to rank bets." if not rep["singles"] and not rep["lines"] else "Nothing on the board clears the 2% edge rule. Pass."
        out.append(f'<div class="panel">{msg}</div>')
    out.append('</section>')
    pl = rep.get("plan")
    if pl and pl["bets"]:
        rows = "".join(f'<tr><td>{i}</td><td>{_e(c["label"])}<div class="muted">{_e(c["kind"])}</div></td>'
                       f'<td class="num">{_pct(c["p"])}</td><td class="num">{c["cost"]*100:.1f}c</td>'
                       f'<td class="num">{c["edge"]*100:+.1f}</td><td class="num">${c["stake"]:.0f}</td></tr>'
                       for i, c in enumerate(pl["bets"], 1))
        out.append('<section><h2>Bet plan for this game</h2><div class="panel"><table><thead><tr><th>#</th><th>Bet</th>'
                   '<th class="num">Hits</th><th class="num">Cost</th><th class="num">Edge</th><th class="num">Stake</th></tr></thead>'
                   f'<tbody>{rows}</tbody></table><p class="note">Total ${pl["total"]:.0f} of a ${pl["cap"]} per-game cap '
                   '(10% of bankroll across every bet on this game; max 3 bets; no player+stat repeated).</p></div></section>')

    # book lines vs model
    if rep.get("book"):
        out.append('<section><h2>Book lines vs my projection</h2>')
        rows = []
        for b in rep["book"]:
            lean = "over" if b["p_over"] >= 0.5 else "under"
            strength = abs(b["p_over"] - 0.5)
            cls = "good" if strength >= 0.08 else ("warn" if strength >= 0.04 else "muted")
            price = ""
            for side in ("over", "under"):
                if f"{side}_odds" in b:
                    e = b[f"{side}_edge"]
                    price += f'{side[0].upper()} {b[side + "_odds"]:+.0f} ({e*100:+.1f}) '
            flag = ' <span class="pill warn">blind spot</span>' if b["blind"] else ""
            rows.append(f'<tr><td><b>{_e(b["player"])}</b>{flag}</td><td>{STAT_SHORT[b["stat"]]}</td><td class="num">{b["line"]:g}</td>'
                        f'<td class="num">{b["median"]:.0f}</td><td class="num">{_pct(b["p_over"])}</td>'
                        f'<td class="{cls}">{lean} {strength*200:.0f}%</td><td class="muted" style="font-size:.8rem">{_e(price.strip())}</td></tr>')
        out.append('<div class="panel tbl"><table><tr><th>Player</th><th>Stat</th><th class="num">Book line</th><th class="num">My median</th>'
                   '<th class="num">P(over)</th><th>Lean</th><th>Book odds (edge pts)</th></tr>' + "".join(rows) + '</table>'
                   '<p class="note">Book lines come from big sportsbooks (DraftKings/FanDuel/consensus). Lean strength = how far my over probability sits from 50/50. '
                   'Edge pts use the book\'s own prices when given. A lean is not a bet until a price clears the 2% rule.</p></div></section>')

    # hit-rate parlays
    if rep.get("hit_parlays"):
        rows = "".join(f'<tr><td>{i}</td><td>{"<br>".join(_e(x) for x in hp["legs"])}</td><td class="num"><b>{_pct(hp["p"])}</b></td>'
                       f'<td class="num">{hp["ticket"]*100:.1f}c</td><td class="num {"good" if hp["edge"] >= .02 else "muted"}">{hp["edge"]*100:+.1f}</td>'
                       f'<td class="num">{hp["fair"]}</td></tr>' for i, hp in enumerate(rep["hit_parlays"], 1))
        out.append('<section><h2>Highest hit-rate parlays (alt lines)</h2><div class="panel tbl"><table><tr><th>#</th><th>Legs</th>'
                   '<th class="num">Hits</th><th class="num">Ticket</th><th class="num">Edge pts</th><th class="num">Fair</th></tr>' + rows + '</table>'
                   '<p class="note">Ranked by how often every leg hits together in the sims, regardless of edge. Ticket = product of the Robinhood leg '
                   'prices (no combo discount), 5c to 40c. Edge includes the 2c fee; only tickets with edge of +2 or more qualify as model bets. '
                   'Blind spots excluded.</p></div></section>')

    # full book
    if rep.get("full_book"):
        rows = []
        for r in rep["full_book"]:
            q = (not r["blind"]) and r["edge"] >= 0.02
            cls = "good" if r["edge"] >= 0.02 else ("bad" if r["edge"] <= -0.05 else "muted")
            flag = ' <span class="pill warn">blind spot</span>' if r["blind"] else (' <span class="pill good">qualifies</span>' if q else "")
            side = "" if r["side"] == "yes" else "NO "
            rows.append(f'<tr><td><b>{_e(r["player"])}</b> <span class="muted">{r["team"]}</span>{flag}</td><td>{side}{r["line"]:g}+ {STAT_SHORT[r["stat"]]}</td>'
                        f'<td class="num"><b>{_pct(r["p"])}</b></td><td class="num">{r["price"]*100:.0f}c</td>'
                        f'<td class="num {cls}">{r["edge"]*100:+.1f}</td><td class="num">{r["median"]:.0f}</td></tr>')
        out.append(f'<section><h2>Full book: every line on the board ({len(rows)}), highest hit rate first</h2><details><summary>Show all lines</summary>'
                   '<div class="panel tbl"><table><tr><th>Player</th><th>Line</th><th class="num">Hits</th><th class="num">Price</th>'
                   '<th class="num">Edge pts</th><th class="num">Median</th></tr>' + "".join(rows) + '</table>'
                   '<p class="note">Hits = share of the sims where the line cashes. Edge = hits minus price minus the 2c fee. '
                   '"Qualifies" = edge of +2 or more and not a blind spot. Robinhood prices are the displayed quotes; thin ladders can be stale.</p>'
                   '</div></details></section>')

    # Robinhood main lines vs model
    if rep.get("market"):
        rows = []
        for m in rep["market"]:
            d = m["p_model"] - m["price"]
            cls = "good" if d >= 0.04 else ("bad" if d <= -0.04 else "muted")
            flag = ' <span class="pill warn">blind spot</span>' if m["blind"] else ""
            rows.append(f'<tr><td><b>{_e(m["player"])}</b> <span class="muted">{m["team"]}</span>{flag}</td><td>{STAT_SHORT[m["stat"]]}</td>'
                        f'<td class="num">{m["line"]:g}+</td><td class="num">{m["price"]*100:.0f}c</td>'
                        f'<td class="num">{_pct(m["p_model"])}</td><td class="num {cls}">{d*100:+.0f}</td>'
                        f'<td class="num">{m["median"]:.0f}</td></tr>')
        out.append('<section><h2>Robinhood main lines vs my projection</h2><div class="panel tbl"><table><tr><th>Player</th><th>Stat</th>'
                   '<th class="num">Line</th><th class="num">Robinhood</th><th class="num">My P</th><th class="num">Diff pts</th>'
                   '<th class="num">My median</th></tr>' + "".join(rows) + '</table>'
                   '<p class="note">Main line = the rung on each Robinhood ladder priced closest to 50c, i.e. the market\'s own line for that stat. '
                   'Diff = my probability minus the price, before the 2c fee. Blind spots are shown but never bet.</p></div></section>')

    # news
    if rep["news"]:
        out.append('<section class="news"><h2>Injuries and news</h2><div class="panel"><ul>')
        for n in rep["news"]:
            st = n.get("status", "")
            cls = "bad" if st.lower() in ("out", "ir", "doubtful") else ("warn" if st.lower() in ("questionable", "limited") else "good")
            src = f' <a href="{_e(n["url"])}" target="_blank" rel="noopener">{_e(n.get("source", "source"))}</a>' if n.get("url") else ""
            out.append(f'<li><span class="pill {cls}">{_e(st)}</span><span><b>{_e(n.get("player",""))}</b> '
                       f'<span class="muted">{_e(n.get("team",""))}</span> · {_e(n.get("detail",""))}{src}</span></li>')
        out.append('</ul></div></section>')

    # game lines
    if sc:
        out.append('<section><h2>Spread, total, team totals</h2><div class="grid2">')
        rows = "".join(f'<tr><td>{sc["fav"]} {l["line"]:+g}</td><td class="num">{_pct(l["win"])}'
                       f'{" (+" + _pct(l["push"]) + " push)" if l["push"] > 0.001 else ""}</td><td class="num">{american(l["win"]/(1-l["push"]) if l["push"]<1 else l["win"])}</td></tr>'
                       for l in sc["alt_spreads"])
        out.append(f'<div class="panel tbl"><table><tr><th>Spread</th><th class="num">Covers</th><th class="num">Fair</th></tr>{rows}</table></div>')
        rows = "".join(f'<tr><td>Over {l["line"]:g}</td><td class="num">{_pct(l["over"])}</td><td class="num">{american(l["over"])}</td></tr>' for l in sc["alt_totals"])
        tt = " · ".join(f"{t} {v:.0f}" for t, v in sc["team_totals"].items())
        out.append(f'<div class="panel tbl"><table><tr><th>Total</th><th class="num">Hits</th><th class="num">Fair</th></tr>{rows}</table>'
                   f'<p class="note">Median team totals: {tt}.</p></div></div>')
        if sc.get("model_line"):
            ml = sc["model_line"]
            out.append(f'<p class="note">My independent model: {_e(ml)}. Shown for reference only: it lost to closing lines in a five-season test, so it never drives a bet.</p>')
        if rep["lines"]:
            rows = "".join(f'<tr><td>{_e(l["label"])}</td><td class="num">{l["price"]*100:.0f}c</td><td class="num">{_pct(l["p"])}</td>'
                           f'<td class="num {"good" if l["edge"] >= .02 else "muted"}">{l["edge"]*100:+.1f}</td><td class="num">{("$" + str(l["stake"])) if l["stake"] else "pass"}</td></tr>'
                           for l in rep["lines"])
            out.append(f'<div class="panel tbl"><table><tr><th>Robinhood line</th><th class="num">Price</th><th class="num">Sims</th><th class="num">Edge</th><th class="num">Stake</th></tr>{rows}</table></div>')
        out.append('</section>')

    # quarterbacks
    if rep.get("qbs"):
        rows = []
        for t in (A, H):
            q = rep["qbs"].get(t)
            if not q:
                continue
            st = q["stats"]
            f = lambda k: f'<b>{st[k][2]:.0f}</b> <span class="muted" style="font-size:.75rem">{st[k][1]:.0f} to {st[k][3]:.0f}</span>'
            adj = f'receivers x{q["yds_mult"]:.2f} yds, x{q["cmp_mult"]:.2f} catches'
            flag = ' <span class="pill warn">blind spot</span>' if q["blind"] else ""
            rows.append(f'<tr><td><b>{_e(q["name"])}</b> <span class="muted">{t}</span>{flag}<div class="muted" style="font-size:.75rem">{adj}</div></td>'
                        f'<td>{f("pass_cmp")} / {f("pass_att")}</td><td>{f("pass_yds")}</td><td class="num">{st["pass_td"][2]:.0f} <span class="muted" style="font-size:.75rem">2+ {q["p"]["2+ TD"]*100:.0f}%</span></td>'
                        f'<td class="num">{st["int"][2]:.0f} <span class="muted" style="font-size:.75rem">1+ {q["p"]["1+ INT"]*100:.0f}%</span></td><td>{f("rush_yds")}</td></tr>')
        out.append('<section><h2>Quarterbacks</h2><div class="panel tbl"><table><tr><th>QB</th><th>Cmp / Att</th><th>Pass yds</th>'
                   '<th class="num">TD</th><th class="num">INT</th><th>Rush yds</th></tr>' + "".join(rows) + '</table>'
                   '<p class="note">Passing lines are the sum of every simulated target, so they move with the receivers. '
                   'QB quality scales his receivers (backtested: completions -0.97% error). TD and INT odds are less tested than yards.</p></div></section>')

    # box score
    out.append(f'<section><h2>Projected box score</h2><p class="note">Median (solid mark) with the middle half of {rep["sims"]:,} sims shaded; '
               'the amber tick is the big-book line where one exists. Bars share one scale per stat across both teams.</p>')
    maxes = {}
    for t in (H, A):
        for r in rep["box"][t]:
            for st, q in r["stats"].items():
                maxes[st] = max(maxes.get(st, 1), q[4])
    cols = [("targets", "Targets"), ("rec", "Catches"), ("rec_yds", "Rec yds"), ("rush_att", "Carries"), ("rush_yds", "Rush yds")]
    for t in (A, H):
        vol = rep["volume"][t]
        out.append(f'<div class="panel tbl"><div class="eyebrow">{t} · projected {vol["targets"]:.0f} targets, {vol["rushes"]:.0f} rushes</div>'
                   '<table><tr><th>Player</th>' + "".join(f"<th>{c}</th>" for _, c in cols) + '</tr>')
        for r in rep["box"][t]:
            cells = []
            for st, _ in cols:
                q = r["stats"].get(st)
                if not q:
                    cells.append('<td class="muted">·</td>')
                    continue
                mx = maxes[st]
                bl = r.get("book", {}).get(st)
                tick = (f'<div class="bk" style="left:calc({min(bl/mx,1)*100:.1f}% - 1px)" title="Book line {bl:g}"></div>' if bl is not None else "")
                btxt = f' · book {bl:g}' if bl is not None else ""
                cells.append(f'<td><div class="statcell"><b>{q[2]:.0f}</b><div class="range"><div class="iq" style="left:{q[1]/mx*100:.1f}%;width:{max((q[3]-q[1])/mx*100,1):.1f}%"></div>'
                             f'<div class="med" style="left:calc({q[2]/mx*100:.1f}% - 1px)"></div>{tick}</div><span class="muted" style="font-size:.75rem">{q[1]:.0f} to {q[3]:.0f}{btxt}</span></div></td>')
            flag = ' <span class="pill warn">model blind spot</span>' if r["blind"] else ""
            out.append(f'<tr><td><b>{_e(r["name"])}</b> <span class="muted">{r["pos"]}</span>{flag}</td>{"".join(cells)}</tr>')
        out.append('</table></div>')
    out.append('</section>')

    # singles
    out.append('<section><h2>Top 10 single props</h2>')
    if rep["singles"]:
        rows = "".join(f'<tr><td>{i}</td><td>{_e(s["label"])}</td><td class="num">{s["price"]*100:.0f}c</td><td class="num">{_pct(s["p"])}</td>'
                       f'<td class="num {"good" if s["edge"] >= .02 else ("bad" if s["edge"] < 0 else "muted")}">{s["edge"]*100:+.1f}</td>'
                       f'<td class="num">{("$" + str(s["stake"])) if s["stake"] else "pass"}</td></tr>' for i, s in enumerate(rep["singles"], 1))
        out.append(f'<div class="panel tbl"><table><tr><th>#</th><th>Prop</th><th class="num">Price</th><th class="num">Hits</th><th class="num">Edge</th><th class="num">Stake</th></tr>{rows}</table>'
                   '<p class="note">Ranked by edge after the fee. Only rows with a stake clear your 2% rule; the rest are the closest near misses.</p></div>')
    else:
        out.append('<div class="panel">Waiting on Robinhood\'s prop prices.</div>')
    out.append('</section>')

    # parlays
    out.append('<section><h2>Top 10 parlays</h2>')
    if rep["parlays"]:
        rows = "".join(f'<tr><td>{i}</td><td><ul class="legs">' + "".join(f"<li>{_e(l)}</li>" for l in p["legs"]) + '</ul></td>'
                       f'<td class="num">{_pct(p["p"])}</td><td class="num">{p["ticket"]*100:.0f}c</td>'
                       f'<td class="num {"good" if p["edge"] >= .02 else "muted"}">{p["edge"]*100:+.1f}</td>'
                       f'<td class="num">{("$" + str(p["stake"])) if p["stake"] else "pass"}</td></tr>' for i, p in enumerate(rep["parlays"], 1))
        out.append(f'<div class="panel tbl"><table><tr><th>#</th><th>Legs (main and alt lines)</th><th class="num">Hits</th><th class="num">Est. ticket</th><th class="num">Edge</th><th class="num">Stake</th></tr>{rows}</table>'
                   '<p class="note">Joint hit rate comes from the same simulated games, so legs that move together are priced together. '
                   'Ticket price is estimated from leg prices; confirm the real ticket before buying. One receiving leg per player; rushing plus receiving allowed.</p></div>')
    else:
        out.append('<div class="panel">Waiting on Robinhood\'s prop prices.</div>')
    out.append('</section>')
    if rep["blind"]:
        out.append(f'<p class="note">Excluded from bets as model blind spots tonight: {", ".join(_e(b) for b in rep["blind"])}.</p>')
    out.append('<p class="note">Simulation projections, not guarantees. Picks are logged with a timestamp before kickoff and graded '
               'afterward, wins and losses alike. 21+. If gambling stops being fun, call 1-800-GAMBLER.</p>')
    out.append('</div>')
    return "\n".join(out)
