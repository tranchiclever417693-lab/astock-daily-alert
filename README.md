# A股每日风险预警

收盘后自动抓取全市场数据，计算两类信号并发布到 GitHub Pages（公开网页，所有人可访问）。

**网站**：https://tranchiclever417693-lab.github.io/astock-daily-alert/

## 两类信号

### 1. 大跌预警（顶背离，四条件全部满足才触发）

| # | 条件 |
|---|------|
| ① | 上证指数当日上涨 |
| ② | 上证收盘价严格高于此前 9 个交易日最高收盘价（创 10 日收盘新高） |
| ③ | 全市场收盘价低于各自 5 日均线的个股占比 > 50% |
| ④ | 近 3 日累计下跌的个股占比 > 50% |

指数创新高但市场宽度走弱 → 结构性顶背离。

### 2. 筑底提醒（三事件宽松分阶段设计）

策略文档：`2026-07-14-three-event-relaxed-staged-signal-design`。目标是在三次主升浪
（2025-11-24 / 2026-03-24 / 2026-06-09）起点前 1–3 个交易日给出试仓信号。

- **一阶段·稳健版**：上证当日 ≤ −0.5% 且 `RSI<35 占比 ≥ 40%` 且 `KDJ K<30 占比 ≥ 60%`。
  回测 3/3 命中，18 个月仅 1 次非事件信号，阈值处于稳定平台中心。
- **一阶段·宽松版**：`RSI<35 占比 ≥ 37.5%` 且 `KDJ K<20 占比 ≥ 30%`。预警更早、信号更多，
  复现全部三个回归基准日（含 2026-03-20）。
- **二阶段确认**：试仓后 5 个交易日内出现深度恐慌（低于 MA5 ≥85% 且 RSI<30 ≥50%）或
  价格—宽度背离（指数处 5 日低位而站上 MA5 占比较前 3 日低点回升 ≥8 个百分点）即确认；
  否则试仓信号到期作废。

规则参数搜索与选取标准见 `research/param_search.py` 与
`2026-07-14-three-event-relaxed-staged-signal-design.md`。

## 技术指标口径

- MA5 / MA10：简单移动平均
- RSI：Wilder 14 日
- KDJ：9 日 RSV，K = EMA(RSV, α=1/3)，D = EMA(K, α=1/3)
- 占比分母 = 当日该指标有效的个股数；新股/停牌/缺失不填充；仅用当日及以前数据

（已验证：以上公式可精确复现历史指标工作簿的 RSI / KDJ 数值。）

## 目录结构

```
scripts/indicators.py     指标与市场宽度计算（回测与实盘共用）
scripts/build_history.py  一次性：从本地 OHLCV 历史构建 breadth_daily.csv 等
scripts/rules.json        两类信号的最终规则参数
scripts/signals.py        套用规则 → data/signals.json
scripts/build_site.py     渲染 index.html（数据内联，纯静态）
scripts/fetch_live.py     实盘抓取：akshare 快照，efinance 兜底
scripts/daily_update.py   每日增量：抓取→重算→重建（--replay 可离线回放测试）
research/param_search.py  筑底规则的网格搜索
.github/workflows/daily.yml  云端定时（工作日 07:35 UTC ≈ 北京 15:35）
run_local.ps1 / setup_task_scheduler.ps1  本地任务计划兜底
```

## 每日更新机制

- **云端（主）**：GitHub Actions 每个工作日 15:35(北京) 运行 `daily_update.py` 并自动提交推送。
- **本地（兜底）**：`setup_task_scheduler.ps1` 注册 Windows 任务计划，同一时间在本地
  （国内 IP，数据源更稳定）运行 `run_local.ps1`。抓取失败则不提交，避免写入坏数据。

首次本地初始化：

```powershell
$env:PYTHONUTF8=1
$py = "C:\Users\cindy\AppData\Local\Programs\Python\Python312\python.exe"
& $py scripts\build_history.py      # 构建历史（依赖本地 OHLCV 数据）
& $py scripts\signals.py
& $py scripts\build_site.py
```

## 免责声明

本页仅为量化指标信息展示，不构成任何投资建议。据此操作，风险自负。
