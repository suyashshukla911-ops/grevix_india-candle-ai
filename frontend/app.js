const qs = (id) => document.getElementById(id);
let timer = null;
let lastSymbol = "";

function fmt(x, digits=2){ return Number.isFinite(Number(x)) ? Number(x).toLocaleString("en-IN",{minimumFractionDigits:digits,maximumFractionDigits:digits}) : "—"; }
function pct(x){ return Number.isFinite(Number(x)) ? `${(Number(x)*100).toFixed(2)}%` : "—"; }

async function getJSON(url){
  const r = await fetch(url);
  const j = await r.json();
  if(!r.ok) throw new Error(j.detail || "Request failed");
  return j;
}

async function boot(){
  try{
    const h = await getJSON("/api/health");
    qs("status").textContent = h.upstox_connected ? "● Upstox connected" : "○ Upstox not connected";
    if(!h.upstox_connected) qs("status").style.color = "#f0c771";
    const p = await getJSON("/api/priority");
    pulse();
    qs("priority-list").innerHTML = p.stocks.map(s => `<option value="${s.symbol}">${s.name}</option>`).join("");
    if(!qs("symbol").value && p.stocks.length) qs("symbol").value = p.stocks[0].symbol;
  }catch(e){ qs("status").textContent = e.message; }
}

function drawChart(rows, pred){
  const x = rows.map(r => r.time);
  const trace = {
    x, open: rows.map(r=>r.open), high: rows.map(r=>r.high), low: rows.map(r=>r.low), close: rows.map(r=>r.close),
    increasing:{line:{color:"#37d49a"}}, decreasing:{line:{color:"#ff5f6d"}},
    type:"candlestick", name:"Market"
  };
  const markerX = [x[x.length-1]];
  const markerY = [rows[rows.length-1].close];
  const predTrace = {x:markerX,y:markerY,type:"scatter",mode:"markers",marker:{size:7,color:"#77c7ff"},name:"Now"};
  const layout = {
    paper_bgcolor:"#0b1729", plot_bgcolor:"#0b1729", margin:{l:45,r:12,t:15,b:30},
    xaxis:{rangeslider:{visible:false},gridcolor:"#15324e",color:"#7892ae"},
    yaxis:{gridcolor:"#15324e",color:"#7892ae"},
    font:{color:"#cfe4f6"},
    showlegend:false
  };
  Plotly.react("chart",[trace,predTrace],layout,{displaylogo:false,responsive:true});
}

function renderNews(n){
  const s=n.summary;
  qs("news-score").textContent=`Impact ${Number(s.impact||0)>=0?"+":""}${Number(s.impact||0).toFixed(3)}`;
  qs("news-score").className="pill "+(s.impact>0.15?"good":s.impact<-0.15?"bad":"warn");
  qs("news-summary").innerHTML=`
    <div><b>${s.headline_count}</b><span>headlines</span></div>
    <div><b>${s.positive}</b><span>positive</span></div>
    <div><b>${s.negative}</b><span>negative</span></div>
  `;
  qs("news-list").innerHTML=(n.articles||[]).map(a=>{
    const cls=a.sentiment>0.15?"tag-pos":a.sentiment<-0.15?"tag-neg":"tag-neu";
    return `<article class="news-item">
      <a href="${a.url}" target="_blank" rel="noopener noreferrer">${a.title}</a>
      <div class="news-meta"><span>${a.domain}</span><span>${a.event}</span><span class="${cls}">${a.sentiment>0.15?"positive":a.sentiment<-0.15?"negative":"neutral"}</span><span>impact ${Number(a.impact).toFixed(3)}</span></div>
    </article>`;
  }).join("") || `<div class="muted">No fresh company-linked headlines found.</div>`;
}

function renderValidation(v){
  const items=[
    ["Direction accuracy",`${v.direction_accuracy.toFixed(2)}%`],
    ["Signal precision",`${v.signal_precision.toFixed(2)}%`],
    ["Signal coverage",`${v.signal_coverage.toFixed(2)}%`],
    ["Next-return MAE",v.next_return_mae.toFixed(6)],
    ["Decision threshold",v.threshold.toFixed(2)],
    ["Validation rows",`${v.validation_rows ?? "—"}`]
  ];
  qs("validation").innerHTML=items.map(([a,b])=>`<div class="val"><span>${a}</span><b>${b}</b></div>`).join("");
}

async function analyze(force=false){
  const symbol=(qs("symbol").value||"").trim();
  const interval=qs("interval").value;
  if(!symbol) return;
  lastSymbol=symbol;
  qs("analyze").disabled=true;
  qs("signal").textContent="Loading…";
  try{
    const d=await getJSON(`/api/analyze?symbol=${encodeURIComponent(symbol)}&interval=${interval}&retrain=${force}`);
    qs("title").textContent=`${d.instrument.name} · ${d.instrument.symbol} · ${d.interval}m`;
    qs("timestamp").textContent=`Last candle ${new Date(d.last_timestamp).toLocaleString("en-IN")}`;
    qs("current").textContent=fmt(d.current_price);
    qs("next-close").textContent=fmt(d.prediction.predicted_close);
    qs("next-high").textContent=fmt(d.prediction.predicted_high);
    qs("next-low").textContent=fmt(d.prediction.predicted_low);
    qs("eod-close").textContent=fmt(d.prediction.predicted_eod_close);
    qs("signal").textContent=d.prediction.signal;
    const up=d.prediction.probability_up;
    qs("probability").textContent=`UP ${(up*100).toFixed(1)}% · DOWN ${((1-up)*100).toFixed(1)}%`;
    qs("probability").className="pill "+(up>=0.62?"good":up<=0.38?"bad":"warn");
    drawChart(d.candles,d.prediction);
    renderNews(d.news);
    renderValidation(d.prediction.validation);
    qs("status").textContent=`● Live · ${d.instrument.exchange} · auto-refresh 60s`;
    qs("status").style.color="#8ff2b3";
    if(timer) clearInterval(timer);
    timer=setInterval(()=>analyze(false), 60000);
  }catch(e){
    qs("signal").textContent="ERROR";
    qs("status").textContent=e.message;
    qs("status").style.color="#ff9aa7";
  }finally{
    qs("analyze").disabled=false;
  }
}

qs("analyze").addEventListener("click",()=>analyze(false));
qs("retrain").addEventListener("click",()=>analyze(true));
qs("symbol").addEventListener("keydown",(e)=>{ if(e.key==="Enter") analyze(false); });
qs("interval").addEventListener("change",()=>{ if(lastSymbol) analyze(false); });

boot();


async function pulse(){
  try{
    const d=await getJSON("/api/market-pulse?limit=50");
    qs("pulse-grid").innerHTML=(d.results||[]).map(x=>{
      const up=Number(x.change_pct)>=0;
      return `<div class="pulse-item">
        <b>${x.symbol}</b><span>${x.name}</span>
        <div class="${up?"pulse-up":"pulse-down"}">${up?"+":""}${Number(x.change_pct).toFixed(2)}%</div>
      </div>`;
    }).join("");
  }catch(e){
    qs("pulse-grid").innerHTML=`<div class="muted">${e.message}</div>`;
  }
}
qs("pulse").addEventListener("click",pulse);
