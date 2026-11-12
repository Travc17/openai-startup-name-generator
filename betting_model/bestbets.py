"""Best Bets bot (BESTBETS_PROMPT.md; spec BESTBETS_SPEC.md; Travis 2026-11-12).

Ten bets for one game, ranked best first, at least 3 parlays, the rest singles or game lines, priced ONLY with Kalshi.

    python bestbets.py --proj projections/<game>.json --kalshi markets/<game>_kalshi_<when>.csv \\
        --books markets/<game>_books_<when>.csv [--books-alt markets/<game>_books_alt_<when>.csv] \\
        [--kalshi-game markets/<game>_kalshi_game_<when>.csv | --pull-game] --when final

Rules (Travis 2026-11-12): every bet type is allowed; no single and no parlay leg above 80% (the model's probability of
the bet side) or above 80c; score = edge points - 0.1 x distance from 50% (lines nearer 50% rank higher when the edge
allows); bets without an edge are still listed, labeled; attempt/completion lines never go in a parlay, and every
attempt/completion single comes with a non-attempt alternate. Bankroll stakes only for bets that pass CLAUDE.md's
approved rules (edge >= 10 points after fee, pricing.rule_ok, max 3, 10% per game). Never places a bet.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "simcast"))
from nflmodel import pricing  # noqa: E402
from nflmodel.market import name_key  # noqa: E402

CAP = 0.80                       # Travis: nothing above 80% (model) or 80c (price)
FEE1, FEE2 = 0.015, 0.024        # observed Kalshi fee per contract: single, combo (2026-11-05 fills)
ATTEMPTS = {"pass_att", "pass_cmp", "rush_att"}
NEVER = {"pass_td", "int"}       # not calibration-checked (CLAUDE.md)
ALT_OF = {"pass_att": "pass_yds", "pass_cmp": "pass_yds", "rush_att": "rush_yds"}
N_PICKS, MIN_PARLAYS = 10, 3
LABEL = {"rec": "catches", "rec_yds": "rec yds", "rush_yds": "rush yds", "pass_yds": "pass yds", "pass_att": "pass att",
         "pass_cmp": "completions", "rec_rush_yds": "rush+rec yds", "rush_att": "carries"}


def score(p: float, edge: float) -> float:
    return 100 * edge - 0.1 * abs(100 * p - 50)


def load_sims(proj: str) -> dict:
    from rerun import rerun, check
    with contextlib.redirect_stdout(io.StringIO()):
        run = rerun(proj)
    bad = check(run)
    if bad:
        sys.exit("STOP: projections cannot be reproduced:\n" + "\n".join(bad[:5]))
    return run


def grades(proj_path: str) -> dict:
    g = HERE / "simcast" / "games" / (Path(proj_path).stem + ".json")
    if not g.exists():
        return {}
    return {(name_key(r["name"]), r["stat"]): r["grade"] for r in json.loads(g.read_text()).get("pred", [])}


def kalshi_game(away: str, home: str) -> pd.DataFrame:
    """Kalshi moneyline, spread, total (+ alternates when posted) via the odds feed (about 5 credits)."""
    from nflmodel import odds_api
    ev = odds_api.find_event(away, home)
    rows, now = [], datetime.now(timezone.utc).isoformat(timespec="seconds")
    for mk in ("h2h,spreads,totals", "alternate_spreads,alternate_totals"):
        try:
            data, hdr = odds_api._get(f"{odds_api.BASE}/events/{ev['id']}/odds", {"bookmakers": "kalshi", "markets": mk, "oddsFormat": "american"})
        except Exception as e:   # alternates may not be offered
            print(f"  (Kalshi {mk}: {e})")
            continue
        for b in data.get("bookmakers", []):
            for m in b["markets"]:
                for o in m["outcomes"]:
                    pr = o["price"]
                    c = 100 / (pr + 100) if pr > 0 else -pr / (-pr + 100)
                    rows.append({"market": m["key"].replace("alternate_", ""), "name": o["name"], "point": o.get("point"),
                                 "price": round(100 * c), "captured_at": now})
        print(f"  Kalshi {mk}: {odds_api.credits(hdr)}")
    return pd.DataFrame(rows)


def main(a) -> int:
    run = load_sims(a.proj)
    proj, sim, home, away = run["proj"], run["sim"]["players"], run["home"], run["away"]
    game = f"{away}@{home}"
    G = grades(a.proj)
    blind = set(proj["meta"].get("adjustments", {}).get("blind") or [])
    P = {name_key(n): (n, v) for n, v in proj["players"].items()}
    qbs = {v["pid"] for v in proj["players"].values() if v["pos"] == "QB"}

    books = pd.read_csv(a.books)
    books = books[~books.venue.str.contains("alt", case=False, na=False)]
    main_line = books[~books.stat.isin(["spreads", "totals"])].assign(k=books.player.map(name_key)).groupby(["k", "stat"]).line.median().to_dict()
    imp = lambda pr: 100 / (pr + 100) if pr > 0 else -pr / (-pr + 100)
    alt_over = {}
    if a.books_alt:
        ba = pd.read_csv(a.books_alt).query("side == 'over'")
        alt_over = ba.assign(k=ba.player.map(name_key), p=ba.price.map(imp)).groupby(["k", "stat", "line"]).p.median().to_dict()

    # ---------------- player-prop singles from Kalshi ladders ----------------
    q = pd.read_csv(a.kalshi)
    two = q.pivot_table(index=["player", "stat", "line"], columns="side", values="price", aggfunc="min")
    W = 0.20                                            # model weight in the best estimate (approved; Brier-tested)
    def p_market(player, stat, line, side, price):
        yes, no = (two.loc[(player, stat, line)].get("yes"), two.loc[(player, stat, line)].get("no")) if (player, stat, line) in two.index else (None, None)
        if yes is not None and no is not None and not (pd.isna(yes) or pd.isna(no)):
            pm = yes / (yes + no)
            return pm if side == "yes" else 1 - pm
        return price
    cands = []
    for r in q.itertuples():
        k = name_key(r.player)
        if k not in P or r.stat in NEVER:
            continue
        nm, pl = P[k]
        pid, pos = pl["pid"], pl["pos"]
        arr = sim.get(pid, {}).get(r.stat)
        if arr is None:
            continue
        x = int(round(r.line))
        over = r.side == "yes"
        p = float((np.asarray(arr) >= x).mean()) if over else float((np.asarray(arr) < x).mean())
        price = r.price / 100
        grade = G.get((k, r.stat)) or (max(G.get((k, "rec_yds"), "C"), G.get((k, "rush_yds"), "C")) if r.stat == "rec_rush_yds" else "C")
        if pos == "QB" and r.stat in ("pass_att", "pass_cmp", "pass_yds"):
            grade = G.get((k, r.stat), "A")
        flags = []
        if nm in blind or grade == "C":
            flags.append("blind spot / grade C")
        if p > CAP:
            flags.append(f"model {p:.0%} > 80%")
        if (0.2 * p + 0.8 * p_market(r.player, r.stat, r.line, r.side, price)) > CAP:
            flags.append("best estimate > 80%")
        if price > CAP:
            flags.append(f"price {r.price}c > 80c")
        ml = main_line.get((k, r.stat))
        bo = alt_over.get((k, r.stat, x - 0.5))
        bk = None if bo is None else (bo if over else 1 - bo)
        edge = p - price - FEE1
        pm = p_market(r.player, r.stat, r.line, r.side, price)
        pb = W * p + (1 - W) * pm
        eb = pb - price - FEE1
        ok, why = pricing.rule_ok("over" if over else "under", r.stat, pos)
        low_rung = over and ml is not None and x < ml
        cands.append(dict(kind="prop", pick=f"{nm} {'' if over else 'UNDER '}{x}+ {LABEL.get(r.stat, r.stat)}".replace("UNDER ", "NO ") if True else "",
                          name=nm, pid=pid, pos=pos, team=pl["team"], stat=r.stat, side="yes" if over else "no", x=x, p=p, price=price,
                          fee=FEE1, edge=edge, pm=pm, pb=pb, eb=eb, score=score(pb, eb), grade=grade, book_main=ml, books=bk,
                          bankroll=bool(ok and edge >= pricing.MIN_EDGE and not flags), rule_note=why if not ok else "",
                          low_rung=bool(low_rung), flags="; ".join(flags), legs=[(pid, r.stat)]))
    C = pd.DataFrame(cands)

    # ---------------- game lines from Kalshi, priced on the market-anchored score sim ----------------
    gl = []
    if a.pull_game or a.kalshi_game:
        K = kalshi_game(away, home) if a.pull_game else pd.read_csv(a.kalshi_game)
        if a.pull_game and len(K):
            out = a.kalshi_game or str(Path(a.kalshi).with_name(Path(a.kalshi).name.replace("_kalshi_", "_kalshi_game_")))
            K.to_csv(out, index=False)
            print(f"  saved {len(K)} Kalshi game-line quotes -> {out}")
        S = run["score"]
        H, A_, M, T = (np.asarray(S[c]) for c in ("home", "away", "margin", "total"))
        full = {"WAS": "Commanders", "NYG": "Giants"}
        for r in K.itertuples():
            nm = str(r.name)
            is_home = home in nm or nm.split()[-1] in TEAMNAME.get(home, "")
            if r.market == "totals":
                pt = float(r.point)
                p = float((T > pt).mean()) if nm.lower() == "over" else float((T < pt).mean())
                lab = f"{'Over' if nm.lower() == 'over' else 'Under'} {pt:g} total"
            elif r.market == "spreads":
                pt = float(r.point)
                mm = M if is_home else -M
                p = float((mm + pt > 0).mean())
                lab = f"{nm} {pt:+g}"
            else:
                mm = M if is_home else -M
                p = float((mm > 0).mean())
                lab = f"{nm} to win"
            price = r.price / 100
            edge = p - price - FEE1
            pb, eb = p, edge                                   # consensus-anchored: already the market view
            flags = []
            if p > CAP:
                flags.append(f"{p:.0%} > 80%")
            if price > CAP:
                flags.append(f"price {r.price}c > 80c")
            gl.append(dict(kind="game", pick=lab, name=lab, pid=None, pos="", team="", stat=r.market, side=nm, x=r.point, p=p,
                           price=price, fee=FEE1, edge=edge, pm=p, pb=pb, eb=eb, score=score(pb, eb), grade="", book_main=None, books=None,
                           bankroll=bool(edge >= pricing.MIN_EDGE and not flags), rule_note="priced on the consensus-anchored score sim",
                           low_rung=False, flags="; ".join(flags), legs=[("GAME", r.market)]))
    C = pd.concat([C, pd.DataFrame(gl)], ignore_index=True) if gl else C

    # ---------------- parlays: props only, no attempt/completion legs, every leg under the 80% cap ----------------
    L = C[(C.kind == "prop") & (C["flags"] == "") & ~C.stat.isin(ATTEMPTS) & (C.pb >= 0.45)]
    L = L.sort_values("score", ascending=False).groupby(["pid", "stat", "side"]).head(2).head(a.leg_pool)
    arr = {i: (np.asarray(sim[r.pid][r.stat]) >= r.x) if r.side == "yes" else (np.asarray(sim[r.pid][r.stat]) < r.x) for i, r in L.iterrows()}
    par = []
    for n in (2, 3, 4):
        for combo in itertools.combinations(L.index, n):
            rows = L.loc[list(combo)]
            per = rows.groupby("pid").stat.apply(list)
            if any(len(v) > 2 or (len(v) == 2 and not ({"rush_yds"} & set(v) and {"rec", "rec_yds"} & set(v))) for v in per):
                continue
            price = float(np.prod(rows.price))
            if price < a.min_ticket:
                continue
            p = float(np.logical_and.reduce([arr[i] for i in combo]).mean())
            edge = p - price - FEE2
            pb = min(0.999, p * float(np.prod(rows.pb / rows.p.clip(lower=1e-6))))
            eb = pb - price - FEE2
            bk = rows.books.astype(float).values
            par.append(dict(kind="parlay", pick=" + ".join(rows.pick), name="", pid=None, pos="", team="", stat="parlay", side="", x=None,
                            p=p, price=price, fee=FEE2, edge=edge, pm=float(np.prod(rows.pm)), pb=pb, eb=eb, score=score(pb, eb),
                            grade="".join(sorted(set(rows.grade))),
                            book_main=None, books=float(np.prod(bk)) if not np.isnan(bk).any() else None,
                            bankroll=bool(edge >= pricing.MIN_EDGE and all(pricing.rule_ok("over" if s == "yes" else "under", st, ps)[0]
                                                                         for s, st, ps in zip(rows.side, rows.stat, rows.pos))),
                            rule_note="", low_rung=False, flags="", legs=list(zip(rows.pid, rows.stat)), indep=float(np.prod(rows.p))))
    Pq = pd.DataFrame(par)
    print(f"candidates: {len(C)} singles/game lines ({(C["flags"] == '').sum()} under the 80% cap), {len(Pq)} parlays from {len(L)} legs")

    # ---------------- pick 10: at least 3 parlays, no player+stat used twice, best score first ----------------
    pool_s = C[C["flags"] == ""].sort_values("score", ascending=False)
    pool_p = Pq.sort_values("score", ascending=False) if len(Pq) else Pq
    picks, used, per_player = [], set(), {}
    def take(r):
        legs = {tuple(l) for l in r["legs"]}
        players = {l[0] for l in legs if l[0] != "GAME"}
        if legs & used or any(per_player.get(pp, 0) >= 2 for pp in players):
            return False                                    # no player+stat twice; a player in at most 2 picks
        picks.append(dict(r)); used.update(legs)
        for pp in players:
            per_player[pp] = per_player.get(pp, 0) + 1
        return True
    for _, r in pool_p.iterrows():
        if sum(p["kind"] == "parlay" for p in picks) >= MIN_PARLAYS:
            break
        take(r)
    merged = pd.concat([pool_s, pool_p], ignore_index=True).sort_values("score", ascending=False)
    for _, r in merged.iterrows():
        if len(picks) >= N_PICKS:
            break
        if r["kind"] == "game" and any(p["kind"] == "game" and p["stat"] == r["stat"] for p in picks):
            continue                                        # one pick per game-line market
        take(r)
    picks.sort(key=lambda r: -r["score"])
    # self-check: every pick obeys Travis's rules, or stop
    bad = [r["pick"] for r in picks if r["price"] > CAP or (r["kind"] != "parlay" and (r["p"] > CAP or r["pb"] > CAP))]
    bad += [r["pick"] for r in picks if r["kind"] == "parlay" and any(st in ATTEMPTS for _, st in r["legs"])]
    n_par = sum(r["kind"] == "parlay" for r in picks)
    if bad or n_par < min(MIN_PARLAYS, len(Pq)):
        sys.exit(f"STOP: self-check failed (rule breaks: {bad}; parlays {n_par})")

    # non-attempt alternate for every attempt/completion single
    for r in picks:
        if r["kind"] == "prop" and r["stat"] in ATTEMPTS:
            alt = C[(C.pid == r["pid"]) & (C.stat == ALT_OF[r["stat"]]) & (C.side == r["side"]) & (C["flags"] == "")]
            if len(alt):
                b = alt.sort_values("score", ascending=False).iloc[0]
                ok, why = pricing.rule_ok("over" if b.side == "yes" else "under", b.stat, b.pos)
                r["alternate"] = f"{b.pick} at {b.price * 100:.0f}c (best {b.pb:.0%}, best edge {100 * b.eb:+.1f}){'' if ok else ' [' + why + ']'}"
            else:
                r["alternate"] = "no non-attempt line under the 80% cap"

    # bankroll stakes only for bets that pass the approved rules
    from nflmodel import ledger
    bank = ledger.current_bankroll()
    plan = pricing.plan_game([dict(label=r["pick"], kind=r["kind"], p=r["p"], cost=r["price"] + r["fee"],
                                   stake=round(bank * pricing.STAKE_FRAC / 5) * 5, legs=r["legs"]) for r in picks if r["bankroll"]], bank)
    stake = {b["label"]: b["stake"] for b in plan["bets"]}

    # ---------------- output ----------------
    out = Path(a.out or f"markets/{Path(a.proj).stem}_bestbets_{a.when}.csv")
    allc = pd.concat([C, Pq], ignore_index=True)
    allc.drop(columns=["legs"]).sort_values("score", ascending=False).head(400).to_csv(out, index=False)
    S = run["score"]
    hm, am = float(np.median(S["home"])), float(np.median(S["away"]))
    meta = proj["meta"]
    L_ = [f"# Best bets: {game} ({a.when}, {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
          f"Projection: {away} {am:.0f}, {home} {hm:.0f} | {home} wins {(np.asarray(S['margin']) > 0).mean():.0%} | total {np.median(S['total']):.0f} "
          f"(score sim anchored to the consensus {meta.get('fav')} -{meta.get('spread')}, {meta.get('total')}; the model's own score blend is untested)", "",
          f"Bankroll ${bank:,.2f}: bankroll bets need edge >= {pricing.MIN_EDGE * 100:.0f} pts and CLAUDE.md rules; the rest are picks without a bankroll stake.", "",
          "Ranked on the BEST estimate (20% model + 80% market, the prediction of record). Labels: BANKROLL = passes the approved rules "
          "(model edge >= 10 pts, unders/low-rung, caps); VALUE = best-estimate edge > 0; MODEL LEAN = only the raw model sees an edge; "
          "NO EDGE = neither (listed because Travis asked for 10). Model overs lost money in both test seasons.", "",
          "| # | Bet | Type | Kalshi | Best hit | Model hit | Break-even | Books | Best edge | Model edge | Score | Label | Stake |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(picks, 1):
        lab = ("BANKROLL" if r["pick"] in stake else ("VALUE" if r["eb"] > 0 else ("MODEL LEAN" if r["edge"] > 0 else "NO EDGE")))
        if r["kind"] == "prop" and r.get("low_rung") and r["side"] == "yes":
            lab += ", low-rung over (untested)"
        bk = "" if r.get("books") in (None,) or pd.isna(r.get("books")) else f"{r['books']:.0%}"
        L_.append(f"| {i} | {r['pick']} | {r['kind']} | {100 * r['price']:.1f}c | {r['pb']:.1%} | {r['p']:.1%} | {r['price'] + r['fee']:.1%} | {bk} | "
                  f"{100 * r['eb']:+.1f} | {100 * r['edge']:+.1f} | {r['score']:.1f} | {lab} | {'$' + format(stake[r['pick']], '.0f') if r['pick'] in stake else '-'} |")
        if r.get("alternate"):
            L_.append(f"|  | non-attempt alternate: {r['alternate']} | | | | | | | | | | | |")
    md = "\n".join(L_) + "\n"
    out.with_suffix(".md").write_text(md)
    print(md)
    print(f"saved -> {out} and {out.with_suffix('.md')}")
    return 0


TEAMNAME = {"ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills", "CAR": "Panthers", "CHI": "Bears",
            "CIN": "Bengals", "CLE": "Browns", "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
            "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs", "LV": "Raiders", "LAC": "Chargers",
            "LA": "Rams", "LAR": "Rams", "MIA": "Dolphins", "MIN": "Vikings", "NE": "Patriots", "NO": "Saints",
            "NYG": "Giants", "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SF": "49ers", "SEA": "Seahawks",
            "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proj", required=True)
    ap.add_argument("--kalshi", required=True, help="Kalshi player-prop ladders (kalshi_quotes.py)")
    ap.add_argument("--books", required=True, help="big-book main lines (nfl.py odds)")
    ap.add_argument("--books-alt", help="big-book alt ladders (books' implied rate per rung)")
    ap.add_argument("--kalshi-game", help="saved Kalshi game-line quotes CSV (or where --pull-game saves them)")
    ap.add_argument("--pull-game", action="store_true", help="pull Kalshi moneyline/spread/total now (about 5 credits)")
    ap.add_argument("--when", default="final")
    ap.add_argument("--out")
    ap.add_argument("--leg-pool", type=int, default=28)
    ap.add_argument("--min-ticket", type=float, default=0.05)
    sys.exit(main(ap.parse_args()))
