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
import json
import re
import sys
from itertools import combinations

import numpy as np

from nflmodel import absences, backtest, data, depth, ledger, market, picks, projections, report, returns, routes, scores
from nflmodel.game import POS_GROUP, STAT_LABEL, GameModel, Player, american
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
    m = GameModel(data.load_targets(HISTORY), data.load_rushes(HISTORY), data.load_positions(),
                  snaps=data.load_snaps(HISTORY))
    if DEFENSE:
        m.cfg.def_mode = DEFENSE
    from nflmodel.qb import QBModel
    m.qbm = QBModel(data.load_passes(list(range(2019, CURRENT_SEASON + 1))))
    m.coach = data.load_coaches(HISTORY)
    try:
        pff, team = routes.load([s for s in HISTORY if s >= 2023])
        m.route_role = routes.RouteRole(pff, team, m.pg)
    except FileNotFoundError:
        m.route_role = None
    return m


DEFENSE = None


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
    outs = {lookup(model, n)[0] for n in (a.out or [])} | set(getattr(a, "out_pids", None) or ())   # out_pids: lab bench
    catches = {}
    for spec in getattr(a, "catch", None) or []:
        n, v = spec.rsplit("=", 1)
        catches[lookup(model, n)[0]] = float(v)
        print(f"CATCH RATE OVERRIDE: {n} = {float(v):.0%}")
    mults = {}
    for spec in a.mult or []:
        n, v = spec.rsplit("=", 1)
        mults[lookup(model, n)[0]] = float(v)
    pids = {}
    for t in (team_a, team_b):
        for pid in model.usage_leaders(t, key):
            pids[pid] = t
    # Depth chart: add today's starters the usage history misses (e.g. a back returning from IR)
    dep = depth_status(model, a, key, (team_a, team_b))
    # Rank among players who are not ruled out (GB at NE 2026-11-08: Kaleb Johnson was RB4 behind the
    # inactive MarShawn Lloyd, so the RB-top-3 rule skipped him; he took 14 carries)
    eff = {}
    for pid, (now, prev, rank, pos, team) in dep.items():
        eff[pid] = rank - sum(1 for q, v in dep.items() if q in outs and v[3] == pos and v[4] == team and v[2] < rank)
    for pid, (now, prev, rank, pos, team) in dep.items():
        rank = eff[pid]
        top = now or (pos == "RB" and rank <= 3) or (pos == "WR" and rank <= 4)
        # history BEFORE this game (in a replay a rookie's only rows can be this very game: 2026-11-11 lab bench)
        if top and pos in ("WR", "TE", "RB") and pid in model._pg_by and model._pg_by[pid].key.min() < key and pid not in outs:
            pids.setdefault(pid, team)
    for pid in extra:
        team = current_team(model, pid)
        pids[pid] = team if team in (team_a, team_b) else sys.exit(f"{name_of(pid)} last played for {team}, not {team_a}/{team_b}.")
    # Every skill player with offensive snaps in the team's last 2 games (Travis, 2026-11-03): depth
    # players get their own share instead of being left out of the box score and the prop coverage.
    # A/B on 2025 wks 6-13: leaders unchanged (all stats |change| < 0.1%, |t| < 1.1); depth players'
    # upper tails too thin (<p90 coverage 82-84%), so they are auto blind spots (shown, never bet).
    a.depth_added = set()
    if not getattr(a, "leaders_only", False):
        for t in (team_a, team_b):
            for pid in model.active_players(t, key):
                if pid not in outs and pid not in pids:
                    pids[pid] = t
                    a.depth_added.add(pid)
    # Vacated share: teammates absorb only part of it. k fitted on real absences
    # (nflmodel/absences.json): boost = 1 + k * (1 / (1 - vacated) - 1)
    ab = absences.load()
    # Next man up: vacated share by position; same-position teammates absorb more (fitted on real absences)
    vac_t = {team_a: {}, team_b: {}}
    vac_c = {team_a: {}, team_b: {}}
    first = {team_a: False, team_b: False}
    for pid in outs:
        team = current_team(model, pid)
        if team not in vac_t:
            continue
        inp = model.player_inputs(Player(pid, team), team_b if team == team_a else team_a, key)
        tk = model.tg[(model.tg.posteam == team) & (model.tg.key < key)].key.unique()
        weeks_missed = int((tk > model._pg_by[pid].key.max()).sum())
        if weeks_missed >= 2:
            print(f"OUT: {name_of(pid)} ({team}) has missed {weeks_missed} straight games: no boost, "
                  "teammates' recent games already reflect it (absence data only supports weeks 1-2)")
            continue
        pos = inp["pos"]
        vac_t[team][pos] = vac_t[team].get(pos, 0) + inp["t_share"]
        vac_c[team][pos] = vac_c[team].get(pos, 0) + inp["c_share"]
        first[team] |= weeks_missed == 0
        print(f"OUT: {name_of(pid)} ({team} {pos}), vacating {inp['t_share']:.0%} of targets, {inp['c_share']:.0%} of carries"
              f" ({'first game missed' if weeks_missed == 0 else 'continuing absence'})")

    def boost_for(team, pos, kind):
        vac = vac_t[team] if kind == "t" else vac_c[team]
        if not vac:
            return 1.0
        stage = "first" if first[team] else "continuing"
        same = vac.get(pos, 0.0)
        other = sum(v for p_, v in vac.items() if p_ != pos)
        b = lambda v: 1 / (1 - min(v, 0.6)) - 1
        ks = ab.get(f"{kind}_{stage}_k_same", ab.get(f"{kind}_{stage}_k", 0.3))
        ko = ab.get(f"{kind}_{stage}_k_other", ab.get(f"{kind}_{stage}_k", 0.3))
        return 1 + ks * b(same) + ko * b(other)

    dp = depth.load()
    players = []
    for pid, t in pids.items():
        if pid in outs:
            continue
        dm_t, dm_c = 1.0, 1.0
        nth = games_back(model, pid, t, key)
        rp = returns.load()
        if nth:
            dm_t, dm_c = rp.get(f"t_game{nth}", 1.0), rp.get(f"c_game{nth}", 1.0)
            print(f"RETURN: {name_of(pid)} ({t}) game {nth} back from a long absence: "
                  f"targets x{dm_t:.2f}, carries x{dm_c:.2f} (fitted on real returns)")
        elif pid in dep:
            now, prev, rank, pos, _ = dep[pid]
            change = "promoted" if now and not prev else ("demoted" if prev and not now else "same")
            dm_t, dm_c = depth.multipliers(dp, change)
            if change != "same":
                print(f"DEPTH: {name_of(pid)} ({t}) {change} ({pos}{rank}): targets x{dm_t:.2f}, carries x{dm_c:.2f}")
        rm = 1.0
        rr = getattr(model, "route_role", None)
        if rr is not None:
            try:
                inp0 = model.player_inputs(Player(pid, t), team_b if t == team_a else team_a, key)
                es = rr.expected_share(pid, t, key, inp0["pos"])
                if es is not None and inp0["t_share"] > 0.01:
                    rm = float(np.clip((0.5 * es + 0.5 * inp0["t_share"]) / inp0["t_share"], 0.4, 2.5))
                    if abs(rm - 1) >= 0.15:
                        print(f"ROUTES: {name_of(pid)} ({t}) route-based role x{rm:.2f} (recent routes/dropback vs target history)")
            except ValueError:
                pass
        ppos = POS_GROUP.get(model.pos.get(pid, "WR"), "WR")
        bt, bc = boost_for(t, ppos, "t"), boost_for(t, ppos, "c")
        if bt > 1.02 or bc > 1.02:
            print(f"NEXT MAN UP: {name_of(pid)} ({t} {ppos}) targets x{bt:.2f}, carries x{bc:.2f}")
        players.append(Player(pid, t, share_mult=bt * dm_t * rm * mults.get(pid, 1.0),
                              carry_mult=bc * dm_c * mults.get(pid, 1.0), catch_rate=catches.get(pid)))
    return players


