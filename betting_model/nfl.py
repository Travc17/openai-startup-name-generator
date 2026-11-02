#!/usr/bin/env python3
"""NFL player prop model: receptions, receiving yards, rushing, alt lines, parlays.

  python nfl.py update
  python nfl.py game SEA CHI --week 8 --out "Rashid Shaheed"
  python nfl.py project "Jaxon Smith-Njigba" --opp CHI --week 8 --line rec_yds:99.5:-113:-113 --line rec:7.5:+110
  python nfl.py parlay SEA CHI --week 8 --leg "Jaxon Smith-Njigba:rec_yds:over:89.5" \\
        --leg "D'Andre Swift:rush_yds:under:59.5" --price +240
  python nfl.py build SEA CHI --week 8 --main "Jaxon Smith-Njigba:rec_yds:99.5" \\
        --main "Jaxon Smith-Njigba:rec:7.5" --main "D'Andre Swift:rush_yds:59.5" --legs 2
  python nfl.py backtest --seasons 2024 2025
  python nfl.py log add "JSN o99.5 rec yds" --price -113 --stake 50 --prob 0.55

Stats: targets, rec, rec_yds, rush_att, rush_yds, rec_rush_yds
Prices: American odds (-113, +240) or Robinhood contract cents (53c).
"""
from __future__ import annotations

import argparse
import sys
from itertools import combinations

import numpy as np

from nflmodel import absences, backtest, data, ledger
from nflmodel.game import STAT_LABEL, GameModel, Player, american
from nflmodel.pricing import ev_per_dollar, no_vig, parse_price, stake

CURRENT_SEASON = 2026
HISTORY = [2022, 2023, 2024, 2025, 2026]
ALIASES = {"receptions": "rec", "catches": "rec", "recyds": "rec_yds", "receiving_yards": "rec_yds",
           "rushyds": "rush_yds", "rushing_yards": "rush_yds", "carries": "rush_att", "rushes": "rush_att",
           "rush_rec_yds": "rec_rush_yds", "scrimmage": "rec_rush_yds", "yds": "rec_yds"}
ALT_STEPS = {"rec_yds": [-30, -20, -10, 0, 10, 20, 30], "rush_yds": [-20, -10, 0, 10, 20],
             "rec_rush_yds": [-30, -20, -10, 0, 10, 20, 30], "rec": [-2, -1, 0, 1, 2],
             "targets": [-2, -1, 0, 1, 2], "rush_att": [-4, -2, 0, 2, 4]}


# ---------------- setup ----------------
def build_model() -> GameModel:
    data.ensure_data(HISTORY)
    return GameModel(data.load_targets(HISTORY), data.load_rushes(HISTORY), data.load_positions())


_PLAYERS = None


def lookup(model: GameModel, name: str) -> tuple[str, str]:
    global _PLAYERS
    if _PLAYERS is None:
        _PLAYERS = data.load_players()
    P = _PLAYERS[_PLAYERS.gsis_id.isin(model._pg_by.keys())]
    hit = P[P.display_name.str.lower() == name.lower()]
    if hit.empty:
        hit = P[P.display_name.str.lower().str.contains(name.lower(), regex=False, na=False)]
    if hit.empty:
        sys.exit(f"No player with targets or carries matching '{name}'.")
    if len(hit) > 1:
        sys.exit(f"'{name}' matches several players: " + ", ".join(hit.display_name))
    return hit.iloc[0].gsis_id, hit.iloc[0].display_name


def name_of(pid: str) -> str:
    global _PLAYERS
    if _PLAYERS is None:
        _PLAYERS = data.load_players()
    m = _PLAYERS[_PLAYERS.gsis_id == pid]
    return m.iloc[0].display_name if len(m) else pid


def current_team(model: GameModel, pid: str) -> str:
    return model._pg_by[pid].iloc[-1].posteam


