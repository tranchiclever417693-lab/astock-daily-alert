# -*- coding: utf-8 -*-
"""Grid search for the Stage-1 (tentative) bottoming rule, following
`2026-07-14-three-event-relaxed-staged-signal-design`.

Priority (lexicographic):
  1. recall hard constraint : all 3 主升浪 events hit inside their D-3..D-1 window
  2. leading-window          : the nearest signal per event is in D-3..D-1 (D0 never counts)
  3. noise                   : minimise # of non-event signal clusters
  4. max relaxation          : among min-noise rules pick the most relaxed (Pareto)
  5. stability               : also report a plateau-centre robust variant

Only same-day-or-earlier data is used. Denominator = stocks valid that day.
"""
import os
import sys
import json
import itertools
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

EVENTS = ["2025-11-24", "2026-03-24", "2026-06-09"]
MERGE_GAP = 5   # consecutive triggers within 5 trading days = one cluster
LEAD_LO, LEAD_HI = 1, 3  # D-1 .. D-3

# grid
IDX_RET_CAPS = [None, 0.005, 0.0, -0.0025, -0.005, -0.0075, -0.010]
MA10_CAPS = [None] + [round(x, 4) for x in np.arange(0.15, 0.3501, 0.025)]
RSI_LEVELS = [35, 40, 45]
RSI_FLOORS = [round(x, 4) for x in np.arange(0.35, 0.7001, 0.025)]
K_LEVELS = [20, 25, 30]
K_FLOORS = [round(x, 4) for x in np.arange(0.25, 0.6001, 0.025)]
TURN_FLOORS = [None, 0.90, 1.00, 1.10]


def cluster(idxs):
    """Merge sorted trading-day indices into clusters (gap <= MERGE_GAP)."""
    if len(idxs) == 0:
        return []
    idxs = sorted(idxs)
    clusters, cur = [], [idxs[0]]
    for i in idxs[1:]:
        if i - cur[-1] <= MERGE_GAP:
            cur.append(i)
        else:
            clusters.append(cur)
            cur = [i]
    clusters.append(cur)
    return clusters


def evaluate(mask, ev_idx):
    """Return (recall, noise_days, leads, n_clusters) for a boolean signal mask.

    - An event is HIT if >=1 signal day falls in its D-3..D-1 window (D0 excluded).
    - noise_days = signal days outside every event window == false bottom-alerts.
      (Counting days, not clusters, so an always-firing rule is heavily penalised
      instead of collapsing into one 'clean' cluster.)
    """
    sig = np.where(mask)[0]
    windows = [set(range(e - LEAD_HI, e - LEAD_LO + 1)) for e in ev_idx]  # D-3..D-1 inclusive
    all_win = set().union(*windows)
    hit = [False] * len(ev_idx)
    leads = [None] * len(ev_idx)
    for d in sig:
        for k, w in enumerate(windows):
            if d in w:
                hit[k] = True
                lead = ev_idx[k] - d
                if leads[k] is None or lead < leads[k]:
                    leads[k] = lead
    recall = sum(hit)
    noise = int(sum(1 for d in sig if d not in all_win))
    return recall, noise, leads, len(cluster(sig))


def relaxation_score(combo):
    """Higher = more relaxed. Removing a filter counts as maximally relaxed on
    that axis; looser thresholds score higher."""
    ret_cap, ma10, rsi, k, turn = combo
    s = 0.0
    # index return: None (no constraint) most relaxed; else higher cap = looser
    s += 10 if ret_cap is None else (ret_cap + 0.01) * 100
    # ma10 cap: None most relaxed; higher cap looser
    s += 5 if ma10 is None else ma10 * 10
    # rsi floor: None most relaxed; lower floor looser (and lower level looser)
    s += 5 if rsi is None else (1 - rsi[1]) * 3
    # k floor: same
    s += 5 if k is None else (1 - k[1]) * 3
    # turnover filter: None most relaxed
    s += 3 if turn is None else (2 - turn)
    return s


def n_filters(combo):
    return sum(x is not None for x in combo)