def games_back(model: GameModel, pid: str, team: str, key: int, min_missed: int = 4) -> int:
    """1 or 2 if this is the player's 1st/2nd game back after missing min_missed+ team games."""
    h = model._pg_by.get(pid)
    if h is None:
        return 0
    keys = sorted(h[h.key < key].key)
    if not keys:
        return 0
    tk = sorted(model.tg[(model.tg.posteam == team) & (model.tg.key < key)].key.unique())
    missed_now = sum(1 for k in tk if k > keys[-1])
    if missed_now >= min_missed:
        return 1
    if len(keys) >= 2 and missed_now == 0:
        gap = sum(1 for k in tk if keys[-2] < k < keys[-1])
        if gap >= min_missed and keys[-1] // 100 == key // 100:
            return 2
    return 0


NOT_ACTIVE = ("not on the active roster", "not activated", "on injured reserve", "on reserve", "not yet activated")
ACTIVE_WORDS = ("active", "activated", "off ir", "returns", "return from", "designated to return", "elevated", "will play", "starting")


def roster_check(model: GameModel, news: list, roster: list, a) -> list[str]:
    """Every RB/WR/TE the news lists as active, activated, off IR or elevated must be in the sims.
    GB at NE 2026-11-08: Mack Hollins (first game back from IR) was 'active' in the news file but not in the
    roster (no snaps in the last 2 games), so his ~5 targets went to teammates. Prints a loud warning;
    fix with --players "Name" (and --blind "Name" for a first game back)."""
    have = {p.pid for p in roster}
    outs = {lookup(model, n)[0] for n in (a.out or [])}
    missing = []
    for it in (news.get("items", []) if isinstance(news, dict) else news) or []:
        st, tm = str(it.get("status", "")).lower(), str(it.get("team", "")).upper()
        if not any(w in st for w in ACTIVE_WORDS) or "inactive" in st or not any(p in tm for p in ("RB", "WR", "TE")) \
                or any(x in st for x in NOT_ACTIVE):   # 2026-11-13: "not on the active roster" matched "active" (Iosivas)
            continue
        try:
            pid = lookup(model, it.get("player", ""))[0]
        except SystemExit:
            continue
        if pid not in have and pid not in outs and pid not in missing:
            missing.append(pid)
            print(f"ROSTER CHECK: {name_of(pid)} ({tm}) is '{it.get('status')}' in the news but NOT in the sims. "
                  f"Rerun with --players \"{name_of(pid)}\" --blind \"{name_of(pid)}\" (source: {it.get('url', 'no url')})")
    # The other direction: a player the news lists as inactive/out who is still in the sims without --out
    # (week 9 grade: five depth backs/TEs predicted, none played, none ruled out)
    for it in (news.get("items", []) if isinstance(news, dict) else news) or []:
        st = str(it.get("status", "")).lower()
        if not re.search(r"(^|[^a-z])(inactive|out)\b(?!s)", st) or "not on the" in st or "no designation" in st \
                or any(x in st for x in ("treated as playing", "kept in the sims")):   # 2026-11-12 false hits (Skattebo, Jefferson)
            continue
        try:
            pid = lookup(model, it.get("player", ""))[0]
        except SystemExit:
            continue
        if pid in have and pid not in outs:
            print(f"INACTIVE CHECK: {name_of(pid)} is '{it.get('status')}' in the news but still in the sims. Rerun with --out \"{name_of(pid)}\"")
    a.roster_missing = missing
    return missing


