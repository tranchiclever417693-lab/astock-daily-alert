# -*- coding: utf-8 -*-
"""Render a self-contained index.html from data/signals.json.

The JSON is embedded directly into the page so GitHub Pages serves a single
static file with no fetch / CORS dependencies.
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")


def render():
    with open(os.path.join(DATA, "signals.json"), encoding="utf-8") as f:
        sig = json.load(f)
    payload = json.dumps(sig, ensure_ascii=False)
    html = TEMPLATE.replace("/*__DATA__*/", payload)
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html written,", len(sig["history"]), "days, latest", sig["latest_date"])


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A股每日风险预警</title>
<style>
:root{
  --bg:#0e1116; --panel:#171b22; --panel2:#1e232c; --line:#2a303b;
  --txt:#e6e9ef; --sub:#8b95a5; --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --red:#ef4444; --redbg:#2a1416; --green:#22c55e; --greenbg:#0f2318;
  --amber:#f59e0b; --amberbg:#2a2110; --blue:#3b82f6;
  --row-h:34.4px; --head-h:34px; --rows-visible:60;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:22px 16px 60px}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 16px;margin-bottom:6px}
h1{font-size:22px;margin:0;letter-spacing:.5px}
.updated{color:var(--sub);font-size:13px;font-family:var(--mono)}
.idx{margin:10px 0 22px;font-family:var(--mono);font-size:14px;color:var(--sub)}
.idx b{color:var(--txt);font-size:16px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:680px){.cards{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px}
.card h2{font-size:14px;margin:0 0 12px;color:var(--sub);font-weight:600;letter-spacing:1px}
.status{font-size:26px;font-weight:700;display:flex;align-items:center;gap:10px;margin-bottom:4px}
.dot{width:13px;height:13px;border-radius:50%;flex:none}
.on-red{color:var(--red)} .on-red .dot{background:var(--red);box-shadow:0 0 12px var(--red)}
.on-green{color:var(--green)} .on-green .dot{background:var(--green)}
.on-amber{color:var(--amber)} .on-amber .dot{background:var(--amber);box-shadow:0 0 10px var(--amber)}
.on-neutral{color:var(--sub)} .on-neutral .dot{background:var(--sub)}
.on-blue{color:var(--blue)} .on-blue .dot{background:var(--blue);box-shadow:0 0 10px var(--blue)}
.sub{color:var(--sub);font-size:12.5px;margin-top:2px}
.cond{list-style:none;padding:0;margin:14px 0 0}
.cond li{display:flex;gap:9px;align-items:flex-start;padding:5px 0;font-size:13px;border-top:1px solid var(--line)}
.cond li:first-child{border-top:none}
.mk{font-family:var(--mono);font-weight:700;flex:none;width:16px}
.yes{color:var(--green)} .no{color:var(--sub)}
.aux{margin-top:11px;display:flex;flex-wrap:wrap;gap:8px}
.auxpill{font-size:11.5px;padding:3px 9px;border-radius:20px;border:1px solid var(--line);
  background:var(--panel2);color:var(--sub)}
.auxpill.on{border-color:var(--amber);color:var(--amber)}
.auxpill .auxlab{color:#6b7382;margin-right:3px}
.auxpill.on .auxlab{color:var(--amber);opacity:.8}
.bars{margin-top:16px;display:grid;gap:11px}
.bar-row{font-size:12px}
.bar-row .lab{display:flex;justify-content:space-between;color:var(--sub);margin-bottom:4px}
.bar-row .lab b{color:var(--txt);font-family:var(--mono)}
.track{height:7px;background:var(--panel2);border-radius:5px;overflow:hidden}
.fill{height:100%;border-radius:5px}
.section{margin-top:30px}
.section h3{font-size:13px;color:var(--sub);letter-spacing:1px;margin:0 0 12px;font-weight:600}
/* border-collapse must stay `separate` — sticky <th> does not stick when collapsed */
table{width:100%;border-collapse:separate;border-spacing:0;font-size:12.5px;font-family:var(--mono)}
th,td{padding:7px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--sub);font-weight:500;position:sticky;top:0;background:var(--bg)}
th:first-child,td:first-child{text-align:left}
.tag{display:inline-block;padding:1px 7px;border-radius:6px;font-size:11px;font-weight:600}
.t-crash{background:var(--redbg);color:var(--red)}
.t-conf{background:var(--greenbg);color:var(--green)}
.t-s1{background:var(--greenbg);color:var(--green)}
.t-watch{background:#182234;color:var(--blue)}
.t-none{color:#586173}
.auxmk{display:inline-block;margin-left:4px;font-size:10px;padding:0 4px;border-radius:4px;
  background:var(--panel2);color:var(--sub);border:1px solid var(--line)}
.auxmk.c{color:var(--amber);border-color:#3a2f10}
/* --rows-visible sets how many table rows fit before it scrolls (see build_site) */
.scroll{overflow:auto;border:1px solid var(--line);border-radius:12px;
  max-height:calc(var(--row-h) * var(--rows-visible) + var(--head-h));
  overscroll-behavior:contain}
.hint{color:var(--sub);font-weight:400;font-size:11.5px;letter-spacing:0}
.method{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;font-size:12.5px;color:var(--sub)}
.method b{color:var(--txt)} .method code{color:var(--amber);font-family:var(--mono);font-size:12px}
.method ul{margin:8px 0;padding-left:20px} .method li{margin:3px 0}
footer{margin-top:34px;color:#586173;font-size:11.5px;text-align:center;line-height:1.7}
.pos{color:var(--red)} .neg{color:var(--green)}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>A股每日风险预警</h1>
    <span class="updated" id="updated"></span>
  </header>
  <div class="idx" id="idxline"></div>

  <div class="cards">
    <div class="card" id="crashCard">
      <h2>大跌预警</h2>
      <div class="status" id="crashStatus"><span class="dot"></span><span id="crashText"></span></div>
      <div class="sub">四条件全部满足才触发（顶背离结构：指数创10日新高但市场宽度走弱）</div>
      <ul class="cond" id="crashCond"></ul>
    </div>
    <div class="card" id="botCard">
      <h2>筑底提醒</h2>
      <div class="status" id="botStatus"><span class="dot"></span><span id="botText"></span></div>
      <div class="sub" id="botSub"></div>
      <div class="aux" id="botAux"></div>
      <div class="bars" id="botBars"></div>
    </div>
  </div>

  <div class="section">
    <h3>近200个交易日 <span class="hint">（上下滚动查看）</span></h3>
    <div class="scroll">
      <table id="histTable">
        <thead><tr>
          <th>日期</th><th>上证</th><th>涨跌%</th>
          <th>低于MA5%</th><th>近3日跌%</th><th>RSI&lt;35%</th><th>K&lt;30%</th>
          <th>大跌预警</th><th>筑底</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h3>指标说明</h3>
    <div class="method" id="method"></div>
  </div>

  <footer id="footer"></footer>
</div>

<script>
const DATA = /*__DATA__*/;
const $ = s => document.querySelector(s);

function pct(x){return (x==null?'-':x.toFixed(1)+'%');}
function fmtRet(x){if(x==null)return '-';const c=x>=0?'pos':'neg';return `<span class="${c}">${x>=0?'+':''}${x.toFixed(2)}%</span>`;}

const L = DATA.latest;
$('#updated').textContent = '更新 ' + DATA.updated + ' · 数据日 ' + DATA.latest_date;
$('#idxline').innerHTML = '上证指数 <b>'+ (L.idx_close??'-') +'</b> &nbsp; '+ fmtRet(L.idx_ret) +
  ' &nbsp;·&nbsp; 全市场约 '+ DATA.history.length +' 个交易日回溯';

/* crash card */
(function(){
  const card=$('#crashCard'), st=$('#crashStatus');
  if(L.crash){card.classList.add(); st.className='status on-red';
    $('#crashText').textContent='预警触发';}
  else {st.className='status on-green'; $('#crashText').textContent='未触发';}
  const labels=[
    ['①','上证指数当日上涨',L.c1],
    ['②','创10日收盘新高（严格高于此前9日最高收盘）',L.c2],
    ['③','低于5日均线个股占比 > 50%（当前 '+pct(L.pct_below_ma5)+'）',L.c3],
    ['④','近3日累计下跌个股占比 > 50%（当前 '+pct(L.pct_down3)+'）',L.c4],
  ];
  $('#crashCond').innerHTML = labels.map(([n,t,v])=>
    `<li><span class="mk ${v?'yes':'no'}">${v?'✓':'·'}</span><span>${n} ${t}</span></li>`).join('');
})();

/* bottoming card — PRIMARY = 稳健版一阶段；宽松版与二阶段确认仅作辅助 */
(function(){
  const st=$('#botStatus'); const s=L.bottoming;
  const map={
    robust:['on-green','稳健版·一阶段试仓','主信号：稳健版超卖条件触发'],
    watching:['on-blue','确认窗口观察中','前5个交易日内出现过稳健版试仓信号'],
    none:['on-neutral','无稳健信号','市场未进入稳健版超卖试仓区'],
  };
  const [cls,txt,sub]=map[s]||map.none;
  st.className='status '+cls; $('#botText').textContent=txt; $('#botSub').textContent=sub;

  // auxiliary badges
  const confMap={deep:'深度恐慌',divergence:'宽度背离回升',none:'未确认'};
  const aux=[
    ['宽松版早预警(辅)', L.aux_relaxed?'触发':'未触发', L.aux_relaxed],
    ['二阶段确认(辅)', confMap[L.aux_confirm]||'未确认', L.aux_confirm!=='none'],
  ];
  $('#botAux').innerHTML = aux.map(([lab,val,on])=>
    `<span class="auxpill ${on?'on':''}"><span class="auxlab">${lab}</span> ${val}</span>`).join('');

  const bars=[
    ['RSI<35 个股占比（稳健阈值≥40%）',L.pct_rsi_lt35,'var(--amber)'],
    ['KDJ K<30 个股占比（稳健阈值≥60%）',L.pct_k_lt30,'var(--amber)'],
    ['低于MA5 个股占比',L.pct_below_ma5,'var(--blue)'],
  ];
  $('#botBars').innerHTML = bars.map(([lab,v,col])=>`
    <div class="bar-row"><div class="lab"><span>${lab}</span><b>${pct(v)}</b></div>
    <div class="track"><div class="fill" style="width:${Math.min(100,v)}%;background:${col}"></div></div></div>`).join('');
})();

/* history table */
(function(){
  const rows=DATA.history.slice(-200).reverse();
  const botTag={robust:['t-s1','稳健试仓'],watching:['t-watch','观察'],none:['t-none','—']};
  $('#histTable tbody').innerHTML = rows.map(h=>{
    const [bc,bt]=botTag[h.bottoming]||botTag.none;
    // auxiliary markers (small, secondary): 宽=宽松版早预警, 确=二阶段确认
    let aux='';
    if(h.aux_relaxed) aux+='<span class="auxmk">宽</span>';
    if(h.aux_confirm && h.aux_confirm!=='none') aux+='<span class="auxmk c">确</span>';
    const crash = h.crash?'<span class="tag t-crash">预警</span>':'<span class="t-none">—</span>';
    return `<tr>
      <td>${h.date}</td><td>${h.idx_close??'-'}</td><td>${fmtRet(h.idx_ret)}</td>
      <td>${h.pct_below_ma5}</td><td>${h.pct_down3}</td>
      <td>${h.pct_rsi_lt35}</td><td>${h.pct_k_lt30}</td>
      <td>${crash}</td><td><span class="tag ${bc}">${bt}</span>${aux}</td></tr>`;
  }).join('');
})();

/* method */
(function(){
  const r=DATA.rules, b=r.bottoming, s1=b.stage1_robust, s1r=b.stage1_relaxed;
  $('#method').innerHTML = `
  <b>大跌预警</b>（顶背离，四条件全部满足才触发）：
  <ul>
    <li>① 上证指数当日上涨；② 上证收盘价严格高于此前9个交易日最高收盘价（创10日收盘新高）；</li>
    <li>③ 全市场收盘价低于各自5日均线的个股占比 &gt; 50%；④ 近3日累计下跌的个股占比 &gt; 50%。</li>
  </ul>
  <b>筑底提醒</b>（三事件宽松分阶段设计，回测命中 2025-11-24 / 2026-03-24 / 2026-06-09 三次主升浪，领先0–3个交易日）：
  <ul>
    <li><b>主信号 · 一阶段稳健版</b>（优先级最高）：上证当日 ≤ <code>${(s1.idx_ret_max*100).toFixed(2)}%</code>
        且 RSI&lt;${s1.rsi_level} 占比 ≥ <code>${(s1.rsi_floor*100)}%</code>
        且 KDJ K&lt;${s1.k_level} 占比 ≥ <code>${(s1.k_floor*100)}%</code>。
        回测 3/3 命中，18个月仅1次非事件信号，阈值处于稳定平台中心 —— 页面顶部状态即以此为准。</li>
    <li><b>辅助①</b> 宽松版早预警：RSI&lt;${s1r.rsi_level} 占比 ≥ <code>${(s1r.rsi_floor*100)}%</code>
        且 KDJ K&lt;${s1r.k_level} 占比 ≥ <code>${(s1r.k_floor*100)}%</code>（预警更早、信号更多，仅作参考，表中标 <span class="auxmk">宽</span>）。</li>
    <li><b>辅助②</b> 二阶段确认（<b>必须由此前5个交易日内的稳健试仓激活</b>，无前置试仓则不算确认）：
        出现价格—宽度背离（指数仍在5日低点 <code>${(b.confirm_divergence.idx_5d_low_tol*100).toFixed(2)}%</code> 以内，
        且站上MA5占比较前3日低点回升 ≥ <code>${(b.confirm_divergence.above_ma5_rebound_min*100).toFixed(1)}个百分点</code>），
        或深度恐慌（低于MA5 ≥ <code>${(b.confirm_deep_panic.below_ma5_min*100).toFixed(0)}%</code>
        且 RSI&lt;30 ≥ <code>${(b.confirm_deep_panic.rsi_lt30_min*100).toFixed(0)}%</code>）即确认；
        5日内未确认则该次试仓到期作废（仅作参考，表中标 <span class="auxmk c">确</span>）。</li>
  </ul>
  阈值标定（<code>research/confirm_search.py</code>，<b>全局唯一一套参数</b>，不按波段分别取值；标定窗口
  2025-02-20 起，更早的个股覆盖不足已剔除）：本轮牛市共 4 个底部
  （2025-04-07 / 2025-11-24 / 2026-03-24 / 2026-06-09）<b>全部 4/4 确认</b>——恐慌型底部 2025-04-07 由
  <b>深度恐慌</b>路线于 04-08 确认，其余三个由<b>背离</b>路线确认，两条路线各司其职。阈值在满足 4/4 的前提下
  尽量放宽并留防漏余量（深度恐慌在 85%~90%/30%~35% 全区间行为一致，取中；背离 tol 下限 1.08% 取 1.33%，
  Rb 上界 10.4pp 取 5.0pp）。
  <br><b>局限（如实说明）</b>：4 个底部均为正样本、无负样本，故"放宽"缺乏数据上的刹车，只能以选择性为约束；
  且未门控的原始确认条件日频率约 35%，意味着二阶段几乎不会否决一阶段——它并非强过滤器，故仅作辅助。
  技术指标：MA为简单均线，RSI为Wilder 14日，KDJ为9/3/3（K=EMA(RSV,1/3)）。占比分母为当日该指标有效的个股数。仅使用当日及以前数据。`;
})();

$('#footer').innerHTML = '数据来源：akshare / 东方财富 · 每交易日收盘后自动更新<br>'+
  '本页仅为量化指标信息展示，不构成任何投资建议。据此操作，风险自负。';
</script>
</body>
</html>
"""


if __name__ == "__main__":
    render()
