# -*- coding: utf-8 -*-
"""Apply the crash-warning and staged-bottoming rules to the daily breadth frame
and emit signals.json (latest state + full history) for the website.

This is the single evaluator used by both the backtest and the daily update.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")


def load_rules():
    with open(os.path.join(HERE, "rules.json"), encoding="utf-8") as f:
        return json.load(f)


def crash_flags(b, cfg):
    c = cfg["crash_warning"]
    f1 = b["idx_up"].fillna(False).astype(bool)
    f2 = b["idx_new10high"].fillna(False).astype(bool)
    f3 = b["pct_below_ma5"] > c["below_ma5_min"]
    f4 = b["pct_down3"] > c["down3_min"]
    fired = f1 & f2 & f3 & f4
    return pd.DataFrame({"c1": f1, "c2": f2, "c3": f3, "c4": f4, "crash": fired})


def stage1_mask(b, s):
    m = np.ones(len(b), dtype=bool)
    if s.get("idx_ret_max") is not None:
        m &= b["idx_ret"].values <= s["idx_ret_max"]
    m &= b[f"pct_rsi_lt{s['rsi_level']}"].values >= s["rsi_floor"]
    m &= b[f"pct_k_lt{s['k_level']}"].values >= s["k_floor"]
    return m


def bottoming_state(b, cfg):
    """Return per-day dicts describing stage-1 (both variants) and stage-2 state."""
    bt = cfg["bottoming"]
    above_ma5 = 1.0 - b["pct_below_ma5"].values
    dp = bt["confirm_deep_panic"]
    dv = bt["confirm_divergence"]

    # (a) 深度恐慌：样本内被非事件日 2025-04-08 完全支配（其宽度/RSI 比任何事件日更极端），
    #     故只能设在历史极值之上作极端兜底；样本内不触发，未经验证。
    deep = (b["pct_below_ma5"].values >= dp["below_ma5_min"]) & \
           (b["pct_rsi_lt30"].values >= dp["rsi_lt30_min"])

    # (b) 价格—宽度背离：指数仍在5日低位 tol 之内，同时站上MA5占比较前3日低点回升 >= Rb
    idx_close = b["idx_close"].values
    prev5_min = pd.Series(idx_close).rolling(5).min().values
    idx_5d_ratio = idx_close / prev5_min                  # 1.0 == 正处5日低点
    prior3_min = pd.Series(above_ma5).shift(1).rolling(3).min().values
    rebound = (idx_5d_ratio <= 1.0 + dv["idx_5d_low_tol"]) & \
              ((above_ma5 - prior3_min) >= dv["above_ma5_rebound_min"])
    confirm_today = deep | rebound

    robust = stage1_mask(b, bt["stage1_robust"])
    relaxed = stage1_mask(b, bt["stage1_relaxed"])
    win = bt["confirm_window"]

    states = []
    for i in range(len(b)):
        # PRIMARY signal = 稳健版一阶段 only. Its confirmation window (watching)
        # is driven solely by robust triggers; 宽松版 and 二阶段确认 are auxiliary.
        robust_recent = any(robust[j] for j in range(max(0, i - win), i))  # prior days
        states.append({
            "stage1_robust": bool(robust[i]),
            "robust_active": bool(robust_recent),
            "stage1_relaxed": bool(relaxed[i]),        # auxiliary
            "confirm_today": bool(confirm_today[i]),   # auxiliary
            "deep_panic": bool(deep[i]),
            "divergence": bool(rebound[i]),
        })
    return states


def build_signals():
    cfg = load_rules()
    b = pd.read_csv(os.path.join(DATA, "breadth_daily.csv"))
    cf = crash_flags(b, cfg)
    bs = bottoming_state(b, cfg)

    hist = []
    for i in range(len(b)):
        r = b.iloc[i]
        st = bs[i]
        # PRIMARY status = 稳健版一阶段 (highest priority). watching = robust fired
        # within the prior confirm-window. 宽松/确认 are reported separately as aux.
        if st["stage1_robust"]:
            bstatus = "robust"
        elif st["robust_active"]:
            bstatus = "watching"
        else:
            bstatus = "none"
        # 二阶段确认只能由"此前5个交易日内的稳健版试仓信号"激活；
        # 没有前置试仓时，即使当日指标满足深度恐慌/背离，也不是确认。
        aux_confirm = "none"
        if st["robust_active"]:
            if st["deep_panic"]:
                aux_confirm = "deep"
            elif st["divergence"]:
                aux_confirm = "divergence"
        hist.append({
            "date": r["date"],
            "idx_close": None if pd.isna(r["idx_close"]) else round(float(r["idx_close"]), 2),
            "idx_ret": None if pd.isna(r["idx_ret"]) else round(float(r["idx_ret"]) * 100, 2),
            "crash": bool(cf["crash"].iloc[i]),
            "c1": bool(cf["c1"].iloc[i]), "c2": bool(cf["c2"].iloc[i]),
            "c3": bool(cf["c3"].iloc[i]), "c4": bool(cf["c4"].iloc[i]),
            "pct_below_ma5": round(float(r["pct_below_ma5"]) * 100, 1),
            "pct_down3": round(float(r["pct_down3"]) * 100, 1),
            "pct_rsi_lt35": round(float(r["pct_rsi_lt35"]) * 100, 1),
            "pct_k_lt30": round(float(r["pct_k_lt30"]) * 100, 1),
            "bottoming": bstatus,               # primary (robust-only)
            "aux_relaxed": bool(st["stage1_relaxed"]),  # auxiliary: 宽松版早预警
            "aux_confirm": aux_confirm,                 # auxiliary: 二阶段确认
        })

    latest = hist[-1]
    out = {
        "updated": pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M"),
        "latest_date": latest["date"],
        "latest": latest,
        "rules": cfg,
        "history": hist,
    }
    with open(os.path.join(DATA, "signals.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


if __name__ == "__main__":
    o = build_signals()
    L = o["latest"]
    print("latest:", L["date"], "| 大跌预警:", L["crash"],
          "| 四条件:", [L["c1"], L["c2"], L["c3"], L["c4"]],
          "| 筑底:", L["bottoming"])
    # backtest sanity: list all crash & bottoming stage-1 dates
    crash_days = [h["date"] for h in o["history"] if h["crash"]]
    s1r = [h["date"] for h in o["history"] if h["bottoming"] == "robust"]
    aux_rx = [h["date"] for h in o["history"] if h["aux_relaxed"]]
    print("历史大跌预警日:", crash_days)
    print("稳健版一阶段信号日(主):", s1r)
    print("宽松版早预警日(辅):", aux_rx)