def reserve_check(model: GameModel, roster: list, key: int) -> list[str]:
    """Players in the sims whom nflverse weekly rosters list on RESERVE (IR, PUP, NFI) for this week. WAS at NYG
    2026-11-12: Dyami Brown went on reserve in week 9 but still had week-8 snaps, so the recent-snaps rule kept him."""
    import pandas as pd
    f = data.DATA_DIR / f"roster_weekly_{key // 100}.parquet"
    try:
        r = pd.read_parquet(f, columns=["week", "team", "gsis_id", "status"])
    except (FileNotFoundError, OSError):
        print(f"RESERVE CHECK skipped: {f.name} not downloaded (python -c 'from nflmodel import data; data.ensure_rosters()')")
        return []
    res = set(r[(r.week == key % 100) & (r.status == "RES")].gsis_id)
    hits = [p.pid for p in roster if p.pid in res]
    for pid in hits:
        print(f"RESERVE CHECK: {name_of(pid)} is on reserve (nflverse weekly roster, week {key % 100}) but in the sims. Rerun with --out \"{name_of(pid)}\"")
    return hits


def depth_status(model: GameModel, a, key: int, teams) -> dict:
    """Starter status from the depth chart on game day vs at each team's previous game."""
    import pandas as pd
    season = key // 100
    try:
        raw = pd.read_parquet(data.DATA_DIR / f"depth_charts_{season}.parquet")
    except FileNotFoundError:
        return {}
    if "dt" not in raw.columns:
        return {}
    gd = data.game_dates([season])
    # Game day: this week's game date when the game is already in the data (a replay after the game), so the
    # chart is the one published by kickoff; live (game not played yet) it is the newest chart. Using the newest
    # chart in a replay read post-game depth charts (2026-11-08 replay mismatch, reviews/lessons.csv).
    wk = gd[(gd.season == season) & (gd.week == key % 100) & (gd.home_team.isin(teams) | gd.away_team.isin(teams))]
    today = getattr(a, "date", None) or (wk.game_date.min() if len(wk) else raw.dt.str[:10].max())
    out = {}
    for team in teams:
        prev = gd[((gd.home_team == team) | (gd.away_team == team)) & (gd.game_date < today)].game_date.max()
        if not isinstance(prev, str):
            continue
        for pid, (now, was, rank, pos) in depth.current_status(raw, team, today, prev).items():
            out[pid] = (now, was, rank, pos, team)
    return out


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
          f"yds/target {info['ypt']:.1f}, yds/carry {info['ypc']:.1f}")
    team_f = model._opp_mult(a.opp.upper(), key, "rec")
    print(f"Defense: {a.opp.upper()} overall pass factor x{team_f:.2f} -> vs {info['pos']}s x{info['rec_mult']:.2f} "
          f"(lever: {model.cfg.def_mode}), run factor x{info['rush_mult']:.2f}")
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


