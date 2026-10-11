const $ = (id) => document.getElementById(id);
const repo = "overnight_demo";

function esc(value){
  return String(value ?? "").replace(/[&<>\"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));
}
function timeLabel(value){ return value ? new Date(value).toLocaleString("en-IN", {dateStyle:"medium", timeStyle:"short"}) : "—"; }

async function json(url, options={}){
  const r = await fetch(url, options);
  const body = await r.json();
  if(!r.ok) throw new Error(body.detail || "Request failed");
  return body;
}

function renderStatus(status){
  const stale = status.stale;
  const change = status.change || {};
  const live = status.current || {};
  const last = status.last_scan;
  const acceptedFingerprint = last?.fingerprint;

  $("files").textContent = live.file_count ?? "—";
  $("lines").textContent = (live.total_lines ?? 0).toLocaleString("en-IN");
  $("critical").textContent = live.summary?.critical ?? 0;
  $("high").textContent = live.summary?.high ?? 0;
  $("low").textContent = live.summary?.low ?? 0;
  $("deps").textContent = live.dependency_files?.length ?? 0;
  $("fingerprint").textContent = live.fingerprint ? live.fingerprint.slice(0, 18) + "…" : "—";
  $("last-scan").textContent = last ? `${last.scan_id} · ${timeLabel(last.scanned_at)}` : "No accepted baseline";
  $("live-state").textContent = stale ? "CHANGED SINCE BASELINE" : (last ? "MATCHES BASELINE" : "AWAITING FIRST SCAN");

  const card = $("status-card");
  card.className = "status-card " + (stale ? "stale" : last ? "current" : "neutral");
  $("status-title").textContent = stale ? "RESULTS STALE" : last ? "BASELINE CURRENT" : "READY TO SCAN";
  $("status-copy").textContent = stale
    ? "The repository changed after the last accepted scan. The old result is kept for auditability but must not be treated as current."
    : last
      ? "No repository delta is detected. The last accepted scan still matches the live content fingerprint."
      : "Run the first scan to establish the repository baseline.";

  $("scan-age").textContent = last ? `Last scan ${timeLabel(last.scanned_at)}` : "No scan yet";
  $("finding-state").textContent = stale ? "STALE" : last ? "CURRENT" : "UNSCANNED";
  $("finding-state").className = "pill " + (stale ? "pill-bad" : last ? "pill-good" : "");

  const items = [
    ["Added", change.added?.length || 0],
    ["Modified", change.modified?.length || 0],
    ["Removed", change.removed?.length || 0],
    ["Dependencies", change.dependency_changed ? "CHANGED" : "UNCHANGED"]
  ];
  $("change-summary").innerHTML = items.map(([a,b]) => `<div><span>${a}</span><b>${esc(b)}</b></div>`).join("");
  const files = [...(change.added || []).map(x=>["+",x]), ...(change.modified || []).map(x=>["~",x]), ...(change.removed || []).map(x=>["−",x])];
  $("changed-files").innerHTML = files.length
    ? files.map(([mark,path]) => `<div class="file-delta"><b>${mark}</b><span>${esc(path)}</span></div>`).join("")
    : `<div class="muted">No file-level changes detected.</div>`;

  const findings = live.findings || [];
  $("findings").innerHTML = findings.length ? findings.map(f => `<article class="finding ${esc(f.severity)}">
    <div class="finding-top"><span class="severity">${esc(f.severity.toUpperCase())}</span><span class="category">${esc(f.category)}</span></div>
    <h3>${esc(f.title)}</h3>
    <div class="finding-meta">${esc(f.path)}${f.line ? `:${f.line}` : ""}</div>
    <p>${esc(f.detail)}</p>
  </article>`).join("") : `<div class="empty">No security or code-quality rules matched the current repository.</div>`;
}

async function refresh(){
  try { renderStatus(await json(`/api/repository?name=${repo}`)); await renderHistory(); }
  catch(e){ $("status-title").textContent="ERROR"; $("status-copy").textContent=e.message; }
}

async function scan(){
  setBusy(true, "Running scan…");
  try { const data = await json(`/api/repository/scan?name=${repo}`, {method:"POST"}); renderStatus(data.status); await renderHistory(); }
  catch(e){ alert(e.message); }
  finally { setBusy(false); }
}

async function simulate(){
  setBusy(true, "Applying overnight update…");
  try { const data = await json(`/api/repository/simulate-update?name=${repo}`, {method:"POST"}); renderStatus(data.status); await renderHistory(); }
  catch(e){ alert(e.message); }
  finally { setBusy(false); }
}

async function reset(){
  setBusy(true, "Resetting demo…");
  try { const data = await json(`/api/repository/reset?name=${repo}`, {method:"POST"}); renderStatus(data.status); await renderHistory(); }
  catch(e){ alert(e.message); }
  finally { setBusy(false); }
}

async function renderHistory(){
  const data = await json(`/api/history?name=${repo}`);
  const rows = (data.history || []).slice().reverse();
  $("history").innerHTML = rows.length ? rows.map((x,i) => `<div class="history-row">
    <div class="timeline-dot"></div><div><b>${esc(x.scan_id)}</b><span>${timeLabel(x.scanned_at)}</span></div>
    <div class="history-stats"><span>${x.file_count} files</span><span>${x.summary.total} findings</span><code>${esc((x.fingerprint||"").slice(0,12))}</code></div>
  </div>`).join("") : `<div class="empty">No accepted scans yet. The challenge starts with a clean baseline.</div>`;
}

function setBusy(busy, text=""){
  for(const id of ["run-scan","simulate","reset"]) $(id).disabled = busy;
  if(text) $("status-title").textContent = text;
}

$("run-scan").addEventListener("click", scan);
$("simulate").addEventListener("click", simulate);
$("reset").addEventListener("click", reset);
refresh();
