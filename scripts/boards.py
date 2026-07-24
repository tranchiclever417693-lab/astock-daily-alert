# -*- coding: utf-8 -*-
"""子板块（创业板 / 科创板）风险预警引擎。

与主站不同：这些规则是用户给定的固定阈值，无需参数搜索。个股宽度直接复用主站
的全市场 OHLCV（按代码前缀过滤），只需额外抓两个板块指数的行情。

指标口径与主站一致：MA 简单均线、RSI Wilder14、KDJ 9/3/3(K=EMA(RSV,1/3),
D=EMA(K,1/3))、MACD 12/26/9(柱=2*(DIF-DEA))。
"""
import os
import numpy as np
import pandas as pd

# ---- 板块配置 -------------------------------------------------------------
BOARDS = {
    "chinext": {
        "id": "chinext",
        "name": "创业板指风险预警",
        "index_name": "创业板指",
        "index_eod": "sz399006",
        "index_sina": "399006",
        "prefixes": ("300", "301"),
        "page": "chinext.html",
    },
    "star": {
        "id": "star",
        "name": "科创板风险预警",
        "index_name": "科创综指",
        "index_eod": "sh000680",
        "index_sina": "000680",
        "prefixes": ("688", "689"),
        "page": "star.html",
    },
}


# ---- 指数指标 -------------------------------------------------------------
def index_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """df: date, high, low, close, volume（升序）。返回加指标后的表。"""
    g = df.sort_values("date").copy()
    c, h, l, v = g["close"], g["high"], g["low"], g["volume"]
    g["ma5"] = c.rolling(5).mean()
    g["ma10"] = c.rolling(10).mean()
    g["ret"] = c / c.shift(1) - 1.0
    # RSI Wilder 14
    d = c.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    rs = up.ewm(alpha=1 / 14, adjust=False).mean() / dn.ewm(alpha=1 / 14, adjust=False).mean()
    g["rsi"] = 100 - 100 / (1 + rs)
    # KDJ 9,3,3
    low9, high9 = l.rolling(9).min(), h.rolling(9).max()
    rsv = (c - low9) / (high9 - low9).replace(0, np.nan) * 100
    g["K"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    g["D"] = g["K"].ewm(alpha=1 / 3, adjust=False).mean()
    g["J"] = 3 * g["K"] - 2 * g["D"]                    # 最灵敏的超卖预警
    g["K_prev"], g["D_prev"] = g["K"].shift(1), g["D"].shift(1)  # 金叉判定（昨日 K≤D）
    # 近6日曾超卖：当日或前1~6个交易日内出现过 J<0 或 K<20（窗口=今日+前6日）
    oversold = ((g["J"] < 0) | (g["K"] < 20)).astype(int)
    g["oversold_recent"] = oversold.rolling(7, min_periods=1).max() > 0
    # MACD 12,26,9 —— 柱 = 2*(DIF-DEA)（红绿柱）
    dif = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    dea = dif.ewm(span=9, adjust=False).mean()
    g["dif"], g["dea"], g["macd"] = dif, dea, 2 * (dif - dea)
    g["macd_prev"] = g["macd"].shift(1)
    g["vol"] = v
    g["vol_avg5"] = v.shift(1).rolling(5).mean()
    g["max10"] = c.rolling(10).max()                    # 近10日(含当日)最高收盘
    g["drawdown10"] = (g["max10"] - c) / g["max10"]     # 相对10日高点回撤
    g["dev10"] = c / g["ma10"] - 1.0                    # 相对MA10乖离（科创板深跌急杀底用）
    # 预警区：近4日内(含当日)曾出现 dev10 ≤ −5%
    g["warn_arm"] = (g["dev10"] <= -0.05).astype(int).rolling(4, min_periods=1).max() > 0
    # 科创板 L2 核心买点：预警区 + MACD柱见谷回升 + KDJ-K勾头向上；仅在首次成立当日发出
    l2_raw = g["warn_arm"] & (g["macd"] > g["macd_prev"]) & (g["K"] > g["K_prev"])
    g["l2_first"] = l2_raw & ~l2_raw.shift(1, fill_value=False)
    return g


# ---- 板块个股宽度 ---------------------------------------------------------
def board_breadth(panel: pd.DataFrame) -> pd.DataFrame:
    """panel: 已含 ma5/ma10/rsi/ret1 的板块个股面板。每个交易日聚合成一行。"""
    rows = []
    for date, g in panel.groupby("date", sort=True):
        rows.append({
            "date": date, "n": len(g),
            "pct_above_ma10": (g["close"] > g["ma10"]).mean(),
            "pct_above_ma5": (g["close"] > g["ma5"]).mean(),
            "pct_rsi_lt40": (g["rsi"] < 40).mean(),
            "pct_up": (g["ret1"] > 0).mean(),
        })
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def finalize_breadth(bs: pd.DataFrame) -> pd.DataFrame:
    """Sort and derive the day-over-day column (needed by 高位衰竭型)."""
    bs = bs.sort_values("date").reset_index(drop=True)
    bs["pct_above_ma5_prev"] = bs["pct_above_ma5"].shift(1)
    return bs


def merge_board(idx: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame:
    keep = ["date", "close", "ret", "ma5", "ma10", "rsi", "K", "D", "macd", "macd_prev",
            "vol", "vol_avg5", "max10", "drawdown10",
            "J", "K_prev", "D_prev", "oversold_recent", "dev10", "warn_arm", "l2_first"]
    m = breadth.merge(idx[keep].rename(columns={"close": "idx_close", "ret": "idx_ret"}),
                      on="date", how="inner")
    return m.sort_values("date").reset_index(drop=True)


# ---- 规则（返回：每个条件的布尔 + 综合）-----------------------------------
def _b(x):
    return bool(x) if not pd.isna(x) else False


def _n(x, fmt="{:.1f}"):
    return "—" if pd.isna(x) else fmt.format(x)


def _pct(x):
    return "—" if pd.isna(x) else f"{x * 100:.1f}%"


def _ratio(a, b):
    return "—" if (pd.isna(a) or pd.isna(b) or b == 0) else f"{a / b:.2f}"


def _allok(conds):
    return all(c[1] for c in conds)


def chinext_signals(r):
    """r: 合并后某一行(Series)。每个条件 = (标签, 是否满足, 当前值字符串)。

    筑底提醒 = KDJ超卖金叉 + MA5趋势确认「三重滤网」（创业板指底部买入策略）：
    三个条件同一天同时成立才发出买入信号；量能/J值前置为非硬性加分项。"""
    px = f"收盘 {_n(r.idx_close)} · MA10 {_n(r.ma10)}"
    golden_cross = _b(r.K > r.D and r.K_prev <= r.D_prev)
    bottom = [
        ("① KDJ金叉（当日K>D 且 昨日K≤D）", golden_cross,
         f"今 K{_n(r.K)}/D{_n(r.D)} · 昨 K{_n(r.K_prev)}/D{_n(r.D_prev)}"),
        ("② 近6日曾超卖（J<0 或 K<20）", _b(r.oversold_recent), f"J {_n(r.J)} · K {_n(r.K)}"),
        ("③ 收盘站上MA5", _b(r.idx_close > r.ma5), f"收盘 {_n(r.idx_close)} · MA5 {_n(r.ma5)}"),
    ]
    # 加分项（不作硬性条件，仅供参考）
    extras = [
        ("量能温和放大（金叉日量比 > 1.0）", _b(r.vol > r.vol_avg5), f"量比 {_ratio(r.vol, r.vol_avg5)}"),
        ("J<0 左侧试探预警（可先建试探仓）", _b(r.J < 0), f"J {_n(r.J)}"),
    ]
    internal = [
        ("创业板指仍在MA10上方", _b(r.idx_close > r.ma10), px),
        ("MACD较前一日走弱", _b(r.macd < r.macd_prev), f"MACD {_n(r.macd)}（前 {_n(r.macd_prev)}）"),
        ("KDJ K < D", _b(r.K < r.D), f"K {_n(r.K)} · D {_n(r.D)}"),
        ("站上MA10个股占比 ≤ 20%", _b(r.pct_above_ma10 <= 0.20), _pct(r.pct_above_ma10)),
        ("当日上涨个股占比 ≤ 30%", _b(r.pct_up <= 0.30), _pct(r.pct_up)),
    ]
    exhaust = [
        ("创业板指仍在MA10上方", _b(r.idx_close > r.ma10), px),
        ("RSI ≥ 65", _b(r.rsi >= 65), f"RSI {_n(r.rsi)}"),
        ("KDJ K ≥ 80", _b(r.K >= 80), f"K {_n(r.K)}"),
        ("成交量 ≥ 前5日均量1.15倍", _b(r.vol >= 1.15 * r.vol_avg5), f"量比 {_ratio(r.vol, r.vol_avg5)}"),
        ("站上MA5个股占比较前一日下降", _b(r.pct_above_ma5 < r.pct_above_ma5_prev),
         f"今 {_pct(r.pct_above_ma5)} · 昨 {_pct(r.pct_above_ma5_prev)}"),
    ]
    return {
        "bottoming": {"label": "创业板筑底提醒（KDJ超卖金叉·三重滤网）",
                      "conds": bottom, "extras": extras, "ok": _allok(bottom)},
        "crash": {"label": "创业板大跌预警", "types": [
            {"name": "内部断裂型", "conds": internal, "ok": _allok(internal)},
            {"name": "高位衰竭型", "conds": exhaust, "ok": _allok(exhaust)},
        ]},
    }


def star_signals(r):
    """科创综指「深跌急杀底」抄底信号（三层递进）：
    L1 预警(备战) → L2 确认(核心买点，三条件同时成立→建首仓40-50%) → L3 深超卖(加仓至70-100%)。
    页面「筑底提醒」= L2 核心买点；L3 深超卖加仓作为加分项展示。指标口径同工作簿。"""
    px = f"收盘 {_n(r.idx_close)} · MA10 {_n(r.ma10)}"
    # L2 核心买点：① 处于预警区(近4日曾 dev10≤−5%) ② MACD柱见谷回升 ③ KDJ-K勾头向上；
    # ④ 首次确认（避免在同一波确认后连日追高，只在起涨首日建首仓）
    bottom = [
        ("① 处于预警区（近4日曾 收盘/MA10−1 ≤ −5%）", _b(r.warn_arm),
         f"dev10 {_n(r.dev10 * 100, '{:+.1f}')}%"),
        ("② MACD柱见谷回升（今柱 > 昨柱）", _b(r.macd > r.macd_prev),
         f"MACD {_n(r.macd)}（昨 {_n(r.macd_prev)}）"),
        ("③ KDJ-K勾头向上（今K > 昨K）", _b(r.K > r.K_prev),
         f"K {_n(r.K)}（昨 {_n(r.K_prev)}）"),
        ("④ 首次确认（昨日未同时成立，起涨首日建首仓40–50%）", _b(r.l2_first),
         "首次确认" if _b(r.l2_first) else "—"),
    ]
    # 加分项：L3 深超卖 → 决定加仓力度（非硬性买点条件）
    extras = [
        ("深超卖·加仓（RSI<35 且 K<20 → 仓位加至70–100%）", _b(r.rsi < 35 and r.K < 20),
         f"RSI {_n(r.rsi)} · K {_n(r.K)}"),
    ]
    crash = [
        ("科创综指仍高于MA10", _b(r.idx_close > r.ma10), px),
        ("RSI ≥ 62", _b(r.rsi >= 62), f"RSI {_n(r.rsi)}"),
        ("MACD为正且衰减至0–10且较前一日下降",
         _b(0 <= r.macd <= 10 and r.macd < r.macd_prev), f"MACD {_n(r.macd)}（前 {_n(r.macd_prev)}）"),
        ("KDJ K < D", _b(r.K < r.D), f"K {_n(r.K)} · D {_n(r.D)}"),
        ("站上MA10个股占比 ≤ 50%", _b(r.pct_above_ma10 <= 0.50), _pct(r.pct_above_ma10)),
        ("当日上涨个股占比 ≤ 35%", _b(r.pct_up <= 0.35), _pct(r.pct_up)),
    ]
    return {
        "bottoming": {"label": "科创板筑底提醒（深跌急杀底·L2核心买点）",
                      "conds": bottom, "extras": extras, "ok": _allok(bottom)},
        "crash": {"label": "科创板大跌预警", "types": [
            {"name": "衰竭型", "conds": crash, "ok": _allok(crash)},
        ]},
    }


RULE_FN = {"chinext": chinext_signals, "star": star_signals}


STOCK_BREADTH_COLS = ["date", "n", "pct_above_ma10", "pct_above_ma5", "pct_rsi_lt40", "pct_up"]


def fetch_index_row(cfg, date, stored_index=None):
    """Return today's index OHLCV row {date,high,low,close,volume} for `date`.

    Prefers EOD; if EOD still lags (after-close) cross-checks a realtime Sina quote
    (昨收 == prev EOD close); finally falls back to a stored index_history row
    (covers replay / already-have)."""
    import datetime
    import akshare as ak
    try:
        d = ak.stock_zh_index_daily(symbol=cfg["index_eod"])
        d["date"] = d["date"].astype(str).str[:10]
        last = d.iloc[-1]
        if str(last["date"]) == date:
            return {"date": date, "high": float(last["high"]), "low": float(last["low"]),
                    "close": float(last["close"]), "volume": float(last["volume"])}
        bj = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        closed = (bj.hour * 60 + bj.minute) >= 15 * 60 + 5
        if closed and str(last["date"]) < date:
            s = ak.stock_zh_index_spot_sina()
            r = s[s["代码"].astype(str).str.contains(cfg["index_sina"])].iloc[0]
            if abs(float(r["昨收"]) - float(last["close"])) < max(0.1, float(last["close"]) * 1e-4):
                return {"date": date, "high": float(r["最高"]), "low": float(r["最低"]),
                        "close": float(r["最新价"]), "volume": float(r["成交量"])}
    except Exception as e:  # noqa: BLE001
        print(f"  [{cfg['id']}] index fetch failed: {type(e).__name__}")
    if stored_index is not None:
        hit = stored_index[stored_index["date"] == date]
        if len(hit):
            r = hit.iloc[0]
            return {"date": date, "high": float(r["high"]), "low": float(r["low"]),
                    "close": float(r["close"]), "volume": float(r["volume"])}
    return None


def evaluate(board_id, merged: pd.DataFrame):
    """返回逐日 signal 列表（每行含 bottoming/crash 明细）。"""
    fn = RULE_FN[board_id]
    out = []
    for _, r in merged.iterrows():
        sig = fn(r)
        crash_any = any(t["ok"] for t in sig["crash"]["types"])
        out.append({
            "date": r["date"],
            "idx_close": None if pd.isna(r["idx_close"]) else round(float(r["idx_close"]), 2),
            "idx_ret": None if pd.isna(r["idx_ret"]) else round(float(r["idx_ret"]) * 100, 2),
            "pct_above_ma10": round(float(r["pct_above_ma10"]) * 100, 1),
            "pct_above_ma5": round(float(r["pct_above_ma5"]) * 100, 1),
            "pct_rsi_lt40": round(float(r["pct_rsi_lt40"]) * 100, 1),
            "pct_up": round(float(r["pct_up"]) * 100, 1),
            "n": int(r["n"]),
            "bottoming": sig["bottoming"]["ok"],
            "crash": crash_any,
            "detail": sig,
        })
    return out


def dump_signals(outdir, cfg, hist):
    """Write a lean signals.json: full condition detail only on the latest day;
    history rows keep just the display metrics (keeps the committed file small)."""
    import json
    lean = [{k: v for k, v in h.items() if k != "detail"} for h in hist]
    out = {
        "updated": pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M"),
        "board": {k: cfg[k] for k in ("id", "name", "index_name", "index_eod")},
        "latest_date": hist[-1]["date"], "latest": hist[-1], "history": lean,
    }
    with open(os.path.join(outdir, "signals.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


def update_board(board_id, date, panel_all, data_root):
    """增量更新单个板块：用已算好指标的全市场面板 panel_all(含 date 当日) + 抓板块指数。
    读写 data/<board>/{breadth_stock.csv, index_history.csv}，产出 signals.json。返回 latest。"""
    cfg = BOARDS[board_id]
    outdir = os.path.join(data_root, board_id)

    # 1) 当日板块个股宽度
    sub = panel_all[panel_all["code"].astype(str).str.startswith(cfg["prefixes"])]
    today = board_breadth(sub[sub["date"] == date])
    if today.empty:
        raise RuntimeError(f"[{board_id}] no board stocks for {date}")
    bs = pd.read_csv(os.path.join(outdir, "breadth_stock.csv"))
    bs["date"] = bs["date"].astype(str)
    bs = bs[bs["date"] != date]
    bs = pd.concat([bs[STOCK_BREADTH_COLS], today[STOCK_BREADTH_COLS]], ignore_index=True)
    bs.to_csv(os.path.join(outdir, "breadth_stock.csv"), index=False, encoding="utf-8-sig")

    # 2) 板块指数当日行情
    ih = pd.read_csv(os.path.join(outdir, "index_history.csv"))
    ih["date"] = ih["date"].astype(str)
    row = fetch_index_row(cfg, date, stored_index=ih)
    if row is None:
        raise RuntimeError(f"[{board_id}] cannot get index {cfg['index_eod']} for {date}")
    ih = ih[ih["date"] != date]
    ih = pd.concat([ih, pd.DataFrame([row])], ignore_index=True).sort_values("date").reset_index(drop=True)
    ih.to_csv(os.path.join(outdir, "index_history.csv"), index=False, encoding="utf-8-sig")

    # 3) 合并 -> 评估 -> 落盘
    merged = merge_board(index_indicators(ih), finalize_breadth(bs))
    merged = merged[merged["idx_close"].notna()].reset_index(drop=True)
    merged.to_csv(os.path.join(outdir, "breadth_daily.csv"), index=False, encoding="utf-8-sig")
    hist = evaluate(board_id, merged)
    dump_signals(outdir, cfg, hist)
    return hist[-1]


def update_all(date, panel_all, data_root):
    res = {}
    for bid in BOARDS:
        try:
            res[bid] = update_board(bid, date, panel_all, data_root)
        except Exception as e:  # noqa: BLE001
            print(f"  [{bid}] 更新失败(跳过): {type(e).__name__}: {e}")
    return res