def cmd_gameline(a):
    """Market anchored score simulation: spread, total, team totals, moneyline, alt lines."""
    home, away = a.home.upper(), a.away.upper()
    fav = a.fav.upper()
    spread_line = a.spread if fav == home else -a.spread   # expected HOME margin
    g, tg = scores.load_games(HISTORY)
    resid = scores.market_residuals(g, a.season + 1)
    sim = scores.market_simulate(spread_line, a.total, resid, n=a.sims)
    H, A, M, T = sim["home"], sim["away"], sim["margin"], sim["total"]
    print(f"\n{away} at {home}: anchor {fav} -{a.spread:g}, total {a.total:g} ({a.sims:,} sims; anchor = big-book consensus line)")
    print(f"Typical score: {home} {np.median(H):.0f}, {away} {np.median(A):.0f}   "
          f"(most common margins: " + ", ".join(f"{home} {int(v):+d} ({c/len(M):.1%})" for v, c in
          zip(*np.unique(M, return_counts=True)) if c / len(M) >= 0.05) + ")")
    print(f"Win probability: {home} {(M > 0).mean():.1%}, {away} {(M < 0).mean():.1%}, tie {(M == 0).mean():.1%}")
    print(f"Fair moneyline: {home} {american((M > 0).mean() / max((M != 0).mean(), 1e-9))}, {away} {american((M < 0).mean() / max((M != 0).mean(), 1e-9))}")
    fm = M if fav == home else -M
    print(f"\nALT SPREADS ({fav})                       ALT TOTALS")
    spreads = [-10.5, -7.5, -6.5, -3.5, -a.spread, -2.5, -1.5, 1.5, 2.5, 3.5, 6.5, 7.5]
    totals = [a.total + k for k in (-10, -7, -3, 0, 3, 7, 10)]
    for i, line in enumerate(sorted(set(spreads))):
        win, push = (fm + line > 0).mean(), (fm + line == 0).mean()
        txt = f"  {fav} {line:+g}: {win:6.1%}" + (f" (+{push:.1%} push)" if push else "            ")
        if i < len(totals):
            tl = totals[i]
            ov, tp = (T > tl).mean(), (T == tl).mean()
            txt += f"     over {tl:g}: {ov:6.1%}" + (f" (+{tp:.1%} push)" if tp else "")
        print(txt)
    print("\nTEAM TOTALS")
    for team, pts in ((home, H), (away, A)):
        med = np.median(pts)
        print(f"  {team}: median {med:.0f}   " + "   ".join(f"{x}+ {(pts >= x).mean():.0%}" for x in
              [int(med) - 7, int(med) - 3, int(med), int(med) + 3, int(med) + 7] if x > 0))
    for spec in a.line or []:
        # TEAM:SPREAD:PRICE (e.g. BAL:-6.5:40c), OVER:41.5:52c, UNDER:41.5:50c, TEAM:ML:60c, TEAM:TT:20.5:50c
        parts = spec.split(":")
        kind = parts[0].upper()
        if kind in ("OVER", "UNDER"):
            x, pr = float(parts[1]), parse_price(parts[2], a.fee)
            p = (T > x).mean() if kind == "OVER" else (T < x).mean()
            lab = f"{kind.lower()} {x:g}"
        elif parts[1].upper() == "ML":
            pts_for = M if kind == home else -M
            p, pr, lab = (pts_for > 0).mean(), parse_price(parts[2], a.fee), f"{kind} to win"
        elif parts[1].upper() == "TT":
            pts = H if kind == home else A
            x, pr = float(parts[2]), parse_price(parts[3], a.fee)
            p, lab = (pts > x).mean(), f"{kind} team total over {x:g}"
        else:
            x, pr = float(parts[1]), parse_price(parts[2], a.fee)
            pts_for = M if kind == home else -M
            p, lab = (pts_for + x > 0).mean(), f"{kind} {x:+g}"
        if kind not in ("OVER", "UNDER") and parts[1].upper() not in ("ML", "TT"):
            push = (pts_for + x == 0).mean()
        elif kind in ("OVER", "UNDER"):
            push = (T == x).mean()
        else:
            push = 0.0
        p = p / (1 - push) if push < 1 else p   # pushes refund: grade on decided outcomes
        amt, why = stake(p, pr, bankroll=a.bankroll)
        lab += f" (push {push:.0%})" if push else ""
        print(f"  {lab:<28} model {p:.1%}  price {pr.raw} (b/e {pr.breakeven:.1%})  edge {p - pr.breakeven:+.1%}  "
              f"-> {('$%d ' % amt) if amt else ''}{why}")
    print("\nNote: centered on the big-book consensus line (my independent score model lost to closing lines in backtests).\n"
          "Edges appear when Robinhood prices disagree with the big books.")


