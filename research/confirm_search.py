# -*- coding: utf-8 -*-
"""Grid search for the Stage-2 CONFIRMATION thresholds.

Stage 2 (per design §2) fires when, within `confirm_window` trading days after a
Stage-1 robust signal, EITHER holds:
  (a) 深度恐慌      : pct_below_ma5 >= B  and  pct_rsi_lt30 >= R
  (b) 价格—宽度背离 : index within `tol` of its 5-day low
                      and above-MA5 breadth rebounds >= Rb vs the prior 3-day low

Selection (one single global parameter set — never per-wave tuning):
  1. hard : all 3 主升浪 events confirmed (no misses)
  2. then : minimise false confirmations (non-event Stage-1 signals)
  3. then : MAXIMISE relaxation (as loose as possible without hurting 1&2)
  4. then : prefer a stable threshold plateau over a razor edge
"""
import os
import json
import itertools
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

EVENTS = ["2025-11-24", "2026-03-24", "2026-06-09"]
WIN = 5          # confirmation window (trading days after the stage-1 signal)
LEAD_LO, LEAD_HI = 1, 3

# grids (relaxation direction: B down, R down, tol up, Rb down)
B_GRID = [round(x, 4) for x in np.arange(0.60, 0.9501, 0.025)]
R_GRID = [round(x, 4) for x in np.arange(0.15, 0.6001, 0.025)]
TOL_GRID = [round(x, 5) for x in np.arange(0.0, 0.02001, 0.0025)]
RB_GRID = [round(x, 4) for x in np.arange(0.00, 0.2001, 0.01)]


def load():
    b = pd.read_csv(os.path.join(DATA, "breadth_daily.csv"))
    with open(os.path.join(ROOT, "scripts", "rules.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    return b, cfg


def stage1_robust(b, s):
    m = np.ones(len(b), dtype=bool)
    if s.get("idx_ret_max") is not None:
        m &= b["idx_ret"].values <= s["idx_ret_max"]
    m &= b[f"pct_rsi_lt{s['rsi_level']}"].values >= s["rsi_floor"]
    m &= b[f"pct_k_lt{s['k_level']}"].values >= s["k_floor"]
    return m


def main():
    b, cfg = load()
    dates = list(b["date"])
    n = len(b)
    ev_idx = [dates.index(e) for e in EVENTS]

    robust = stage1_robust(b, cfg["bottoming"]["stage1_robust"])
    sig = list(np.where(robust)[0])
    print("stage-1 robust signals:", [dates[i] for i in sig])

    # group signals: which belong to which event (D-3..D-1), which are non-event
    ev_windows = [set(range(e - LEAD_HI, e - LEAD_LO + 1)) for e in ev_idx]
    ev_signals = [[j for j in sig if j in w] for w in ev_windows]
    non_event = [j for j in sig if not any(j in w for w in ev_windows)]
    for k, e in enumerate(EVENTS):
        print(f"  event {e}: stage-1 at {[dates[j] for j in ev_signals[k]]}")
    print("  non-event stage-1:", [dates[j] for j in non_event])

    # --- ingredients ---
    below5 = b["pct_below_ma5"].values
    rsi30 = b["pct_rsi_lt30"].values
    above5 = 1.0 - below5
    idx_close = b["idx_close"].values
    prev5min = pd.Series(idx_close).rolling(5).min().values
    ratio = idx_close / prev5min                       # >= 1 ; ==1 at the 5-day low
    prior3min = pd.Series(above5).shift(1).rolling(3).min().values
    rebound = above5 - prior3min

    def confirmed_windows(conf):
        """for a boolean confirm array, return (recall, n_false)."""
        def hit(j):
            lo, hi = j + 1, min(n, j + 1 + WIN)
            return bool(conf[lo:hi].any())
        recall = sum(any(hit(j) for j in grp) if grp else False for grp in ev_signals)
        n_false = sum(1 for j in non_event if hit(j))
        return recall, n_false

    def relax_score(B, R, tol, Rb):
        return ((0.95 - B) / 0.35 + (0.60 - R) / 0.45 + tol / 0.02 + (0.20 - Rb) / 0.20)

    rows = []
    for B, R in itertools.product(B_GRID, R_GRID):
        deep = (below5 >= B) & (rsi30 >= R)
        for tol, Rb in itertools.product(TOL_GRID, RB_GRID):
            div = (ratio <= 1 + tol) & (rebound >= Rb)
            conf = deep | div
            recall, n_false = confirmed_windows(conf)
            if recall < 3:
                continue
            rows.append({"B": B, "R": R, "tol": tol, "Rb": Rb,
                         "recall": recall, "false": n_false,
                         "relax": round(relax_score(B, R, tol, Rb), 4),
                         "n_confirm_days": int(conf.sum())})
    df = pd.DataFrame(rows)
    print(f"\nfeasible (recall 3/3): {len(df)}")
    if df.empty:
        print("NO FEASIBLE RULE")
        return
    min_false = int(df["false"].min())
    print("min false confirmations:", min_false)
    best = df[df["false"] == min_false].copy()
    best = best.sort_values("relax", ascending=False)
    df.sort_values(["false", "relax"], ascending=[True, False]).to_csv(
        os.path.join(HERE, "results", "confirm_pareto.csv"), index=False, encoding="utf-8-sig")
    print("\n=== most relaxed with min false ===")
    print(best.head(8).to_string(index=False))
    return best, (below5, rsi30, ratio, rebound), ev_signals, non_event, dates, n


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    main()