def main():
    b = pd.read_csv(os.path.join(DATA, "breadth_daily.csv"))
    dates = list(b["date"])
    ev_idx = [dates.index(e) for e in EVENTS]

    idx_ret = b["idx_ret"].values
    ma10 = b["pct_above_ma10"].values
    turn = b["turnover_rel5"].values
    rsi_masks = {lv: b[f"pct_rsi_lt{lv}"].values for lv in RSI_LEVELS}
    k_masks = {lv: b[f"pct_k_lt{lv}"].values for lv in K_LEVELS}

    def base_mask(ret_cap, ma10_cap, turn_floor):
        m = np.ones(len(b), dtype=bool)
        if ret_cap is not None:
            m &= idx_ret <= ret_cap
        if ma10_cap is not None:
            m &= ma10 <= ma10_cap
        if turn_floor is not None:
            m &= np.nan_to_num(turn, nan=0.0) >= turn_floor
        return m

    # RSI and KDJ-K oversold breadth are the two mandatory Stage-1 measures
    rsi_opts = [(lv, f) for lv in RSI_LEVELS for f in RSI_FLOORS]
    k_opts = [(lv, f) for lv in K_LEVELS for f in K_FLOORS]

    results = []
    for ret_cap, ma10_cap, turn_floor in itertools.product(IDX_RET_CAPS, MA10_CAPS, TURN_FLOORS):
        bm = base_mask(ret_cap, ma10_cap, turn_floor)
        for rsi in rsi_opts:
            rm = bm if rsi is None else bm & (rsi_masks[rsi[0]] >= rsi[1])
            for k in k_opts:
                mask = rm if k is None else rm & (k_masks[k[0]] >= k[1])
                if mask.sum() == 0:
                    continue
                recall, noise, leads, nclust = evaluate(mask, ev_idx)
                if recall < 3:
                    continue
                combo = (ret_cap, ma10_cap, rsi, k, turn_floor)
                results.append({
                    "ret_cap": ret_cap, "ma10_cap": ma10_cap,
                    "rsi": rsi, "k": k, "turn_floor": turn_floor,
                    "recall": recall, "noise": noise, "n_clusters": nclust,
                    "leads": leads, "n_filters": n_filters(combo),
                    "relax": round(relaxation_score(combo), 3),
                    "n_signals": int(mask.sum()),
                })
    print(f"feasible rules (recall 3/3): {len(results)}")
    if not results:
        print("NO FEASIBLE RULE")
        return
    df = pd.DataFrame(results)
    min_noise = df["noise"].min()
    print("min noise (non-event clusters):", min_noise)
    best = df[df["noise"] == min_noise].copy()

    # max-relaxation pick among min-noise
    relaxed = best.sort_values(["relax", "n_signals"], ascending=[False, True]).iloc[0]
    # robust/plateau-centre pick: fewest filters, moderate thresholds, low noise
    robust = best.sort_values(["n_filters", "noise", "n_signals"]).iloc[0]

    df.sort_values(["noise", "relax"], ascending=[True, False]).to_csv(
        os.path.join(HERE, "results", "pareto.csv"), index=False, encoding="utf-8-sig")

    def _f(x):
        return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)

    def describe(r):
        rsi = r["rsi"]; k = r["k"]
        return {
            "ret_cap": _f(r["ret_cap"]), "ma10_cap": _f(r["ma10_cap"]),
            "rsi": [int(rsi[0]), float(rsi[1])] if rsi is not None else None,
            "k": [int(k[0]), float(k[1])] if k is not None else None,
            "turn_floor": _f(r["turn_floor"]),
            "recall": int(r["recall"]), "noise_days": int(r["noise"]),
            "n_clusters": int(r["n_clusters"]),
            "leads": [int(x) if x is not None else None for x in r["leads"]],
            "n_signals": int(r["n_signals"]), "n_filters": int(r["n_filters"]),
        }

    out = {"relaxed": describe(relaxed), "robust": describe(robust),
           "events": EVENTS, "min_noise": int(min_noise), "n_feasible": len(results)}
    with open(os.path.join(HERE, "results", "chosen_rule.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n=== RELAXED ===");  print(json.dumps(describe(relaxed), ensure_ascii=False))
    print("\n=== ROBUST ===");   print(json.dumps(describe(robust), ensure_ascii=False))


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    main()
