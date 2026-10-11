
const $ = (id) => document.getElementById(id);
const state = { last:null };

function fmt(x,d=2){ return Number.isFinite(Number(x)) ? Number(x).toLocaleString("en-IN",{minimumFractionDigits:d,maximumFractionDigits:d}) : "—"; }
function setBusy(btn,busy,label){ btn.disabled=busy; if(busy){btn.dataset.old=btn.textContent;btn.textContent=label;}else{btn.textContent=btn.dataset.old||btn.textContent;} }
async function api(path, opts={}) {
  const attempts = opts.retry === false ? 1 : 2;
  let lastErr = null;
  for(let attempt=0; attempt<attempts; attempt++){
    const controller = new AbortController();
    const timer = setTimeout(()=>controller.abort(), 25000);
    try{
      const r=await fetch(path,{...opts,signal:controller.signal,headers:{"Content-Type":"application/json",...(opts.headers||{})}});
      const text=await r.text(); let data={};
      try{ data=text?JSON.parse(text):{} }catch{ data={detail:text||"Invalid server response"} }
      if(!r.ok) throw new Error(data.detail||`Request failed (${r.status})`);
      return data;
    }catch(e){
      lastErr=e;
      if(attempt===attempts-1) throw new Error(e.name==="AbortError" ? "Request timed out. The model is still safe to retry." : e.message);
      await new Promise(r=>setTimeout(r,350));
    } finally { clearTimeout(timer); }
  }
  throw lastErr || new Error("Request failed");
}
function message(target,text,kind="ok"){ const el=$(target); if(!el)return; el.textContent=text; el.className=`message ${kind}`; }
function clearMessage(target){ const el=$(target); if(el){el.className="message hidden";el.textContent="";} }

function switchTab(name){
  document.querySelectorAll(".tab").forEach(b=>b.classList.toggle("active",b.dataset.tab===name));
  document.querySelectorAll(".tab-panel").forEach(p=>p.classList.toggle("active",p.id===name));
}
document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>switchTab(b.dataset.tab)));

async function boot(){
  try{
    const b=await api("/api/bootstrap");
    $("providerBadge").textContent=`DATA: ${b.mode}`;
    $("providerBadge").className="badge badge-green";
    $("stockList").innerHTML=(b.universe||[]).map(x=>`<option value="${x.symbol}">${x.name}</option>`).join("");
    renderRepository(b.repository);
  }catch(e){
    $("providerBadge").textContent="DATA: LOCAL FALLBACK";
    $("providerBadge").className="badge badge-amber";
    message("marketMessage",e.message,"err");
  }
}

function drawChart(rows){
  const c=$("chart"),ctx=c.getContext("2d"),dpr=window.devicePixelRatio||1;
  const rect=c.getBoundingClientRect(); c.width=rect.width*dpr;c.height=rect.height*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);
  const w=rect.width,h=rect.height; ctx.clearRect(0,0,w,h);
  if(!rows?.length){return}
  const pad={l:54,r:18,t:18,b:28}; const plotW=w-pad.l-pad.r,plotH=h-pad.t-pad.b;
  const hi=Math.max(...rows.map(r=>r.high)),lo=Math.min(...rows.map(r=>r.low)); const span=(hi-lo)||1;
  const py=v=>pad.t+(hi-v)/span*plotH; const sx=i=>pad.l+i/(rows.length-1)*plotW;
  ctx.strokeStyle="#e5ecf4";ctx.lineWidth=1;ctx.font="11px Inter,Arial";ctx.fillStyle="#72859d";
  for(let i=0;i<5;i++){const y=pad.t+i/4*plotH;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.fillText(fmt(hi-(span*i/4),2),6,y+4);}
  const candleW=Math.max(2,plotW/rows.length*.64);
  rows.forEach((r,i)=>{
    const x=sx(i),up=r.close>=r.open,col=up?"#14966a":"#d74a5a";
    ctx.strokeStyle=col;ctx.fillStyle=up?"#e7f8f1":"#fff0f2";ctx.beginPath();ctx.moveTo(x,py(r.high));ctx.lineTo(x,py(r.low));ctx.stroke();
    const y1=py(Math.max(r.open,r.close)),y2=py(Math.min(r.open,r.close));
    ctx.fillRect(x-candleW/2,y1,candleW,Math.max(2,y2-y1));ctx.strokeRect(x-candleW/2,y1,candleW,Math.max(2,y2-y1));
  });
  const last=rows[rows.length-1];ctx.fillStyle="#1464ff";ctx.beginPath();ctx.arc(sx(rows.length-1),py(last.close),4,0,Math.PI*2);ctx.fill();
}
window.addEventListener("resize",()=>{ if(state.last)drawChart(state.last.candles) });

