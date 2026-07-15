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


def _snapshot_efinance():
    import efinance as ef
    df = _retry(lambda: ef.stock.get_realtime_quotes(), tries=4)
    df = df.rename(columns={"股票代码": "code", "最新价": "close", "最高": "high",
                            "最低": "low", "成交量": "vol_shares"})
    df = df[["code", "close", "high", "low", "vol_shares"]].copy()
    df["src"] = "efinance"
    return df


def _snapshot_perstock(codes, date):
    """Reliable but slow fallback: fetch each stock's latest daily bar via
    akshare stock_zh_a_hist (the same endpoint that built the history).
    `date` = target session (YYYY-MM-DD); returns that day's close/high/low."""
    import akshare as ak
    ymd = date.replace("-", "")
    start = (dt.datetime.strptime(date, "%Y-%m-%d") - dt.timedelta(days=12)).strftime("%Y%m%d")
    rows, fails = [], []
    for i, code in enumerate(codes):
        try:
            h = _retry(lambda: ak.stock_zh_a_hist(symbol=code, period="daily",
                                                  start_date=start, end_date=ymd, adjust=""),
                       tries=3, wait=1)
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
            print(f"  per-stock fetch {i + 1}/{len(codes)} (fails {len(fails)})")
    df = pd.DataFrame(rows)
    df["src"] = "akshare-hist"
    if fails:
        print(f"per-stock fallback: {len(fails)} codes failed")
    return df


def fetch_snapshot(codes=None, date=None):
    """Return DataFrame(code, close, high, low, vol_shares, src) for all A-shares.

    Tries the two fast bulk snapshots first; if both fail and a `codes` list +
    `date` are supplied, falls back to the slow per-stock daily fetch so a
    China-IP local run is never left without data."""
    df = None
    for fn in (_snapshot_akshare, _snapshot_efinance):
        try:
            df = fn()
            break
        except Exception as e:  # noqa: BLE001
            print("bulk snapshot failed:", type(e).__name__)
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
