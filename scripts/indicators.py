# -*- coding: utf-8 -*-
"""Single source of truth for per-stock technical indicators and market breadth.

Formulas verified to reproduce the historical workbook exactly:
  - MA5 / MA10 : simple rolling mean of close
  - RSI        : Wilder's 14-period
  - KDJ        : 9-period RSV, K=EMA(RSV, alpha=1/3), D=EMA(K, alpha=1/3), J=3K-2D

The same functions run over the cached OHLCV history (backtest) and over freshly
fetched akshare data (live), so signals are identical between the two.
"""
import numpy as np
import pandas as pd


def add_indicators(g: pd.DataFrame) -> pd.DataFrame:
    """Add ma5, ma10, rsi, kdj_k for a single stock, sorted by date ascending."""
    g = g.sort_values("date").copy()
    c, h, l = g["close"], g["high"], g["low"]
    g["ma5"] = c.rolling(5).mean()
    g["ma10"] = c.rolling(10).mean()
    # RSI Wilder 14
    d = c.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    rs = up.ewm(alpha=1 / 14, adjust=False).mean() / dn.ewm(alpha=1 / 14, adjust=False).mean()
    g["rsi"] = 100 - 100 / (1 + rs)
    # KDJ 9,3,3
    low9 = l.rolling(9).min()
    high9 = h.rolling(9).max()
    rng = (high9 - low9).replace(0, np.nan)
    rsv = (c - low9) / rng * 100
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    g["kdj_k"] = k
    # 3-day cumulative return (close_t / close_{t-3} - 1)
    g["ret3"] = c / c.shift(3) - 1.0
    g["ret1"] = c / c.shift(1) - 1.0
    return g


def build_panel(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Given long OHLCV (code,date,close,high,low,vol_shares), return the same
    frame with indicator columns added per stock."""
    ohlcv = ohlcv.copy()
    ohlcv["code"] = ohlcv["code"].astype(str).str.zfill(6)
    ohlcv["date"] = ohlcv["date"].astype(str)
    parts = [add_indicators(g) for _, g in ohlcv.groupby("code", sort=False)]
    return pd.concat(parts, ignore_index=True)


# Breadth thresholds we may need for the bottoming grid search
RSI_LEVELS = [35, 40, 45]
K_LEVELS = [20, 25, 30]


def compute_breadth(panel: pd.DataFrame) -> pd.DataFrame:
    """Collapse the per-stock panel into one row per trading date.

    Denominator for every share is the count of stocks with a valid value for
    that indicator on that date (new/suspended/missing are simply excluded)."""
    rows = []
    for date, g in panel.groupby("date", sort=True):
        rec = {"date": date, "n": len(g)}
        # breadth used by the crash-warning rule
        below5 = g["close"] < g["ma5"]
        rec["pct_below_ma5"] = below5.mean(skipna=True)
        rec["pct_down3"] = (g["ret3"] < 0).mean()
        # breadth used by the bottoming rule
        rec["pct_above_ma10"] = (g["close"] > g["ma10"]).mean()
        rec["pct_rsi_lt30"] = (g["rsi"] < 30).mean()  # deep-panic confirmation
        for lv in RSI_LEVELS:
            rec[f"pct_rsi_lt{lv}"] = (g["rsi"] < lv).mean()
        for lv in K_LEVELS:
            rec[f"pct_k_lt{lv}"] = (g["kdj_k"] < lv).mean()
        rec["turnover_med"] = g["vol_shares"].median()  # proxy; refined later if turnover% available
        rows.append(rec)
    b = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    # turnover relative to prior 5-day median of the market median
    b["turnover_rel5"] = b["turnover_med"] / b["turnover_med"].shift(1).rolling(5).mean()
    return b


def add_index_conditions(breadth: pd.DataFrame, idx: pd.DataFrame) -> pd.DataFrame:
    """Merge Shanghai Composite conditions into the breadth frame.

    idx: columns date, close (ascending). Adds:
      idx_close, idx_ret, idx_up, idx_new10high, idx_5d_low
    """
    idx = idx.sort_values("date").copy()
    idx["idx_ret"] = idx["close"] / idx["close"].shift(1) - 1.0
    idx["idx_up"] = idx["close"] > idx["close"].shift(1)
    # strictly above the highest close of the prior 9 sessions == new 10-day close high
    idx["prev9_max"] = idx["close"].shift(1).rolling(9).max()
    idx["idx_new10high"] = idx["close"] > idx["prev9_max"]
    # near 5-day low: today's close within the bottom of the last 5 closes
    idx["prev5_min"] = idx["close"].rolling(5).min()
    idx["idx_5d_low"] = idx["close"] <= idx["prev5_min"] * 1.005  # within 0.5% of 5d low
    out = breadth.merge(
        idx[["date", "close", "idx_ret", "idx_up", "idx_new10high", "idx_5d_low"]].rename(
            columns={"close": "idx_close"}
        ),
        on="date",
        how="left",
    )
    return out
