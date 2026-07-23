# -*- coding: utf-8 -*-
"""渲染子板块页面 chinext.html / star.html（自包含，数据内联）。"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
import boards as B  # noqa: E402


def payload(board_id):
    sig = json.load(open(os.path.join(DATA, board_id, "signals.json"), encoding="utf-8"))
    trimmed = [{k: h[k] for k in ("date", "idx_close", "idx_ret", "pct_above_ma10",
                                  "pct_above_ma5", "pct_rsi_lt40", "pct_up",
                                  "bottoming", "crash")} for h in sig["history"]]
    return {"board": sig["board"], "updated": sig["updated"],
            "latest_date": sig["latest_date"], "latest": sig["latest"], "history": trimmed}


def render(board_id):
    p = payload(board_id)
    html = TEMPLATE.replace("/*__DATA__*/", json.dumps(p, ensure_ascii=False))
    out = os.path.join(ROOT, B.BOARDS[board_id]["page"])
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{B.BOARDS[board_id]['page']} written, {len(p['history'])}日, 最新 {p['latest_date']}")


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>子板块风险预警</title>
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
.wrap{max-width:960px;margin:0 auto;padding:18px 16px 60px}
.nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.nav a{font-size:12.5px;color:var(--sub);text-decoration:none;padding:5px 12px;border:1px solid var(--line);
  border-radius:20px;background:var(--panel)}
.nav a.on{color:var(--txt);border-color:var(--blue);background:var(--panel2)}
.nav a:hover{color:var(--txt)}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 16px;margin-bottom:4px}
h1{font-size:21px;margin:0;letter-spacing:.5px}
.updated{color:var(--sub);font-size:13px;font-family:var(--mono)}
.idx{margin:9px 0 20px;font-family:var(--mono);font-size:14px;color:var(--sub)}
.idx b{color:var(--txt);font-size:16px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:680px){.cards{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}
.card h2{font-size:14px;margin:0 0 12px;color:var(--sub);font-weight:600;letter-spacing:1px}
.status{font-size:23px;font-weight:700;display:flex;align-items:center;gap:10px;margin-bottom:2px}
.dot{width:12px;height:12px;border-radius:50%;flex:none}
.on-red{color:var(--red)} .on-red .dot{background:var(--red);box-shadow:0 0 12px var(--red)}
.on-green{color:var(--green)} .on-green .dot{background:var(--green)}
.on-amber{color:var(--amber)} .on-amber .dot{background:var(--amber);box-shadow:0 0 10px var(--amber)}
.on-neutral{color:var(--sub)} .on-neutral .dot{background:var(--sub)}
.typ{margin-top:14px;border-top:1px solid var(--line);padding-top:10px}
.typ .tname{font-size:12px;color:var(--sub);margin-bottom:6px;display:flex;justify-content:space-between}
.typ .tname .tf{font-weight:700}
.cond{list-style:none;padding:0;margin:0}
.cond li{display:flex;gap:9px;align-items:flex-start;padding:4px 0;font-size:12.5px}
.mk{font-family:var(--mono);font-weight:700;flex:none;width:14px}
.yes{color:var(--green)} .no{color:var(--sub)}
.section{margin-top:28px}
.section h3{font-size:13px;color:var(--sub);letter-spacing:1px;margin:0 0 12px;font-weight:600}
.hint{color:var(--sub);font-weight:400;font-size:11.5px;letter-spacing:0}
.scroll{overflow:auto;border:1px solid var(--line);border-radius:12px;
  max-height:calc(var(--row-h) * var(--rows-visible) + var(--head-h));overscroll-behavior:contain}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:12.5px;font-family:var(--mono)}
th,td{padding:7px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--sub);font-weight:500;position:sticky;top:0;background:var(--bg)}
th:first-child,td:first-child{text-align:left}
.tag{display:inline-block;padding:1px 7px;border-radius:6px;font-size:11px;font-weight:600}
.t-crash{background:var(--redbg);color:var(--red)}
.t-bot{background:var(--amberbg);color:var(--amber)}
.t-none{color:#586173}
.method{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;font-size:12.5px;color:var(--sub)}
.method b{color:var(--txt)} .method code{color:var(--amber);font-family:var(--mono);font-size:12px}
.method ul{margin:6px 0;padding-left:20px} .method li{margin:3px 0}
footer{margin-top:32px;color:#586173;font-size:11.5px;text-align:center;line-height:1.7}
.pos{color:var(--red)} .neg{color:var(--green)}
</style>
</head>
<body>
<div class="wrap">
  <nav class="nav" id="nav"></nav>
  <header><h1 id="title"></h1><span class="updated" id="updated"></span></header>
  <div class="idx" id="idxline"></div>

  <div class="cards">
    <div class="card" id="botCard">
      <h2 id="botH"></h2>
      <div class="status" id="botStatus"><span class="dot"></span><span id="botText"></span></div>
      <div class="sub" style="color:var(--sub);font-size:12px;margin-top:2px">收盘后同时满足全部条件才触发</div>
      <ul class="cond" id="botCond"></ul>
    </div>
    <div class="card" id="crashCard">
      <h2 id="crashH"></h2>
      <div class="status" id="crashStatus"><span class="dot"></span><span id="crashText"></span></div>
      <div class="sub" style="color:var(--sub);font-size:12px;margin-top:2px">任一分型满足全部条件即触发</div>
      <div id="crashTypes"></div>
    </div>
  </div>

  <div class="section">
    <h3>近200个交易日 <span class="hint">（上下滚动查看）</span></h3>
    <div class="scroll"><table id="histTable"><thead><tr>
      <th>日期</th><th>指数</th><th>涨跌%</th><th>站上MA10%</th><th>站上MA5%</th>
      <th>RSI&lt;40%</th><th>上涨%</th><th>筑底</th><th>大跌</th>
    </tr></thead><tbody></tbody></table></div>
  </div>

  <div class="section"><h3>策略说明</h3><div class="method" id="method"></div></div>
  <footer id="footer"></footer>
</div>

<script>
const DATA = /*__DATA__*/;
const $ = s => document.querySelector(s);
const pct = x => (x==null?'-':x.toFixed(1)+'%');
const fmtRet = x => x==null?'-':`<span class="${x>=0?'pos':'neg'}">${x>=0?'+':''}${x.toFixed(2)}%</span>`;
const L = DATA.latest, BRD = DATA.board;

/* nav */
$('#nav').innerHTML =
  `<a href="index.html">🏠 A股主站</a>`+
  `<a href="chinext.html" class="${BRD.id==='chinext'?'on':''}">创业板</a>`+
  `<a href="star.html" class="${BRD.id==='star'?'on':''}">科创板</a>`;

document.title = BRD.name;
$('#title').textContent = BRD.name;
$('#updated').textContent = '更新 '+DATA.updated+' · 数据日 '+DATA.latest_date;
$('#idxline').innerHTML = BRD.index_name+' <b>'+(L.idx_close??'-')+'</b> &nbsp; '+fmtRet(L.idx_ret)+
  ' &nbsp;·&nbsp; 成分股 '+L.n+' 只';

/* bottoming card (机会 -> 触发用琥珀色) */
(function(){
  const bt=L.detail.bottoming;
  $('#botH').textContent=bt.label;
  const st=$('#botStatus');
  st.className='status '+(bt.ok?'on-amber':'on-neutral');
  $('#botText').textContent=bt.ok?'触发':'未触发';
  $('#botCond').innerHTML=bt.conds.map(([lab,ok])=>
    `<li><span class="mk ${ok?'yes':'no'}">${ok?'✓':'·'}</span><span>${lab}</span></li>`).join('');
})();

/* crash card (风险 -> 触发用红色) */
(function(){
  const cr=L.detail.crash;
  $('#crashH').textContent=cr.label;
  const st=$('#crashStatus');
  st.className='status '+(L.crash?'on-red':'on-green');
  $('#crashText').textContent=L.crash?'预警触发':'未触发';
  $('#crashTypes').innerHTML=cr.types.map(t=>`
    <div class="typ"><div class="tname"><span>${t.name}</span>
      <span class="tf ${t.ok?'on-red':''}" style="color:${t.ok?'var(--red)':'var(--sub)'}">${t.ok?'满足':'未满足'}</span></div>
      <ul class="cond">${t.conds.map(([lab,ok])=>
        `<li><span class="mk ${ok?'yes':'no'}">${ok?'✓':'·'}</span><span>${lab}</span></li>`).join('')}</ul></div>`).join('');
})();

/* history */
(function(){
  const rows=DATA.history.slice(-200).reverse();
  $('#histTable tbody').innerHTML=rows.map(h=>{
    const bot=h.bottoming?'<span class="tag t-bot">筑底</span>':'<span class="t-none">—</span>';
    const cr=h.crash?'<span class="tag t-crash">预警</span>':'<span class="t-none">—</span>';
    return `<tr><td>${h.date}</td><td>${h.idx_close??'-'}</td><td>${fmtRet(h.idx_ret)}</td>
      <td>${h.pct_above_ma10}</td><td>${h.pct_above_ma5}</td><td>${h.pct_rsi_lt40}</td>
      <td>${h.pct_up}</td><td>${bot}</td><td>${cr}</td></tr>`;
  }).join('');
})();

/* method */
(function(){
  const bt=L.detail.bottoming, cr=L.detail.crash;
  const li=a=>a.map(([lab])=>`<li>${lab}</li>`).join('');
  let h=`<b>${bt.label}</b>（收盘后同时满足全部条件）：<ul>${li(bt.conds)}</ul>`;
  h+=`<b>${cr.label}</b>（任一分型满足即触发）：`;
  cr.types.forEach(t=>{ h+=`<div style="margin:6px 0 2px"><b>${t.name}</b></div><ul>${li(t.conds)}</ul>`; });
  h+=`<div style="margin-top:8px">指标口径：MA简单均线、RSI Wilder14、KDJ 9/3/3、MACD 12/26/9(柱=2×(DIF−DEA))。
      个股占比分母为当日该板块有效成分股数；仅使用当日及以前数据。回测中创业板"内部断裂型/高位衰竭型"
      分别于 2026-06-04 / 2026-06-22 触发，与设计参考日(6月5日前/6月23日前)一致。</div>`;
  $('#method').innerHTML=h;
})();

$('#footer').innerHTML='数据来源：akshare / 东方财富·新浪 · 每交易日收盘后自动更新<br>'+
  '本页仅为量化指标信息展示，不构成任何投资建议。据此操作，风险自负。';
</script>
</body>
</html>
"""


def main():
    for bid in B.BOARDS:
        render(bid)


if __name__ == "__main__":
    main()
