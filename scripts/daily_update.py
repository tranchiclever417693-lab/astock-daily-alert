# -*- coding: utf-8 -*-
"""Daily routine: extend the OHLCV cache by one session, recompute breadth,
re-run signals, and rebuild the website.

Usage:
  python daily_update.py            # live: fetch today's snapshot via akshare/efinance
  python daily_update.py --replay 2026-07-14
                                    # test: rebuild that date from ohlcv_recent.csv
                                    # (no network), used to validate the pipeline
"""
import os
import sys
import argparse
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
from indicators import build_panel, compute_breadth, add_index_conditions  # noqa: E402
import signals as sig_mod  # noqa: E402
import build_site  # noqa: E402

CACHE_DAYS = 60


def load_cache():
    p = os.path.join(DATA, "ohlcv_recent.csv.gz")
    df = pd.read_csv(p, dtype={"code": str})
    df["code"] = df["code"].str.zfill(6)
    df["date"] = df["date"].astype(str)
    return df


def load_index():
    p = os.path.join(DATA, "index_history.csv")
    idx = pd.read_csv(p)
    idx["date"] = idx["date"].astype(str)
    return idx


def get_new_day(replay):
    """Return (date_str, snapshot_df[code,close,high,low,vol_shares], idx_close)."""
    if replay:
        cache = load_cache()
        day = cache[cache["date"] == replay]
        if day.empty:
            raise SystemExit(f"replay date {replay} not in cache")
        idx = load_index()
        ic = float(idx.loc[idx["date"] == replay, "close"].iloc[0])
        return replay, day[["code", "close", "high", "low", "vol_shares"]].copy(), ic
    from fetch_live import fetch_snapshot, fetch_index_today
    idx_date, idx_close = fetch_index_today()
    codes = sorted(load_cache()["code"].unique())
    snap = fetch_snapshot(codes=codes, date=idx_date)
    print("snapshot source:", snap["src"].iloc[0] if len(snap) else "empty")
    snap["date"] = idx_date
    return idx_date, snap, idx_close


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", default=None, help="rebuild an existing cached date (offline test)")
    args = ap.parse_args()

    date, snap, idx_close = get_new_day(args.replay)
    print("target session:", date, "| stocks:", len(snap), "| index:", idx_close)

    # guard: never write a partial day (shrunken breadth denominator = bad signals)
    MIN_STOCKS = 3000
    if len(snap) < MIN_STOCKS:
        raise SystemExit(f"only {len(snap)} stocks fetched (< {MIN_STOCKS}); "
                         f"data source unreliable now — abort without writing.")

    # --- extend OHLCV cache (replace if the date already exists) ---
    cache = load_cache()
    cache = cache[cache["date"] != date]
    snap = snap.assign(date=date)[["code", "date", "close", "high", "low", "vol_shares"]]
    cache = pd.concat([cache, snap], ignore_index=True)
    keep = sorted(cache["date"].unique())[-CACHE_DAYS:]
    cache = cache[cache["date"].isin(keep)].reset_index(drop=True)

    # --- recompute indicators + breadth over the cache window ---
    panel = build_panel(cache)
    breadth = compute_breadth(panel)

    # --- index history: append today, then merge index conditions ---
    idx = load_index()
    idx = idx[idx["date"] != date]
    idx = pd.concat([idx, pd.DataFrame([{"date": date, "close": idx_close}])], ignore_index=True)
    idx = idx.sort_values("date").reset_index(drop=True)

    merged = add_index_conditions(breadth, idx)
    today_row = merged[merged["date"] == date]
    if today_row.empty or today_row["idx_close"].isna().all():
        raise SystemExit("failed to compute today's breadth row")

    # --- append today's row to the full breadth_daily history ---
    hist = pd.read_csv(os.path.join(DATA, "breadth_daily.csv"))
    hist["date"] = hist["date"].astype(str)
    hist = hist[hist["date"] != date]
    cols = hist.columns
    add = today_row.reindex(columns=cols)
    hist = pd.concat([hist, add], ignore_index=True).sort_values("date").reset_index(drop=True)

    # --- persist everything ---
    cache.to_csv(os.path.join(DATA, "ohlcv_recent.csv.gz"), index=False,
                 encoding="utf-8-sig", compression="gzip")
    idx.to_csv(os.path.join(DATA, "index_history.csv"), index=False, encoding="utf-8-sig")
    hist.to_csv(os.path.join(DATA, "breadth_daily.csv"), index=False, encoding="utf-8-sig")

    out = sig_mod.build_signals()
    build_site.render()
    L = out["latest"]
    print(f"DONE {L['date']} | 大跌预警={L['crash']} 四条件={[L['c1'],L['c2'],L['c3'],L['c4']]} "
          f"| 筑底={L['bottoming']}")


if __name__ == "__main__":
    main()
