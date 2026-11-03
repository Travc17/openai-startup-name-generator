"""Paper-trading log: every qualifying pick from a report, timestamped before kickoff, graded afterward.

This is the public, every-pick record subscribers need. Real-money bets stay in bets.csv.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

LOG = Path(__file__).resolve().parent.parent / "picks_log.csv"
COLS = ["logged_utc", "key", "game", "kind", "label", "legs", "price", "fee", "model_p", "edge", "stake", "result",
        "profit_per_1", "close_price"]


def _read():
    df = pd.read_csv(LOG) if LOG.exists() else pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in df.columns:
            df[c] = None
    for c in ("price", "fee", "model_p", "edge", "stake", "profit_per_1", "close_price"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    for c in ("logged_utc", "game", "kind", "label", "legs", "result"):
        df[c] = df[c].astype(object).where(df[c].notna(), "")
    return df[COLS]


def set_close(game: str, label: str, close: float) -> str:
    """Record the last price before kickoff (same basis as `price`, fee excluded) for closing line value."""
    df = _read()
    hit = (df.game.str.upper() == game.upper()) & (df.label.str.lower() == label.lower())
    if not hit.any():
        return f"No logged pick '{label}' for {game}."
    df.loc[hit, "close_price"] = close
    df.to_csv(LOG, index=False)
    return f"Close {close:.2f} recorded for {label} ({game})."


def log_report(rep: dict, key: int) -> int:
    df = _read()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    game = f'{rep["away"]}@{rep["home"]}'
    new = []
    for s in rep.get("singles", []):
        if s.get("stake"):
            new.append(dict(kind="single", label=s["label"], legs=json.dumps([[s["pid"], s["stat"], s["x"]]]),
                            price=s["price"], model_p=s["p"], edge=s["edge"], stake=s["stake"]))
    for p in rep.get("parlays", []):
        if p.get("stake"):
            new.append(dict(kind="parlay", label=" + ".join(p["legs"]), legs=json.dumps(p["legs_data"]),
                            price=p["ticket"], model_p=p["p"], edge=p["edge"], stake=p["stake"]))
    if not new:
        return 0
    add = pd.DataFrame(new).assign(logged_utc=now, key=key, game=game, fee=rep["fee"], result="", profit_per_1=None, close_price=None)
    # one row per (game, label): re-running a report updates the price/prob instead of duplicating
    df = df[~((df.game == game) & (df.key == key) & df.label.isin(add.label) & (df.result.fillna("") == ""))]
    pd.concat([df, add[COLS]], ignore_index=True).to_csv(LOG, index=False)
    return len(new)


def grade(model) -> str:
    df = _read()
    if df.empty:
        return "No picks logged yet."
    df["result"] = df.result.fillna("").astype(str)
    graded = 0
    qb = model.qbm.p.groupby(["passer_player_id", "key"]).agg(
        pass_att=("yards", "size"), pass_cmp=("complete", "sum"), pass_yds=("yards", "sum"),
        pass_td=("td", "sum"), int=("int", "sum"))
    for i, r in df[df.result == ""].iterrows():
        if model.tg.key.max() < r.key:
            continue  # game not in the data yet
        ok = True
        for pid, stat, x in json.loads(r.legs):
            if stat.startswith("pass_") or stat == "int":
                val = qb[stat].get((pid, r.key)) if (pid, r.key) in qb.index else None
            else:
                h = model._pg_by.get(pid)
                row = h[h.key == r.key] if h is not None else None
                val = None if row is None or row.empty else row.iloc[0][stat]
            if val is None:
                ok = None  # no snaps / no attempts: player did not play, the pick is void
                break
            if not val >= x:
                ok = False
        if ok is None:
            df.at[i, "result"], df.at[i, "profit_per_1"] = "void", 0.0
            continue
        cost = r.price + r.fee
        df.at[i, "result"] = "win" if ok else "loss"
        df.at[i, "profit_per_1"] = round((1 - cost) / cost if ok else -1.0, 4)
        graded += 1
    df.to_csv(LOG, index=False)
    return f"Graded {graded} picks.\n" + summary()


def summary() -> str:
    df = _read()
    g = df[df.result.isin(["win", "loss"])]
    out = [f"{len(df)} picks logged, none graded yet." if g.empty else
           f"{len(df)} picks logged, {len(g)} graded: {(g.result == 'win').mean():.1%} won "
           f"(model expected {pd.to_numeric(g.model_p).mean():.1%}), flat-stake ROI "
           f"{pd.to_numeric(g.profit_per_1).mean():+.1%}"]
    close = pd.to_numeric(df.close_price, errors="coerce")
    if close.notna().any():
        clv = close[close.notna()] - pd.to_numeric(df.price[close.notna()])
        out.append(f"Closing line value on {len(clv)} picks: avg {clv.mean() * 100:+.1f}c, beat the close on "
                   f"{(clv > 0).mean():.0%} (positive = the market moved toward the pick)")
    return "\n".join(out)
