# -*- coding: utf-8 -*-
"""Fetch one trading day's market snapshot (all A-shares) + Shanghai Composite.

Primary source: akshare stock_zh_a_spot_em (one paged call).
Fallback:       efinance get_realtime_quotes.
Both are retried; whichever succeeds first is used. Only close/high/low are
needed by the shipped rules, so volume-unit differences are irrelevant.
"""
import time
import datetime as dt
import pandas as pd


def _retry(fn, tries=5, wait=3):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(wait * (i + 1))
    raise last


def _snapshot_akshare():
    import akshare as ak
    df = _retry(lambda: ak.stock_zh_a_spot_em(), tries=4)
    df = df.rename(columns={"代码": "code", "最新价": "close", "最高": "high",
                            "最低": "low", "成交量": "vol_shares"})
    df = df[["code", "close", "high", "low", "vol_shares"]].copy()
    df["src"] = "akshare-spot"
    return df


def _snapshot_sina():
    # Sina backend (different host than 东方财富); slower (~90s, 70 pages) but
    # often reachable when 东方财富 refuses. 代码 comes prefixed e.g. 'sh600519'.
    import re
    import akshare as ak
    df = _retry(lambda: ak.stock_zh_a_spot(), tries=3, wait=4)
    df = df.rename(columns={"代码": "code", "最新价": "close", "最高": "high",
                            "最低": "low", "成交量": "vol_shares"})
    df = df[["code", "close", "high", "low", "vol_shares"]].copy()
    df["code"] = df["code"].astype(str).map(lambda s: re.sub(r"\D", "", s)[-6:])
    df["src"] = "akshare-sina"
    return df


def _snapshot_efinance():
    import efinance as ef
    df = _retry(lambda: ef.stock.get_realtime_quotes(), tries=4)
    df = df.rename(columns={"股票代码": "code", "最新价": "close", "最高": "high",
                            "最低": "low", "成交量": "vol_shares"})
    df = df[["code", "close", "high", "low", "vol_shares"]].copy()
    df["src"] = "efinance"
    return df


PERSTOCK_BUDGET_S = 720  # hard wall-clock cap so the job can never hang for hours


def _snapshot_perstock(codes, date, budget_s=PERSTOCK_BUDGET_S):
    """Bounded slow fallback: fetch each stock's latest daily bar via akshare
    stock_zh_a_hist (the endpoint that built the history). Stops after
    `budget_s` seconds so a flaky network can never wedge the daily job — the
    caller's MIN_STOCKS guard then decides whether the partial result is usable.
    `date` = target session (YYYY-MM-DD); returns that day's close/high/low."""
    import akshare as ak
    ymd = date.replace("-", "")
    start = (dt.datetime.strptime(date, "%Y-%m-%d") - dt.timedelta(days=12)).strftime("%Y%m%d")
    rows, fails = [], []
    t0 = time.time()
    stopped_early = False
    for i, code in enumerate(codes):
        if time.time() - t0 > budget_s:
            stopped_early = True
            print(f"  per-stock time budget {budget_s}s reached at {i}/{len(codes)}; stopping")
            break
        try:
            h = _retry(lambda: ak.stock_zh_a_hist(symbol=code, period="daily",
                                                  start_date=start, end_date=ymd, adjust=""),
                       tries=2, wait=1)
            if h is None or h.empty:
                continue
            last = h.iloc[-1]
            if str(last["日期"])[:10] != date:
                continue  # no bar for the target session (suspended/new)
            rows.append({"code": code, "close": float(last["收盘"]),
                         "high": float(last["最高"]), "low": float(last["最低"]),
                         "vol_shares": float(last["成交量"]) * 100})  # 手 -> 股
        except Exception:
            fails.append(code)
        if (i + 1) % 500 == 0:
            print(f"  per-stock fetch {i + 1}/{len(codes)} (ok {len(rows)}, fails {len(fails)})")
    df = pd.DataFrame(rows)
    df["src"] = "akshare-hist"
    print(f"per-stock fallback: got {len(rows)}, {len(fails)} failed"
          + (" (stopped by time budget)" if stopped_early else ""))
    return df


def fetch_snapshot(codes=None, date=None):
    """Return DataFrame(code, close, high, low, vol_shares, src) for all A-shares.

    Tries the two fast bulk snapshots first; if both fail and a `codes` list +
    `date` are supplied, falls back to the slow per-stock daily fetch so a
    China-IP local run is never left without data."""
    df = None
    for fn in (_snapshot_akshare, _snapshot_sina, _snapshot_efinance):
        try:
            df = fn()
            if df is not None and len(df) >= 3000:
                print("snapshot via", df["src"].iloc[0], "rows", len(df))
                break
            df = None
        except Exception as e:  # noqa: BLE001
            print(f"bulk snapshot {fn.__name__} failed:", type(e).__name__)
    if df is None:
        if codes is None or date is None:
            raise RuntimeError("bulk snapshots failed and no code list for per-stock fallback")
        print(f"falling back to per-stock fetch for {len(codes)} codes ...")
        df = _snapshot_perstock(codes, date)
    df["code"] = df["code"].astype(str).str.zfill(6)
    for c in ["close", "high", "low", "vol_shares"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # keep only Shanghai/Shenzhen/Beijing A-shares (drop indices/funds)
    df = df[df["code"].str.match(r"^(60|00|30|68|8|4|92)")]
    df = df[df["close"].notna() & (df["close"] > 0)].reset_index(drop=True)
    return df


def fetch_index_today():
    """Return (date_str, close) for the Shanghai Composite latest session."""
    import akshare as ak
    df = _retry(lambda: ak.stock_zh_index_daily(symbol="sh000001"))
    last = df.iloc[-1]
    return str(last["date"])[:10], float(last["close"])


def latest_trading_date_guess():
    return dt.datetime.now().strftime("%Y-%m-%d")


if __name__ == "__main__":
    snap = fetch_snapshot()
    d, c = fetch_index_today()
    print("snapshot:", len(snap), "stocks via", snap["src"].iloc[0])
    print("index:", d, c)
