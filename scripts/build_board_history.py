# -*- coding: utf-8 -*-
"""一次性 bootstrap：为创业板 / 科创板构建 breadth_daily + index_history + signals.json。

个股行情来自主站已有的 _ohlcv.pkl（全市场，2025-02 起）+ 近期缓存 ohlcv_recent.csv.gz，
按代码前缀过滤；板块指数用 akshare 抓 EOD。之后 daily_update 只做增量。
"""
import os
import sys
import json
import pickle
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
from indicators import add_indicators  # noqa: E402
import boards as B  # noqa: E402

OHLCV_PKL = r"D:\A股数据_指标_扩展\_ohlcv.pkl"
MIN_N = {"chinext": 500, "star": 300}   # 板块个股有效数下限（早期覆盖不足则丢弃）
START = "2025-02-20"


def load_all_ohlcv():
    oh = pickle.load(open(OHLCV_PKL, "rb"))
    oh["code"] = oh["code"].astype(str).str.zfill(6)
    oh["date"] = oh["date"].astype(str)
    rec = pd.read_csv(os.path.join(DATA, "ohlcv_recent.csv.gz"), dtype={"code": str})
    rec["code"] = rec["code"].str.zfill(6)
    rec["date"] = rec["date"].astype(str)
    both = pd.concat([oh[["code", "date", "close", "high", "low", "vol_shares"]], rec],
                     ignore_index=True)
    both = both.drop_duplicates(["code", "date"], keep="last")
    return both


def fetch_index_eod(code):
    import akshare as ak
    d = ak.stock_zh_index_daily(symbol=code)
    d = d[["date", "high", "low", "close", "volume"]].copy()
    d["date"] = d["date"].astype(str).str[:10]
    return d


def build_board(board_id, all_ohlcv):
    cfg = B.BOARDS[board_id]
    sub = all_ohlcv[all_ohlcv["code"].str.startswith(cfg["prefixes"])].copy()
    parts = [add_indicators(g) for _, g in sub.groupby("code", sort=False)]
    panel = pd.concat(parts, ignore_index=True)
    breadth = B.board_breadth(panel)
    breadth = breadth[(breadth["n"] >= MIN_N[board_id]) & (breadth["date"] >= START)]

    idx_raw = fetch_index_eod(cfg["index_eod"])
    idx = B.index_indicators(idx_raw)
    merged = B.merge_board(idx, B.finalize_breadth(breadth))
    merged = merged[merged["idx_close"].notna()].reset_index(drop=True)

    outdir = os.path.join(DATA, board_id)
    os.makedirs(outdir, exist_ok=True)
    # persist the pieces daily_update needs: raw index OHLCV + raw stock breadth
    idx_raw[idx_raw["date"] >= START].to_csv(
        os.path.join(outdir, "index_history.csv"), index=False, encoding="utf-8-sig")
    breadth[B.STOCK_BREADTH_COLS].to_csv(
        os.path.join(outdir, "breadth_stock.csv"), index=False, encoding="utf-8-sig")
    merged.to_csv(os.path.join(outdir, "breadth_daily.csv"), index=False, encoding="utf-8-sig")

    hist = B.evaluate(board_id, merged)
    B.dump_signals(outdir, cfg, hist)
    latest = hist[-1]
    print(f"[{board_id}] {len(merged)}日 {merged['date'].min()}..{merged['date'].max()} | "
          f"最新 {latest['date']} 筑底={latest['bottoming']} 大跌={latest['crash']}")
    return hist


def main():
    print("loading OHLCV ...")
    allo = load_all_ohlcv()
    for bid in B.BOARDS:
        build_board(bid, allo)


if __name__ == "__main__":
    main()
