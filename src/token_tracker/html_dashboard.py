"""Generate a private, self-contained HTML usage dashboard."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .analyzer.aggregator import aggregate_daily, aggregate_monthly, aggregate_weekly

_NUMBER_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "total_tokens",
    "cost_usd",
    "session_count",
    "message_count",
)


def _merge_stats(stats: list[Any], key_attr: str) -> list[dict[str, Any]]:
    """Merge per-agent aggregates without exposing raw records or local paths."""
    merged: dict[str, dict[str, Any]] = {}
    for item in stats:
        key = str(getattr(item, key_attr))
        row = merged.setdefault(
            key,
            {
                "key": key,
                "inputTokens": 0,
                "outputTokens": 0,
                "cacheCreationTokens": 0,
                "cacheReadTokens": 0,
                "totalTokens": 0,
                "costUsd": 0.0,
                "sessionCount": 0,
                "messageCount": 0,
                "models": {},
            },
        )
        for field in _NUMBER_FIELDS:
            js_name = {
                "input_tokens": "inputTokens",
                "output_tokens": "outputTokens",
                "cache_creation_tokens": "cacheCreationTokens",
                "cache_read_tokens": "cacheReadTokens",
                "total_tokens": "totalTokens",
                "cost_usd": "costUsd",
                "session_count": "sessionCount",
                "message_count": "messageCount",
            }[field]
            row[js_name] += getattr(item, field)
        for model, tokens in item.models.items():
            row["models"][model] = row["models"].get(model, 0) + tokens
    return [merged[key] for key in sorted(merged)]


def build_dashboard_data(loaded: list[tuple[Any, list[Any]]], generated_at: datetime | None = None) -> dict[str, Any]:
    """Build browser-safe aggregate data from entries already loaded by the CLI."""
    period_specs: dict[str, tuple[Callable[[list[Any]], list[Any]], str]] = {
        "day": (aggregate_daily, "date"),
        "week": (aggregate_weekly, "week"),
        "month": (aggregate_monthly, "month"),
    }
    periods: dict[str, list[dict[str, Any]]] = {}
    for period, (aggregate, key_attr) in period_specs.items():
        per_agent = [stat for _agent, entries in loaded for stat in aggregate(entries)]
        periods[period] = _merge_stats(per_agent, key_attr)

    timestamp = generated_at or datetime.now().astimezone()
    return {
        "generatedAt": timestamp.isoformat(timespec="seconds"),
        "agents": [agent.name for agent, _entries in loaded],
        "periods": periods,
    }


def _safe_json(data: dict[str, Any]) -> str:
    """Prevent user-controlled model names from terminating the JSON script tag."""
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_dashboard(data: dict[str, Any]) -> str:
    return _HTML.replace("__DASHBOARD_DATA__", _safe_json(data))


def write_dashboard(path: Path, data: dict[str, Any]) -> Path:
    """Atomically write the report so an interrupted refresh keeps the old file usable."""
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(render_dashboard(data))
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return path


_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>Token Tracker Dashboard</title>
<style>
:root{--bg:#11111b;--panel:#181825;--panel2:#1e1e2e;--text:#cdd6f4;--muted:#9399b2;--line:#313244;--accent:#cba6f7;--blue:#89b4fa;--green:#a6e3a1;--peach:#fab387;--red:#f38ba8;--shadow:0 20px 45px rgba(0,0,0,.25)}
:root[data-theme="light"]{--bg:#eff1f5;--panel:#fff;--panel2:#e6e9ef;--text:#4c4f69;--muted:#7c7f93;--line:#ccd0da;--accent:#8839ef;--blue:#1e66f5;--green:#40a02b;--peach:#fe640b;--red:#d20f39;--shadow:0 18px 40px rgba(76,79,105,.12)}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,color-mix(in srgb,var(--accent) 12%,transparent),transparent 30%),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}.shell{max-width:1240px;margin:auto;padding:42px 24px 64px}header{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:30px}.eyebrow{color:var(--accent);font:700 12px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.15em;text-transform:uppercase}.title{font-size:clamp(30px,5vw,54px);line-height:1;margin:10px 0 12px;letter-spacing:-.045em}.subtitle{color:var(--muted);margin:0;font-size:14px}.actions{display:flex;gap:10px}.control{border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:12px;padding:10px 13px;font-weight:700;cursor:pointer}.tabs{display:inline-flex;padding:4px;background:var(--panel);border:1px solid var(--line);border-radius:14px;margin-bottom:18px}.tab{border:0;background:transparent;color:var(--muted);padding:9px 18px;border-radius:10px;font-weight:750;cursor:pointer}.tab.active{background:var(--accent);color:var(--bg)}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card,.chart-card,.table-card,.models-card{background:color-mix(in srgb,var(--panel) 94%,transparent);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}.card{padding:20px}.label{color:var(--muted);font-size:12px;font-weight:750;text-transform:uppercase;letter-spacing:.08em}.value{font:750 clamp(23px,3vw,34px) ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:10px}.delta{font-size:12px;color:var(--muted);margin-top:7px}.grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(260px,1fr);gap:14px;margin-top:14px}.chart-card,.models-card,.table-card{padding:20px}.section-head{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:20px}.section-title{font-size:15px;font-weight:800}.metric-tabs{display:flex;gap:5px}.metric{border:0;border-radius:8px;padding:6px 9px;background:transparent;color:var(--muted);cursor:pointer}.metric.active{background:var(--panel2);color:var(--text)}#chart{display:flex;align-items:flex-end;gap:6px;height:250px;border-bottom:1px solid var(--line);padding-top:12px}.bar-wrap{height:100%;flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;min-width:0}.bar{width:min(30px,80%);min-height:2px;background:linear-gradient(180deg,var(--accent),var(--blue));border-radius:7px 7px 2px 2px;position:relative;transition:height .3s ease}.bar:hover{filter:brightness(1.14)}.bar:hover:after{content:attr(data-tip);position:absolute;bottom:calc(100% + 9px);left:50%;transform:translateX(-50%);white-space:nowrap;background:var(--text);color:var(--bg);padding:6px 8px;border-radius:7px;font:700 11px ui-monospace,monospace;z-index:3}.tick{font:10px ui-monospace,monospace;color:var(--muted);margin-top:8px;overflow:hidden;text-overflow:ellipsis;width:100%;text-align:center}.model-list{display:grid;gap:14px}.model-row{display:grid;gap:7px}.model-meta{display:flex;justify-content:space-between;gap:12px;font-size:12px}.model-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.track{height:7px;background:var(--panel2);border-radius:99px;overflow:hidden}.fill{height:100%;background:var(--green);border-radius:inherit}.table-card{margin-top:14px;overflow:hidden}.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:right;padding:13px 12px;border-bottom:1px solid var(--line);white-space:nowrap}th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em}th:first-child,td:first-child{text-align:left}tbody tr:last-child td{border-bottom:0}.empty{height:220px;display:grid;place-items:center;color:var(--muted)}footer{display:flex;justify-content:space-between;gap:20px;color:var(--muted);font-size:12px;margin-top:18px;padding:0 4px}code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.privacy{color:var(--green)}
@media(max-width:800px){.shell{padding:28px 14px 46px}header{align-items:stretch;flex-direction:column}.actions{align-self:flex-end}.cards{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.tick:nth-child(even){visibility:hidden}}@media(max-width:480px){.cards{grid-template-columns:1fr 1fr}.card{padding:15px}.value{font-size:21px}.tab{padding:8px 13px}footer{flex-direction:column}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
</style>
</head>
<body>
<main class="shell">
<header><div><div class="eyebrow">tt / local analytics</div><h1 class="title">Token 使用仪表盘</h1><p class="subtitle" id="meta"></p></div><div class="actions"><button class="control" id="theme" type="button" aria-label="切换明暗主题">◐ 主题</button></div></header>
<nav class="tabs" aria-label="统计周期"><button class="tab active" data-period="day">天</button><button class="tab" data-period="week">周</button><button class="tab" data-period="month">月</button></nav>
<section class="cards"><article class="card"><div class="label">Token 总量</div><div class="value" id="tokens">0</div><div class="delta" id="range"></div></article><article class="card"><div class="label">等效成本</div><div class="value" id="cost">$0</div><div class="delta">基于当前价格表估算</div></article><article class="card"><div class="label">会话数</div><div class="value" id="sessions">0</div><div class="delta">所选周期累计</div></article><article class="card"><div class="label">消息数</div><div class="value" id="messages">0</div><div class="delta">所选周期累计</div></article></section>
<section class="grid"><article class="chart-card"><div class="section-head"><div class="section-title">使用趋势</div><div class="metric-tabs"><button class="metric active" data-metric="totalTokens">Token</button><button class="metric" data-metric="costUsd">成本</button></div></div><div id="chart"></div></article><aside class="models-card"><div class="section-head"><div class="section-title">模型分布</div></div><div class="model-list" id="models"></div></aside></section>
<section class="table-card"><div class="section-head"><div class="section-title">周期明细</div><div class="label" id="count"></div></div><div class="table-scroll"><table><thead><tr><th>周期</th><th>Token</th><th>输入</th><th>输出</th><th>缓存创建</th><th>缓存读取</th><th>成本</th><th>会话</th><th>消息</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<footer><span class="privacy">● 仅含本地聚合指标</span><span>刷新数据：在项目根目录运行 <code>tt dashboard</code></span></footer>
</main>
<script id="dashboard-data" type="application/json">__DASHBOARD_DATA__</script>
<script>
const data=JSON.parse(document.getElementById('dashboard-data').textContent);let period='day',metric='totalTokens';
const $=id=>document.getElementById(id),fmt=new Intl.NumberFormat('zh-CN',{notation:'compact',maximumFractionDigits:1}),num=new Intl.NumberFormat('zh-CN'),usd=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2});
const labels={day:'日',week:'周',month:'月'};const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function totals(rows){return rows.reduce((a,r)=>{for(const k of ['inputTokens','outputTokens','cacheCreationTokens','cacheReadTokens','totalTokens','costUsd','sessionCount','messageCount'])a[k]+=r[k];for(const [m,v] of Object.entries(r.models))a.models[m]=(a.models[m]||0)+v;return a},{inputTokens:0,outputTokens:0,cacheCreationTokens:0,cacheReadTokens:0,totalTokens:0,costUsd:0,sessionCount:0,messageCount:0,models:{}})}
function tick(key){return period==='day'?key.slice(5):period==='week'?key.replace(/^\d{4}-?/,''):key.slice(2)}
function render(){const rows=data.periods[period]||[],sum=totals(rows);$('tokens').textContent=fmt.format(sum.totalTokens);$('cost').textContent=usd.format(sum.costUsd);$('sessions').textContent=num.format(sum.sessionCount);$('messages').textContent=num.format(sum.messageCount);$('range').textContent=rows.length?`${rows[0].key} 至 ${rows.at(-1).key}`:'暂无数据';$('count').textContent=`${rows.length} 个${labels[period]}周期`;
const shown=rows.slice(-(period==='day'?30:period==='week'?16:12)),max=Math.max(1,...shown.map(r=>r[metric]));$('chart').innerHTML=shown.length?shown.map(r=>`<div class="bar-wrap"><div class="bar" style="height:${Math.max(1,r[metric]/max*100)}%" data-tip="${esc(r.key)} · ${metric==='costUsd'?usd.format(r[metric]):num.format(r[metric])}"></div><div class="tick">${esc(tick(r.key))}</div></div>`).join(''):'<div class="empty">暂无使用数据</div>';
const models=Object.entries(sum.models).sort((a,b)=>b[1]-a[1]).slice(0,8),modelMax=models[0]?.[1]||1;$('models').innerHTML=models.length?models.map(([name,value])=>`<div class="model-row"><div class="model-meta"><span class="model-name" title="${esc(name)}">${esc(name)}</span><strong>${fmt.format(value)}</strong></div><div class="track"><div class="fill" style="width:${value/modelMax*100}%"></div></div></div>`).join(''):'<div class="empty">暂无模型数据</div>';
$('rows').innerHTML=rows.slice().reverse().slice(0,24).map(r=>`<tr><td>${esc(r.key)}</td><td>${num.format(r.totalTokens)}</td><td>${num.format(r.inputTokens)}</td><td>${num.format(r.outputTokens)}</td><td>${num.format(r.cacheCreationTokens)}</td><td>${num.format(r.cacheReadTokens)}</td><td>${usd.format(r.costUsd)}</td><td>${num.format(r.sessionCount)}</td><td>${num.format(r.messageCount)}</td></tr>`).join('');}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelector('.tab.active').classList.remove('active');b.classList.add('active');period=b.dataset.period;render()});document.querySelectorAll('.metric').forEach(b=>b.onclick=()=>{document.querySelector('.metric.active').classList.remove('active');b.classList.add('active');metric=b.dataset.metric;render()});
const root=document.documentElement,saved=localStorage.getItem('tt-dashboard-theme');if(saved)root.dataset.theme=saved;$('theme').onclick=()=>{const next=root.dataset.theme==='light'?'dark':'light';root.dataset.theme=next;localStorage.setItem('tt-dashboard-theme',next)};$('meta').textContent=`${data.agents.join(' + ')||'Token Tracker'} · 生成于 ${new Date(data.generatedAt).toLocaleString('zh-CN')}`;render();
</script>
</body>
</html>
'''
