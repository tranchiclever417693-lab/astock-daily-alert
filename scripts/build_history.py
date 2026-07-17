# -*- coding: utf-8 -*-
"""One-time bootstrap: build breadth_daily.csv, index_history.csv and a rolling
OHLCV cache from the local historical OHLCV pickle + akshare index history.

After this runs, daily_update.py only needs a light daily snapshot to extend it.
"""
import os
import sys
import pickle
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
from indicators import build_panel, compute_breadth, add_index_conditions  # noqa: E402

OHLCV_PKL = r"D:\A股数据_指标_扩展\_ohlcv.pkl"
CACHE_DAYS = 60      # trading days of OHLCV kept in the repo for indicator warmup
MIN_BREADTH_N = 3000  # a session needs a real cross-section for breadth % to mean anything


def fetch_index():
    import akshare as ak
    df = ak.stock_zh_index_daily(symbol="sh000001")
    df = df[["date", "close"]].copy()
    df["date"] = df["date"].astype(str)
    return df


def main():
    os.makedirs(DATA, exist_ok=True)
    print("loading OHLCV pickle ...")
    oh = pickle.load(open(OHLCV_PKL, "rb"))
    oh["code"] = oh["code"].astype(str).str.zfill(6)
    oh["date"] = oh["date"].astype(str)

    print(f"building indicators for {oh['code'].nunique()} stocks ...")
    panel = build_panel(oh)

    print("computing market breadth ...")
    breadth = compute_breadth(panel)

    print("fetching Shanghai Composite ...")
    idx = fetch_index()
    idx.to_csv(os.path.join(DATA, "index_history.csv"), index=False, encoding="utf-8-sig")

    merged = add_index_conditions(breadth, idx)
    # keep only dates with a valid index row (drops pre-warmup / non-trading noise)
    merged = merged[merged["idx_close"].notna()]
    # The OHLCV history has ragged coverage: the earliest sessions contain only a
    # handful of stocks, so their "share of the whole market" figures are noise
    # (1 stock below MA5 => 100%). Drop any session without a real cross-section.
    thin = (merged["n"] < MIN_BREADTH_N).sum()
    if thin:
        print(f"dropping {thin} sessions with < {MIN_BREADTH_N} stocks (ragged early coverage)")
    merged = merged[merged["n"] >= MIN_BREADTH_N].reset_index(drop=True)
    merged.to_csv(os.path.join(DATA, "breadth_daily.csv"), index=False, encoding="utf-8-sig")
    print(f"breadth_daily.csv: {len(merged)} rows, {merged['date'].min()} .. {merged['date'].max()}")

    # rolling OHLCV cache for the next incremental update
    dates = sorted(oh["date"].unique())
    keep = set(dates[-CACHE_DAYS:])
    cache = oh[oh["date"].isin(keep)][["code", "date", "close", "high", "low", "vol_shares"]]
    cache.to_csv(os.path.join(DATA, "ohlcv_recent.csv.gz"), index=False,
                 encoding="utf-8-sig", compression="gzip")
    print(f"ohlcv_recent.csv.gz: {len(cache)} rows, last {CACHE_DAYS} sessions")


if __name__ == "__main__":
    main()