function renderValidation(v){
  const items=[
    ["Direction accuracy",`${v.direction_accuracy}%`],
    ["Signal precision",`${v.signal_precision}%`],
    ["Signal coverage",`${v.signal_coverage}%`],
    ["Return MAE",v.next_return_mae],
    ["Return R²",v.next_return_r2],
    ["Validation rows",v.validation_rows],
    ["Threshold",v.threshold],
    ["Model",v.classifier_name],
  ];
  $("validation").innerHTML=items.map(([a,b])=>`<div class="val"><span>${a}</span><b>${b}</b></div>`).join("");
  const pass=v.gate_pass;
  $("gatePill").textContent=pass?"90% GATE: PASS":"90% GATE: FAIL";
  $("gatePill").className=`gate-pill ${pass?"gate-pass":"gate-fail"}`;
}
function renderBacktest(b){
  const items=[
    ["Signals",b.signals],["Winning signals",b.wins],["Losing signals",b.losses],
    ["Signal precision",`${b.signal_precision}%`],["Coverage",`${b.coverage_pct}%`],
    ["Strategy return",`${b.strategy_return_pct}%`],["Buy & hold",`${b.buy_hold_return_pct}%`],
    ["Max drawdown",`${b.max_drawdown_pct}%`],["Profit factor",b.profit_factor],
  ];
  $("backtest").innerHTML=items.map(([a,b])=>`<div class="val"><span>${a}</span><b>${b}</b></div>`).join("");
}
function renderNews(n){
  const s=n.summary||{};
  $("newsImpact").textContent=`Impact ${Number(s.impact||0)>=0?"+":""}${Number(s.impact||0).toFixed(2)}`;
  $("newsSummary").innerHTML=[
    ["Headlines",s.headline_count||0],["Positive",s.positive||0],["Negative",s.negative||0],["Neutral",s.neutral||0]
  ].map(([a,b])=>`<div><b>${b}</b><span>${a}</span></div>`).join("");
  $("newsList").innerHTML=(n.articles||[]).map(a=>`<article class="news-item"><strong>${a.title}</strong><div class="news-meta"><span>${a.publisher||""}</span><span>${Number(a.sentiment)>=0?"positive":"negative"}</span></div></article>`).join("");
}
function renderExplain(p){
  $("reasons").innerHTML=(p.explanation?.reasons||["No dominant positive reason"]).map(x=>`<div class="reason">✓ ${x}</div>`).join("");
  $("risks").innerHTML=(p.explanation?.risks||["No major rule-based risk flag"]).map(x=>`<div class="reason risk">⚠ ${x}</div>`).join("");
  $("regime").textContent=p.regime||"REGIME —";
}
function setTrust(t){
  $("trustScore").textContent=`${t.score}/100`;
  $("trustStatus").textContent=t.status;
  $("overallBadge").textContent=`TRUST: ${t.status}`;
  const good=t.status==="TRUSTED";const warn=t.status.includes("REVALIDATION")||t.status.includes("NO-TRADE");
  $("overallBadge").className=`badge ${good?"badge-green":warn?"badge-amber":"badge-red"}`;
  $("trustChecks").innerHTML=(t.checks||[]).map(x=>`<div class="panel"><span class="eyebrow">${x.name}</span><h2>${x.status}</h2><p>${x.detail}</p></div>`).join("");
}
function renderTrustReport(d){
  const p=d.prediction,repo=d.prediction.environment.repository,data=d.prediction.environment.data;
  $("trustHeadline").textContent=`${d.instrument.symbol} · ${d.interval}`;
  $("trustReport").textContent=[
    "TRUSTGRAPH REPORT",
    "-----------------",
    `Market data       : ${data}`,
    `Repository        : ${repo}`,
    `Model precision   : ${p.validation.signal_precision}%`,
    `90% gate          : ${p.validation.gate_pass?"PASS":"FAIL"}`,
    `Model version     : ${p.validation.model_version}`,
    `Regime            : ${d.regime.regime}`,
    `Signal            : ${p.signal}`,
    `Confidence        : ${p.confidence}%`,
    "",
    "Decision:",
    p.signal==="REVALIDATE"
      ? "Re-scan and accept the updated environment before treating this result as trusted."
      : (p.signal==="NO-TRADE"
        ? "The model intentionally abstained because its trust gates were not satisfied."
        : "All current trust conditions are satisfied for this paper-analysis signal.")
  ].join("\n");
}
async function analyze(force=false,full=false){
  const symbol=$("symbol").value.trim(),interval=$("interval").value;
  if(!symbol)return;
  const btn=force?$("retrainBtn"):full?$("fullBtn"):$("analyzeBtn");
  setBusy(btn,true,force?"RETRAINING…":full?"RUNNING FULL CHECK…":"ANALYZING…");
  clearMessage("marketMessage");
  $("signal").textContent="ANALYZING…";
  try{
    const d=await api(`${full?"/api/full-analysis":"/api/analyze"}?symbol=${encodeURIComponent(symbol)}&interval=${interval}&retrain=${force}`);
    state.last=d;
    $("providerBadge").textContent=`DATA: ${d.data.source}`;
    $("providerBadge").className="badge "+(d.data.status==="LIVE"?"badge-green":"badge-amber");
    $("dataState").textContent=d.data.status;
    $("modelState").textContent=d.model.gate_pass?"PASS":"FAIL";
    $("repoState").textContent=d.prediction.environment.repository;
    $("current").textContent=fmt(d.current_price);$("nextClose").textContent=fmt(d.prediction.predicted_close);
    $("nextHigh").textContent=fmt(d.prediction.predicted_high);$("nextLow").textContent=fmt(d.prediction.predicted_low);
    $("eodClose").textContent=fmt(d.prediction.predicted_eod_close);$("signal").textContent=d.prediction.signal;
    $("confidence").textContent=`Confidence ${d.prediction.confidence}%`;
    $("probability").textContent=`UP ${(d.prediction.probability_up*100).toFixed(1)}%`;
    drawChart(d.candles);renderValidation(d.model);renderBacktest(d.backtest);renderNews(d.news);renderExplain(d.prediction);
    setTrust(d.prediction.trust);renderTrustReport(d);
    message("marketMessage",`Analysis complete · ${d.retrained?"model trained":"cached model reused"} · ${d.data.source}`,"ok");
  }catch(e){ $("signal").textContent="ERROR"; message("marketMessage",e.message,"err"); }
  finally{setBusy(btn,false);}
}
$("analyzeBtn").onclick=()=>analyze(false,false);
$("retrainBtn").onclick=()=>analyze(true,false);
$("fullBtn").onclick=()=>analyze(false,true);
$("backtestBtn").onclick=()=>state.last?renderBacktest(state.last.backtest):analyze(false,false);