def cmd_report(a):
    """Full game report (news, score, lines, box score, top singles/parlays, best bet) as HTML + JSON."""
    model = build_model()
    a.team_a, a.team_b = a.home.upper(), a.away.upper()
    key = game_key(model, a)
    roster = roster_for(model, a, key, [lookup(model, n)[0] for n in (a.players or [])])
    board = report.load_board(a.board)
    news = report.load_news(a.news)
    roster_check(model, news, roster, a)
    reserve_check(model, roster, key)
    blind = set(a.blind or [])
    for pid in sorted(getattr(a, "depth_added", ())):
        print(f"DEPTH ADD: {name_of(pid)} (recent snaps; auto blind spot until depth-player tails are calibrated)")
        blind.add(name_of(pid))
    qbs = {t: model.qbm.starter(t, key) for t in (a.team_a, a.team_b)}
    for spec in a.qb or []:
        t, n = spec.split("=", 1)
        qbs[t.upper()] = lookup(model, n)[0]
    for t, q in qbs.items():
        if q:
            qy, qc, nq = model.qbm.adjustment(q, t, key)
            print(f"QB: {name_of(q)} ({t}) receivers x{qy:.2f} yards, x{qc:.2f} completions ({nq} recent targeted attempts)")
            if q in model._pg_by and q not in [p.pid for p in roster]:
                roster.append(Player(q, t))
    rep = report.build(model, name_of, lambda n: lookup(model, n)[0], roster, a.team_a, a.team_b, key, a.sims,
                       board, news, a.bankroll, a.fee, fav=(a.fav or "").upper() or None, spread=a.spread,
                       total=a.total, model_line=a.model_line, blind=blind, qbs=qbs, wind=a.wind, rain=getattr(a, 'rain', False))
    title = a.title or f"{a.team_b} at {a.team_a} Report"
    proj = rep.pop("projections")
    # every manual input, so later reviews can grade whether human adjustments helped or hurt
    proj["meta"]["adjustments"] = {"out": a.out or [], "mult": a.mult or [], "catch": a.catch or [],
                                   "blind": sorted(blind), "qb_override": a.qb or [], "sims": a.sims}
    proj_path = a.proj or a.html.rsplit(".", 1)[0] + ".proj.json"
    projections.save(proj, proj_path)
    print(f"Projections (no prices, for `nfl.py price`): {proj_path}")
    with open(a.html, "w") as f:
        f.write(report.render(rep, title))
    brief_path = a.html.rsplit(".", 1)[0] + ".canva.txt"
    with open(brief_path, "w") as f:
        f.write(report.canva_brief(rep, title))
    print(f"Canva brief (numbers straight from this report): {brief_path}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(rep, f, indent=1, default=float)
    played = ((model.tg.key == key) & model.tg.posteam.isin([a.away.upper(), a.home.upper()])).any()
    if played and not a.no_log:
        print("Paper-trading log: NOT logged, this game is already in the play by play (picks must be logged before kickoff)")
    elif not a.no_log:
        n = picks.log_report(rep, key)
        print(f"Paper-trading log: {n} qualifying picks recorded (betting_model/picks_log.csv)")
    b = rep.get("best")
    print(f"Wrote {a.html}. Best bet: " + (f"{b['label']} ${b['stake']} (edge {b['edge']*100:+.1f})" if b else "none"))


def cmd_price(a):
    """Layer 3: compare one game's projections with every quote from every venue."""
    import csv
    proj = projections.load(a.proj)
    fees = {k.lower(): float(v) for k, v in (f.split("=", 1) for f in (a.fee or []))}
    quotes = market.load_quotes(a.quotes, fees) if a.quotes else []
    if a.board:
        quotes += market.from_board(report.load_board(a.board), fees)
    rows = market.find(proj, quotes, a.min_edge)    # blind spots and TD/INT are kept out of bets inside find()
    print(f"{proj['game']} projections made {proj['made_utc']} ({proj['sims']} sims); {len(quotes)} quotes, "
          f"{sum(1 for k in market.market_probs(quotes))} lines with a two-sided big-book price")
    print(market.table(rows, a.top))
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {a.csv}")


def cmd_odds(a):
    """Pull big-book player prop lines (The Odds API) into a quotes CSV for `price`."""
    from nflmodel import odds_api
    rows, hdr, kick = odds_api.fetch(a.away, a.home, alt=a.alt)
    props = [r for r in rows if r["stat"] not in ("spreads", "totals")]
    game = [r for r in rows if r["stat"] in ("spreads", "totals")]
    odds_api.save(props, a.out)
    print(f"{a.away.upper()} at {a.home.upper()} (kickoff {kick}): {len(props)} prop quotes from "
          f"{len({r['venue'] for r in props})} books -> {a.out}; {odds_api.credits(hdr)}")
    two = {}
    for r in props:
        two.setdefault((r["venue"], r["player"], r["stat"], r["line"]), set()).add(r["side"])
    print(f"Lines with both sides priced: {sum(1 for s in two.values() if len(s) == 2)} of {len(two)}")
    if game:
        gl = a.out.rsplit(".", 1)[0] + "_gamelines.csv"
        odds_api.save(game, gl)
        tot = sorted(r["line"] for r in game if r["stat"] == "totals" and r["side"] == "over")
        sp = sorted(r["line"] for r in game if r["stat"] == "spreads" and r["player"] == odds_api.TEAMS[a.home.upper()])
        if tot and sp:
            print(f"Big-book consensus (median): {a.home.upper()} spread {sp[len(sp) // 2]:+g}, total {tot[len(tot) // 2]:g} -> {gl}")


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
    try:
        n = routes.refresh_pff(CURRENT_SEASON)
        print(f"PFF weekly receiving data refreshed ({n} weeks).")
    except Exception as e:
        print(f"PFF refresh skipped: {e}")
    try:
        data.ensure_rosters([CURRENT_SEASON])   # weekly roster status (reserve check)
    except Exception as e:
        print(f"Weekly roster refresh skipped: {e}")
    print(f"Refreshed {CURRENT_SEASON} play by play and player list.")


def cmd_log(a):
    if a.action == "add":
        print(f"Logged bet #{ledger.add(a.bet, a.price, a.stake, a.prob, a.sport, a.notes or '')}")
    elif a.action == "settle":
        r = ledger.settle(int(a.bet), a.result, a.close, a.pnl)
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
        sp.add_argument("--leaders-only", action="store_true",
                        help="Old roster: usage leaders + depth starters only (default adds every skill player with recent snaps)")
        sp.add_argument("--mult", action="append", help="'NAME=1.10' share multiplier for role news")
        sp.add_argument("--catch", action="append", help="'NAME=0.48' catch-rate override (manual, flagged)")
        sp.add_argument("--fee", type=float, default=0.02, help="Fee per $1 contract (Robinhood charged 2c on bet #1)")
        sp.add_argument("--bankroll", type=float, default=None, help="Default: current bankroll from the bet log")

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

    gl = sub.add_parser("gameline", help="Spread/total/team total/moneyline sim anchored to the market line")
    gl.add_argument("away")
    gl.add_argument("home")
    gl.add_argument("--fav", required=True, help="Team favored on the main spread")
    gl.add_argument("--spread", type=float, required=True, help="Main spread size, e.g. 2.5")
    gl.add_argument("--total", type=float, required=True)
    gl.add_argument("--line", action="append", help="BAL:-6.5:40c | OVER:41.5:52c | BAL:ML:60c | BAL:TT:20.5:50c")
    gl.add_argument("--sims", type=int, default=25000)
    gl.add_argument("--season", type=int, default=CURRENT_SEASON)
    gl.add_argument("--fee", type=float, default=0.02)
    gl.add_argument("--bankroll", type=float, default=None)
    gl.set_defaults(func=cmd_gameline)

    rp = sub.add_parser("report", help="Full game report as an HTML page")
    common(rp, teams=False)
    rp.add_argument("away")
    rp.add_argument("home")
    rp.add_argument("--fav")
    rp.add_argument("--spread", type=float)
    rp.add_argument("--total", type=float)
    rp.add_argument("--board", help="CSV of Robinhood prices and/or big-book lines")
    rp.add_argument("--news", help="JSON list of injury/news items with sources")
    rp.add_argument("--players", nargs="+")
    rp.add_argument("--blind", nargs="+", help="Players the model can't price tonight (excluded from bets); \"Name:rec,rec_yds\" excludes only those stats")
    rp.add_argument("--model-line", help="Independent model's number, shown for reference")
    rp.add_argument("--qb", action="append", help="'TEAM=QB Name' starter override (default: last game's starter)")
    rp.add_argument("--wind", type=float, help="Forecast wind (mph) for outdoor games; leave out for domes")
    rp.add_argument("--rain", action="store_true", help="Rain forecast at kickoff (50%+ chance) for outdoor games: fewer/shorter passes, more runs (tested 2026-11-12, ON)")
    rp.add_argument("--no-log", action="store_true", help="Don't add this report's picks to the paper-trading log")
    rp.add_argument("--sims", type=int, default=25000)
    rp.add_argument("--html", default="report.html")
    rp.add_argument("--json")
    rp.add_argument("--title")
    rp.add_argument("--proj", help="Where to save the projections file (default: next to the HTML as .proj.json)")
    rp.set_defaults(func=cmd_report)

    pc = sub.add_parser("price", help="Bet finder: projections vs any venue's prices, and vs big-book no-vig")
    pc.add_argument("--proj", required=True, help="Projections file written by `report`")
    pc.add_argument("--quotes", help="Quotes CSV: venue,player,stat,line,side,price,captured_at")
    pc.add_argument("--board", help="Or the report's board CSV (Robinhood rungs + book rows)")
    pc.add_argument("--fee", action="append", help="'venue=0.02' fee per contract (Robinhood default 0.02)")
    pc.add_argument("--min-edge", type=float, default=0.10, help="model edge after fee (CLAUDE.md 2026-11-05: 10%%)")
    pc.add_argument("--top", type=int, default=40)
    pc.add_argument("--csv", help="Write every priced quote to this CSV")
    pc.set_defaults(func=cmd_price)

    od = sub.add_parser("odds", help="Pull big-book player prop lines (The Odds API) into a quotes CSV")
    od.add_argument("away")
    od.add_argument("home")
    od.add_argument("--out", required=True, help="Quotes CSV to write (save under markets/)")
    od.add_argument("--alt", action="store_true", help="Also pull alternate lines (roughly doubles the credits)")
    od.set_defaults(func=cmd_odds)

    bt = sub.add_parser("backtest")
    bt.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025])
    bt.add_argument("--fit", type=int, nargs="+", help="Refit copula on these seasons first")
    bt.add_argument("--limit", type=int, help="Max games (quick check)")
    bt.set_defaults(func=cmd_backtest)

    sub.add_parser("update").set_defaults(func=cmd_update)
    pk = sub.add_parser("picks", help="Grade and summarize the paper-trading log")
    pk.add_argument("action", choices=["grade", "summary", "close"])
    pk.add_argument("--game", help="close: game as logged, e.g. JAX@BAL")
    pk.add_argument("--label", help="close: pick label exactly as logged")
    pk.add_argument("--price", type=float, help="close: last price before kickoff, e.g. 0.43")
    pk.set_defaults(func=lambda a: print(picks.grade(build_model()) if a.action == "grade" else
                                         picks.set_close(a.game, a.label, a.price) if a.action == "close" else picks.summary()))

    lg = sub.add_parser("log")
    lg.add_argument("action", choices=["add", "settle", "summary"])
    lg.add_argument("bet", nargs="?")
    lg.add_argument("result", nargs="?", choices=["win", "loss", "push", "cashout"])
    lg.add_argument("--pnl", type=float, help="exact profit for a cashout (sale credit minus total cost)")
    lg.add_argument("--price")
    lg.add_argument("--stake", type=float, default=50)
    lg.add_argument("--prob", type=float)
    lg.add_argument("--close")
    lg.add_argument("--sport", default="NFL")
    lg.add_argument("--notes")
    lg.add_argument("--bankroll", type=float, default=2000)
    lg.set_defaults(func=cmd_log)

    p.add_argument("--defense", choices=["team", "pos_ypt", "pos_ypt_long", "pos_volume", "zone", "zone_volume"],
                   help="Defense vs position lever (default pos_ypt_long)")
    a = p.parse_args()
    if getattr(a, "bankroll", 0) is None:
        a.bankroll = ledger.current_bankroll()
    global DEFENSE
    DEFENSE = a.defense
    a.func(a)


if __name__ == "__main__":
    main()
