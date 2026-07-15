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


def fetch_snapshot():
    """Return DataFrame(code, close, high, low, vol_shares) for all A-shares."""
    # try akshare first
    try:
        import akshare as ak
        df = _retry(lambda: ak.stock_zh_a_spot_em(), tries=4)
        df = df.rename(columns={"代码": "code", "最新价": "close", "最高": "high",
                                "最低": "low", "成交量": "vol_shares"})
        df = df[["code", "close", "high", "low", "vol_shares"]].copy()
        df["src"] = "akshare"
    except Exception:
        import efinance as ef
        df = _retry(lambda: ef.stock.get_realtime_quotes(), tries=4)
        df = df.rename(columns={"股票代码": "code", "最新价": "close", "最高": "high",
                                "最低": "low", "成交量": "vol_shares"})
        df = df[["code", "close", "high", "low", "vol_shares"]].copy()
        df["src"] = "efinance"
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