async function loadPulse(){
  setBusy($("pulseBtn"),true,"LOADING…");
  try{
    const d=await api("/api/pulse?limit=12");
    $("pulseGrid").innerHTML=(d.results||[]).map(x=>`<div class="pulse-item"><b>${x.symbol}</b><span>${x.name}</span><div class="${x.change_pct>=0?"pulse-up":"pulse-down"}">${x.change_pct>=0?"+":""}${Number(x.change_pct).toFixed(2)}%</div><small>${fmt(x.price)}</small></div>`).join("");
  }catch(e){message("marketMessage",e.message,"err")}finally{setBusy($("pulseBtn"),false)}
}
$("pulseBtn").onclick=loadPulse;

function renderRepository(d){
  $("repoPath").textContent=d.source?.path||"—";$("repoStateBig").textContent=d.state;$("repoFiles").textContent=Object.keys(d.current?.files||{}).length;
  $("securityScore").textContent=`${d.security_score}/100`;$("depChange").textContent=d.impact?.dependency_change?"YES":"NO";$("revalidation").textContent=d.impact?.revalidation||"—";
  const comps=d.current?.components||{};$("components").innerHTML=Object.entries(comps).map(([k,v])=>`<div class="component"><b>${k.toUpperCase()}</b><div class="hash">${v}</div></div>`).join("")||"<div class='muted'>No tracked components.</div>";
  $("impactList").innerHTML=(d.impact?.items||[]).slice(0,30).map(x=>`<div class="impact"><span class="tag">${x.impact}</span><b>${x.kind.toUpperCase()} · ${x.path}</b><div class="muted">${x.reason}</div></div>`).join("")||"<div class='muted'>No changes detected.</div>";
  $("findings").innerHTML=(d.findings||[]).map(f=>`<div class="finding ${f.severity.toLowerCase()}"><b>${f.severity}</b> · ${f.message}<code>${f.file}:${f.line}</code></div>`).join("")||"<div class='muted'>No findings.</div>";
  if(d.state==="CURRENT"){ $("repoStateBig").style.color="var(--green)"; } else if(d.state==="STALE"){ $("repoStateBig").style.color="var(--red)"; } else { $("repoStateBig").style.color="var(--amber)"; }
}
async function repoAction(path,button,label){
  setBusy(button,true,label);clearMessage("repoMessage");
  try{const d=await api(path,{method:"POST"});renderRepository(d);message("repoMessage",d.message||`Repository state: ${d.state}`,"ok");}
  catch(e){message("repoMessage",e.message,"err")} finally{setBusy(button,false);}
}
$("acceptBtn").onclick=()=>repoAction("/api/repository/accept",$("acceptBtn"),"ACCEPTING…");
$("checkBtn").onclick=()=>repoAction("/api/repository/check",$("checkBtn"),"CHECKING…");
$("simulateBtn").onclick=()=>repoAction("/api/repository/simulate",$("simulateBtn"),"SIMULATING…");
$("resetBtn").onclick=()=>repoAction("/api/repository/reset",$("resetBtn"),"RESETTING…");