def game_key(model: GameModel, a) -> int:
    if a.week:
        return a.season * 100 + a.week
    return int(model.tg[model.tg.key // 100 == a.season].key.max()) + 1


def stat_name(s: str) -> str:
    s = s.strip().lower()
    s = ALIASES.get(s, s)
    if s not in STAT_LABEL:
        sys.exit(f"Unknown stat '{s}'. Use one of: {', '.join(STAT_LABEL)}")
    return s


def roster_for(model: GameModel, a, key: int, extra: list[str]) -> list[Player]:
    """Usage leaders for both teams plus any named players, minus --out, with news multipliers."""
    team_a, team_b = a.team_a.upper(), a.team_b.upper()
    outs = {lookup(model, n)[0] for n in (a.out or [])}
    mults = {}
    for spec in a.mult or []:
        n, v = spec.rsplit("=", 1)
        mults[lookup(model, n)[0]] = float(v)
    pids = {}
    for t in (team_a, team_b):
        for pid in model.usage_leaders(t, key):
            pids[pid] = t
    for pid in extra:
        team = current_team(model, pid)
        pids[pid] = team if team in (team_a, team_b) else sys.exit(f"{name_of(pid)} last played for {team}, not {team_a}/{team_b}.")
    # Vacated share: teammates absorb only part of it. k fitted on real absences
    # (nflmodel/absences.json): boost = 1 + k * (1 / (1 - vacated) - 1)
    ab = absences.load()
    vac_t, vac_c, first = {team_a: 0.0, team_b: 0.0}, {team_a: 0.0, team_b: 0.0}, {team_a: False, team_b: False}
    for pid in outs:
        team = current_team(model, pid)
        if team not in vac_t:
            continue
        inp = model.player_inputs(Player(pid, team), team_b if team == team_a else team_a, key)
        vac_t[team] += inp["t_share"]
        vac_c[team] += inp["c_share"]
        last_team_game = model.tg[(model.tg.posteam == team) & (model.tg.key < key)].key.max()
        missed_already = model._pg_by[pid].key.max() < last_team_game
        first[team] |= not missed_already
        print(f"OUT: {name_of(pid)} ({team}), vacating {inp['t_share']:.0%} of targets, {inp['c_share']:.0%} of carries"
              f" ({'continuing absence' if missed_already else 'first game missed'})")

    def boost(vac, kind, team):
        if vac <= 0:
            return 1.0
        stage = "first" if first[team] else "continuing"
        k = ab.get(f"{kind}_{stage}_k", ab.get(f"{kind}_first_k", 0.3))
        return 1 + k * (1 / (1 - min(vac, 0.6)) - 1)
    boost_t = {t: boost(vac_t[t], "t", t) for t in vac_t}
    boost_c = {t: boost(vac_c[t], "c", t) for t in vac_c}
    for t in (team_a, team_b):
        if vac_t[t] or vac_c[t]:
            print(f"     {t} teammates: targets x{boost_t[t]:.3f}, carries x{boost_c[t]:.3f} (fitted on real absences)")
    return [Player(pid, t, share_mult=boost_t[t] * mults.get(pid, 1.0), carry_mult=boost_c[t] * mults.get(pid, 1.0))
            for pid, t in pids.items() if pid not in outs]


def parse_leg(model, spec: str) -> tuple[str, str, str, float]:
    parts = spec.split(":")
    if len(parts) != 4:
        sys.exit(f"Leg '{spec}' must be NAME:STAT:over|under:LINE")
    pid, _ = lookup(model, parts[0])
    side = parts[2].lower()
    if side not in ("over", "under"):
        sys.exit("Side must be over or under")
    return pid, stat_name(parts[1]), side, float(parts[3])


def hits(sim, pid, stat, side, line) -> np.ndarray:
    v = sim["players"][pid][stat]
    return v > line if side == "over" else v < line


def leg_label(pid, stat, side, line) -> str:
    return f"{name_of(pid)} {side} {line:g} {STAT_LABEL[stat]}"


# ---------------- commands ----------------
def cmd_game(a):
    model = build_model()
    key = game_key(model, a)
    extra = [lookup(model, n)[0] for n in (a.players or [])]
    roster = roster_for(model, a, key, extra)
    if a.players:
        roster = [p for p in roster if p.pid in extra]
    sim = model.simulate(a.team_a.upper(), a.team_b.upper(), key, roster)
    for team, (mt, mr) in sim["team_mu"].items():
        print(f"{team}: projected {mt:.1f} targets, {mr:.1f} rushes")
    print(f"\n{'player':<24}{'tm':<5}{'stat':<17}{'10th':>6}{'25th':>6}{'MED':>6}{'75th':>6}{'90th':>6}{'mean':>7}")
    for p in roster:
        s, info = sim["players"][p.pid], sim["info"][p.pid]
        stats = (["targets", "rec", "rec_yds"] if info["t_share"] >= 0.08 else []) + \
                (["rush_att", "rush_yds"] if info["c_share"] >= 0.15 else [])
        if info["t_share"] >= 0.08 and info["c_share"] >= 0.15:
            stats.append("rec_rush_yds")
        for i, st in enumerate(stats):
            q = np.quantile(s[st], [.1, .25, .5, .75, .9])
            nm = name_of(p.pid) if i == 0 else ""
            print(f"{nm:<24}{p.team if i == 0 else '':<5}{STAT_LABEL[st]:<17}" + "".join(f"{v:>6.0f}" for v in q) + f"{s[st].mean():>7.1f}")
    print("\nNews is manual: --out NAME for players ruled out, --mult 'NAME=1.1' for role changes.")


def cmd_project(a):
    model = build_model()
    pid, name = lookup(model, a.player)
    team = (a.team or current_team(model, pid)).upper()
    a.team_a, a.team_b = team, a.opp.upper()
    key = game_key(model, a)
    roster = roster_for(model, a, key, [pid])
    sim = model.simulate(team, a.opp.upper(), key, roster)
    s, info = sim["players"][pid], sim["info"][pid]
    rec = info["recent"]
    print(f"\n{name} ({info['pos']}, {team}) vs {a.opp.upper()}  [{info['games']} games of history]")
    print("Recent games (targets/rec/rec yds | carries/rush yds): " + ", ".join(
        f"{int(r.targets)}/{int(r.rec)}/{int(r.rec_yds)}|{int(r.rush_att)}/{int(r.rush_yds)}" for r in rec.itertuples()))
    print(f"Inputs: target share {info['t_share']:.1%}, carry share {info['c_share']:.1%}, catch rate {info['catch']:.0%}, "
          f"yds/target {info['ypt']:.1f}, yds/carry {info['ypc']:.1f}, opp factor rec x{info['rec_mult']:.2f} rush x{info['rush_mult']:.2f}")
    for st in ("targets", "rec", "rec_yds", "rush_att", "rush_yds"):
        if s[st].mean() >= 0.5:
            q = np.quantile(s[st], [.1, .25, .5, .75, .9])
            print(f"  {STAT_LABEL[st]:<16} 10th {q[0]:.0f} | 25th {q[1]:.0f} | MEDIAN {q[2]:.0f} | 75th {q[3]:.0f} | 90th {q[4]:.0f}   mean {s[st].mean():.1f}")
    if a.line:
        print(f"\n{'bet':<28}{'model':>7}{'price':>7}{'b/e':>7}{'edge':>7}{'EV/$':>7}{'mkt':>7}  decision")
    for spec in a.line or []:
        parts = spec.split(":")
        st, line = stat_name(parts[0]), float(parts[1])
        po = float((s[st] > line).mean())
        over = parse_price(parts[2], a.fee) if len(parts) > 2 else None
        under = parse_price(parts[3], a.fee) if len(parts) > 3 else None
        mkt = f"{no_vig(over, under):.0%}" if over and under else ""
        for side, p, pr in (("over", po, over), ("under", 1 - po, under)):
            lab = f"{side} {line:g} {STAT_LABEL[st]}"
            if pr is None:
                print(f"{lab:<28}{p:>7.1%}   fair {american(p)}")
                continue
            amt, why = stake(p, pr, bankroll=a.bankroll)
            print(f"{lab:<28}{p:>7.1%}{pr.raw:>7}{pr.breakeven:>7.1%}{p - pr.breakeven:>+7.1%}{ev_per_dollar(p, pr):>+7.1%}"
                  f"{mkt if side == 'over' else '':>7}  {('$%d ' % amt) if amt else ''}{why}")


def cmd_parlay(a):
    model = build_model()
    key = game_key(model, a)
    legs = [parse_leg(model, l) for l in a.leg]
    roster = roster_for(model, a, key, [l[0] for l in legs])
    sim = model.simulate(a.team_a.upper(), a.team_b.upper(), key, roster)
    ind = 1.0
    joint = np.ones(len(next(iter(sim["players"].values()))["rec"]), dtype=bool)
    print()
    for pid, st, side, line in legs:
        h = hits(sim, pid, st, side, line)
        ind *= h.mean()
        joint &= h
        print(f"  {leg_label(pid, st, side, line):<50} {h.mean():>6.1%}  fair {american(h.mean())}")
    pj = float(joint.mean())
    print(f"\nJoint probability {pj:.1%} (fair {american(pj)})   if legs were independent {ind:.1%} (fair {american(ind)})"
          f"   correlation lift x{pj / ind:.2f}")
    if a.price:
        pr = parse_price(a.price, a.fee)
        amt, why = stake(pj, pr, bankroll=a.bankroll)
        print(f"Price {pr.raw}: break even {pr.breakeven:.1%}, edge {pj - pr.breakeven:+.1%}, EV {ev_per_dollar(pj, pr):+.1%} per $1"
              f"  ->  {('$%d ' % amt) if amt else ''}{why}")
    else:
        print("Add --price to get an edge and stake.")


def cmd_build(a):
    model = build_model()
    key = game_key(model, a)
    mains = []
    for spec in a.main:
        parts = spec.split(":")
        if len(parts) != 3:
            sys.exit(f"--main '{spec}' must be NAME:STAT:LINE")
        mains.append((lookup(model, parts[0])[0], stat_name(parts[1]), float(parts[2])))
    roster = roster_for(model, a, key, [m[0] for m in mains])
    sim = model.simulate(a.team_a.upper(), a.team_b.upper(), key, roster, n_sims=a.sims)
    print(f"Simulated the game {a.sims:,} times.")

    cands = []
    print("\nALT LADDERS (model probability, fair odds)")
    for pid, st, main in mains:
        print(f"  {name_of(pid)}: {STAT_LABEL[st]} (main {main:g})")
        for step in ALT_STEPS[st]:
            line = main + step
            if line <= 0:
                continue
            po = float((sim["players"][pid][st] > line).mean())
            tag = "  <- main" if step == 0 else ""
            print(f"     {line:>6g}   over {po:>6.1%} ({american(po):>6})   under {1 - po:>6.1%} ({american(1 - po):>6}){tag}")
            for side in ("over", "under"):
                if a.lower_only and not (side == "over" and step < 0):
                    continue
                h = hits(sim, pid, st, side, line)
                if a.min_leg <= h.mean() <= a.max_leg:
                    cands.append(((pid, st, side, line), h))

    lo, _, hi = a.legs.partition("-")
    sizes = range(int(lo), int(hi or lo) + 1)
    for size in sizes:
        combos = []
        for combo in combinations(cands, size):
            keys = [(c[0][0], c[0][1]) for c in combo]
            if len(set(keys)) < len(keys):  # one line per player stat
                continue
            if a.cross_player_only and len({k[0] for k in keys}) < len(keys):
                continue
            joint = np.logical_and.reduce([c[1] for c in combo]).mean()
            ind = np.prod([c[1].mean() for c in combo])
            if a.min_prob <= joint <= a.max_prob and ind > 0:
                combos.append((joint / ind if a.rank == "lift" else joint, joint, ind, [c[0] for c in combo]))
        combos.sort(key=lambda x: -x[0])
        print(f"\nTOP {size} LEG PARLAYS by {'correlation lift' if a.rank == 'lift' else 'hit probability'} "
              f"(joint {a.min_prob:.0%} to {a.max_prob:.0%}, {len(combos):,} combos checked)")
        for score, joint, ind, legs in combos[:a.top]:
            print(f"  joint {joint:.1%}  fair {american(joint):>6}   (if independent {ind:.1%}, lift x{joint / ind:.2f})")
            for l in legs:
                print(f"        {leg_label(*l)}  [{hits(sim, *l).mean():.0%}]")
        if not combos:
            print("  No combos in range. Widen --min-prob/--max-prob or add more --main lines.")
    print("\nOnly bet a parlay if the offered price beats FAIR by your 2% edge rule: "
          "python nfl.py parlay ... --price <odds>")


def cmd_backtest(a):
    model = build_model()
    rho = None
    if a.fit:
        _, tr = backtest.run(model, a.fit)
        rho = backtest.fit_copula(tr, a.fit)
        print(f"Copula fitted on {a.fit}: {rho}\n")
    marg, pairs = backtest.run(model, a.seasons, rho=rho, limit_games=a.limit)
    print(backtest.report(marg, pairs))


def cmd_update(a):
    data.ensure_data(HISTORY, refresh_seasons=[CURRENT_SEASON])
    print(f"Refreshed {CURRENT_SEASON} play by play and player list.")


def cmd_log(a):
    if a.action == "add":
        print(f"Logged bet #{ledger.add(a.bet, a.price, a.stake, a.prob, a.sport, a.notes or '')}")
    elif a.action == "settle":
        r = ledger.settle(int(a.bet), a.result, a.close)
        print(f"Settled #{r['id']}: {r['result']} {r['pnl']}")
    print(ledger.summary(a.bankroll))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, teams=True):
        if teams:
            sp.add_argument("team_a")
            sp.add_argument("team_b")
        sp.add_argument("--season", type=int, default=CURRENT_SEASON)
        sp.add_argument("--week", type=int, help="Week being projected (default: next week in the data)")
        sp.add_argument("--out", action="append", help="Player ruled out (repeatable)")
        sp.add_argument("--mult", action="append", help="'NAME=1.10' share multiplier for role news")
        sp.add_argument("--fee", type=float, default=0.0, help="Fee per $1 contract, e.g. 0.01")
        sp.add_argument("--bankroll", type=float, default=2000)

    g = sub.add_parser("game", help="Projections for every key player in a game")
    common(g)
    g.add_argument("--players", nargs="+")
    g.set_defaults(func=cmd_game)

    pr = sub.add_parser("project", help="One player, priced lines")
    common(pr, teams=False)
    pr.add_argument("player")
    pr.add_argument("--opp", required=True)
    pr.add_argument("--team")
    pr.add_argument("--line", action="append", help="STAT:LINE[:OVER[:UNDER]], e.g. rec_yds:99.5:-113:-113")
    pr.set_defaults(func=cmd_project)

    pa = sub.add_parser("parlay", help="Price a specific parlay")
    common(pa)
    pa.add_argument("--leg", action="append", required=True, help="NAME:STAT:over|under:LINE")
    pa.add_argument("--price", help="Offered parlay price, e.g. +240 or 28c")
    pa.set_defaults(func=cmd_parlay)

    b = sub.add_parser("build", help="Alt line ladders and best correlated parlays")
    common(b)
    b.add_argument("--main", action="append", required=True, help="NAME:STAT:MAIN_LINE")
    b.add_argument("--legs", default="2", help="Leg count or range, e.g. 3 or 3-5")
    b.add_argument("--sims", type=int, default=20000)
    b.add_argument("--lower-only", action="store_true", help="Only overs at alt lines BELOW the book line")
    b.add_argument("--rank", choices=["lift", "prob"], default="lift")
    b.add_argument("--top", type=int, default=10)
    b.add_argument("--min-leg", type=float, default=0.30, help="Skip legs less likely than this")
    b.add_argument("--max-leg", type=float, default=0.90)
    b.add_argument("--min-prob", type=float, default=0.15)
    b.add_argument("--max-prob", type=float, default=0.60)
    b.add_argument("--cross-player-only", action="store_true",
                   help="Skip same player combos (books already price receptions+yards correlation)")
    b.set_defaults(func=cmd_build)

    bt = sub.add_parser("backtest")
    bt.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025])
    bt.add_argument("--fit", type=int, nargs="+", help="Refit copula on these seasons first")
    bt.add_argument("--limit", type=int, help="Max games (quick check)")
    bt.set_defaults(func=cmd_backtest)

    sub.add_parser("update").set_defaults(func=cmd_update)

    lg = sub.add_parser("log")
    lg.add_argument("action", choices=["add", "settle", "summary"])
    lg.add_argument("bet", nargs="?")
    lg.add_argument("result", nargs="?", choices=["win", "loss", "push"])
    lg.add_argument("--price")
    lg.add_argument("--stake", type=float, default=50)
    lg.add_argument("--prob", type=float)
    lg.add_argument("--close")
    lg.add_argument("--sport", default="NFL")
    lg.add_argument("--notes")
    lg.add_argument("--bankroll", type=float, default=2000)
    lg.set_defaults(func=cmd_log)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