async function loadAudit(){
  const d=await api("/api/audit?limit=30");
  $("audit").innerHTML=(d.results||[]).map(x=>`<div class="audit-row"><div><b>${x.event}</b><div class="muted">${x.status}</div></div><span>${new Date(x.ts).toLocaleString()}</span></div>`).join("");
}
async function loadJournal(){
  const d=await api("/api/journal?limit=60");
  const rows=d.results||[];
  $("journalTable").innerHTML=`<table class="table"><thead><tr><th>TIME</th><th>SYMBOL</th><th>TF</th><th>SIGNAL</th><th>CONFIDENCE</th><th>PRECISION</th><th>MODEL</th><th>REPO</th></tr></thead><tbody>${
    rows.map(x=>`<tr><td>${new Date(x.ts).toLocaleString()}</td><td>${x.symbol}</td><td>${x.interval}</td><td>${x.signal}</td><td>${x.confidence??"—"}%</td><td>${x.precision?Number(x.precision*100).toFixed(2):"—"}%</td><td>${x.model_version}</td><td>${x.repo_state}</td></tr>`).join("")
  }</tbody></table>`;
}
$("journalBtn").onclick=loadJournal;
$("githubBtn").onclick=async ()=>{
  const url=$("githubUrl").value.trim();
  if(!url) return message("repoMessage","Enter a public GitHub HTTPS URL.","err");
  setBusy($("githubBtn"),true,"CLONING…");
  try{
    const d=await api(`/api/repository/source/github?url=${encodeURIComponent(url)}`,{method:"POST"});
    const fresh=await api("/api/repository/check",{method:"POST"});
    renderRepository(fresh);message("repoMessage","Public GitHub repository cloned and now monitored.","ok");
  }catch(e){message("repoMessage",e.message,"err")}
  finally{setBusy($("githubBtn"),false)}
};

boot();
