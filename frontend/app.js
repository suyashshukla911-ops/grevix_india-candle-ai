const $ = (id) => document.getElementById(id);
const fmt = (n, d = 2) => Number.isFinite(Number(n))
  ? Number(n).toLocaleString('en-IN', {minimumFractionDigits: d, maximumFractionDigits: d})
  : '—';

async function api(url, options = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {...options, signal: controller.signal, cache: 'no-store'});
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : {detail: await response.text()};
    if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
    return payload;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The operation took too long. Try again; cached analyses should be fast.');
    if (error instanceof TypeError) throw new Error('The local API is not reachable. Confirm that Uvicorn is still running on 127.0.0.1:8000.');
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function showAlert(el, msg, kind = '') {
  el.textContent = msg;
  el.className = `alert ${kind}`.trim();
  el.classList.remove('hidden');
}
function hideAlert(el) { el.classList.add('hidden'); }
function setBadge(el, text, kind = 'neutral') { el.textContent = text; el.className = `badge ${kind}`; }
function setBusy(button, busy, busyText) {
  if (!button) return;
  if (!button.dataset.readyText) button.dataset.readyText = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? busyText : button.dataset.readyText;
}

function switchView(view) {
  document.querySelectorAll('.view').forEach(x => x.classList.toggle('active', x.id === `${view}View`));
  document.querySelectorAll('.nav-btn').forEach(x => x.classList.toggle('active', x.dataset.view === view));
  if (view === 'repo') loadRepo();
}

document.querySelectorAll('.nav-btn').forEach(b => b.addEventListener('click', () => switchView(b.dataset.view)));
document.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => switchView('repo')));

async function boot() {
  try {
    const [health, stocks, env, pulse] = await Promise.all([
      api('/api/health'), api('/api/stocks'), api('/api/repository/status'), api('/api/market/overview')
    ]);
    $('repoPath').textContent = health.monitored_repository;
    setBadge($('modeBadge'), 'LOCAL OFFLINE MODE', 'good');
    $('symbol').innerHTML = stocks.results.map(s => `<option value="${s.symbol}">${s.symbol} — ${s.name}</option>`).join('');
    $('symbol').value = stocks.default_symbol;
    $('interval').value = String(stocks.default_interval);
    renderEnvironment(env);
    renderPulse(pulse);
  } catch (e) {
    showAlert($('globalAlert'), e.message, 'error');
  }
}

function renderEnvironment(s) {
  const stale = s.state === 'STALE';
  setBadge($('envBadge'), `ENVIRONMENT: ${s.state}`, stale ? 'bad' : s.state === 'CURRENT' ? 'good' : 'neutral');
  if (stale) {
    showAlert($('globalAlert'), 'Repository changed since the last accepted scan. Previous model verdicts are stale until the repository is rescanned.', 'error');
  } else if (s.state === 'READY') {
    showAlert($('globalAlert'), 'No repository baseline yet. Scan and accept the source environment before trusting a model signal.', 'warn');
  } else {
    hideAlert($('globalAlert'));
  }
}

function drawChart(candles, pred) {
  const canvas = $('chart');
  if (!canvas || !candles?.length) return;
  const ctx = canvas.getContext('2d');
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const cssW = Math.max(360, canvas.clientWidth || 800);
  const cssH = 390;
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  const data = candles.slice(-60);
  const highs = data.map(x => x.high);
  const lows = data.map(x => x.low);
  const hi = Math.max(...highs, pred.predicted_high);
  const lo = Math.min(...lows, pred.predicted_low);
  const pad = Math.max((hi - lo) * 0.08, 0.01);
  const top = 25, bottom = 22, left = 52, right = 18;
  const chartH = cssH - top - bottom;
  const chartW = cssW - left - right;
  const y = v => top + (hi + pad - v) / (hi - lo + 2 * pad) * chartH;
  const x = i => left + (i / Math.max(1, data.length - 1)) * chartW;

  ctx.strokeStyle = '#e4eaf1';
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) {
    const yy = top + i * chartH / 4;
    ctx.beginPath(); ctx.moveTo(left, yy); ctx.lineTo(cssW - right, yy); ctx.stroke();
  }

  data.forEach((d, i) => {
    const xx = x(i), oy = y(d.open), cy = y(d.close), hy = y(d.high), ly = y(d.low);
    const up = d.close >= d.open;
    ctx.strokeStyle = up ? '#138a5b' : '#cc3d4f';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(xx, hy); ctx.lineTo(xx, ly); ctx.stroke();
    const bw = Math.max(3, chartW / data.length * 0.55);
    ctx.fillStyle = up ? '#d9f4e8' : '#fde1e5';
    ctx.fillRect(xx - bw / 2, Math.min(oy, cy), bw, Math.max(2, Math.abs(cy - oy)));
    ctx.strokeRect(xx - bw / 2, Math.min(oy, cy), bw, Math.max(2, Math.abs(cy - oy)));
  });

  const lastX = x(data.length - 1);
  const px = Math.min(cssW - right, lastX + chartW / data.length);
  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = '#1769e0';
  ctx.beginPath(); ctx.moveTo(lastX, y(data[data.length - 1].close)); ctx.lineTo(px, y(pred.predicted_close)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#1769e0';
  ctx.beginPath(); ctx.arc(px, y(pred.predicted_close), 4, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#63788f'; ctx.font = '11px sans-serif';
  ctx.fillText(fmt(hi), 6, top + 4);
  ctx.fillText(fmt(lo), 6, cssH - bottom);
}

function renderAnalysis(d) {
  const v = d.validation;
  $('chartTitle').textContent = `${d.instrument.symbol} · ${d.interval}m`;
  $('mCurrent').textContent = fmt(d.current_price);
  $('mNext').textContent = fmt(d.prediction.predicted_close);
  $('mHigh').textContent = fmt(d.prediction.predicted_high);
  $('mLow').textContent = fmt(d.prediction.predicted_low);
  $('mEod').textContent = fmt(d.prediction.predicted_eod_close);
  $('mSignal').textContent = d.trusted_signal;
  $('latencyBadge').textContent = `${d.latency_ms} ms${d.latency_ms < 1500 ? ' · FAST' : ''}`;

  const p = Math.round(d.prediction.probability_up * 100);
  setBadge($('probBadge'), `MODEL UP ${p}%`, p >= 60 ? 'good' : p <= 40 ? 'bad' : 'warn');
  setBadge($('newsImpact'), `Impact ${d.news.summary.impact >= 0 ? '+' : ''}${d.news.summary.impact}`, d.news.summary.impact > 0.15 ? 'good' : d.news.summary.impact < -0.15 ? 'bad' : 'warn');
  setBadge($('gateBadge'), v.gate_met ? `90% GATE PASS · ${v.signal_precision}%` : `90% GATE NOT MET`, v.gate_met ? 'good' : 'warn');

  drawChart(d.candles, d.prediction);
  $('newsSummary').innerHTML = `
    <div><b>${d.news.summary.headline_count}</b><span>headlines</span></div>
    <div><b>${d.news.summary.positive}</b><span>positive</span></div>
    <div><b>${d.news.summary.negative}</b><span>negative</span></div>
    <div><b>${d.news.summary.neutral}</b><span>neutral</span></div>`;
  $('newsList').innerHTML = d.news.articles.map(a => `<div class="news-item"><h4>${a.title}</h4><div class="news-meta">${a.event} · impact ${a.impact}</div></div>`).join('');
  $('validation').innerHTML = `
    <div><span>Direction accuracy</span><b>${v.direction_accuracy}%</b><small>overall walk-forward</small></div>
    <div><span>90% signal precision</span><b>${v.signal_precision}%</b><small>${v.gate_met ? 'gate passed' : 'gate not supported'}</small></div>
    <div><span>Signal coverage</span><b>${v.signal_coverage}%</b><small>${v.qualified_signals} qualified rows</small></div>
    <div><span>Next-return MAE</span><b>${v.next_return_mae}</b><small>validation error</small></div>
    <div><span>Operating threshold</span><b>${v.threshold}</b><small>probability cutoff</small></div>
    <div><span>Validation rows</span><b>${v.validation_rows}</b><small>strict time split</small></div>`;

  if (d.trust_state === 'STALE') {
    showAlert($('globalAlert'), `${d.trust_note} The model calculation is shown for inspection, but the trusted signal is REVALIDATE.`, 'error');
  } else if (!v.gate_met) {
    showAlert($('globalAlert'), `${v.gate_note} The system will not issue a trusted BUY/SELL signal for this stock/timeframe.`, 'warn');
  } else {
    showAlert($('globalAlert'), `${v.gate_note} This is a validation precision gate, not a guarantee of future returns.`, 'success');
  }
}

async function analyze(retrain = false) {
  const button = retrain ? $('retrainBtn') : $('analyzeBtn');
  try {
    setBusy(button, true, retrain ? 'RECALIBRATING…' : 'ANALYZING…');
    const d = await api(`/api/analyze?symbol=${encodeURIComponent($('symbol').value)}&interval=${$('interval').value}&retrain=${retrain}`, {}, retrain ? 30000 : 20000);
    renderAnalysis(d);
  } catch (e) {
    showAlert($('globalAlert'), e.message, 'error');
  } finally {
    setBusy(button, false, '');
  }
}

$('analyzeBtn').addEventListener('click', () => analyze(false));
$('retrainBtn').addEventListener('click', () => analyze(true));

function renderPulse(d) {
  $('pulse').innerHTML = d.results.map(r => `<div class="pulse-item"><b>${r.symbol}</b><span>${fmt(r.price)} · <span class="${r.change_pct >= 0 ? 'pos' : 'neg'}">${r.change_pct >= 0 ? '+' : ''}${r.change_pct}%</span></span></div>`).join('');
}
async function refreshPulse() {
  try { renderPulse(await api('/api/market/overview')); }
  catch (e) { showAlert($('globalAlert'), e.message, 'error'); }
}
$('pulseBtn').addEventListener('click', refreshPulse);

function renderRepo(s) {
  renderEnvironment(s);
  setBadge($('envBadge'), `ENVIRONMENT: ${s.state}`, s.state === 'CURRENT' ? 'good' : s.state === 'STALE' ? 'bad' : 'neutral');
  $('rState').textContent = s.state;
  $('rFiles').textContent = s.accepted?.files ?? '—';
  $('rLines').textContent = s.accepted?.lines ?? '—';
  const findings = s.accepted?.findings || [];
  $('rCritical').textContent = findings.filter(x => x.severity === 'CRITICAL').length;
  $('rHigh').textContent = findings.filter(x => x.severity === 'HIGH').length;
  $('rDeps').textContent = s.accepted?.dependency_files ?? '—';
  $('acceptedFp').textContent = s.accepted?.fingerprint || 'No baseline';
  $('liveFp').textContent = s.live_fingerprint;
  $('changeCounts').innerHTML = `
    <div><b>${s.changes.added.length}</b><span>added</span></div>
    <div><b>${s.changes.modified.length}</b><span>modified</span></div>
    <div><b>${s.changes.removed.length}</b><span>removed</span></div>
    <div><b>${s.changes.dependencies_changed ? 'YES' : 'NO'}</b><span>dependency change</span></div>`;
  const changes = [];
  s.changes.added.forEach(x => changes.push(`<div class="news-item"><strong>ADDED</strong> · ${x}</div>`));
  s.changes.modified.forEach(x => changes.push(`<div class="news-item"><strong>MODIFIED</strong> · ${x}</div>`));
  s.changes.removed.forEach(x => changes.push(`<div class="news-item"><strong>REMOVED</strong> · ${x}</div>`));
  $('changes').innerHTML = changes.join('') || '<div class="news-item">No file-level changes detected.</div>';
  setBadge($('scanBadge'), s.accepted ? 'ACCEPTED SCAN' : 'NOT SCANNED', s.accepted ? 'good' : 'neutral');
  $('findings').innerHTML = findings.length
    ? findings.map(f => `<div class="finding"><div class="sev">${f.severity}</div><div class="cat">${f.category}/${f.rule}</div><div class="msg">${f.message}<br><code>${f.file}:${f.line}</code></div></div>`).join('')
    : '<div class="news-item">No security or code-quality rules matched the accepted scan.</div>';
}

async function loadRepo() {
  try {
    const [status, history] = await Promise.all([api('/api/repository/status'), api('/api/repository/history')]);
    renderRepo(status);
    $('history').innerHTML = history.history.length
      ? history.history.map(x => `<div class="history-item"><span>${new Date(x.scanned_at).toLocaleString()}</span><code>${x.fingerprint.slice(0, 16)}… · ${x.findings.length} findings</code></div>`).join('')
      : '<div class="news-item">No accepted scans yet.</div>';
  } catch (e) {
    showAlert($('repoAlert'), e.message, 'error');
  }
}

async function repoAction(button, text, fn) {
  try {
    setBusy(button, true, text);
    const status = await fn();
    renderRepo(status);
    const history = await api('/api/repository/history');
    $('history').innerHTML = history.history.length
      ? history.history.map(x => `<div class="history-item"><span>${new Date(x.scanned_at).toLocaleString()}</span><code>${x.fingerprint.slice(0, 16)}… · ${x.findings.length} findings</code></div>`).join('')
      : '<div class="news-item">No accepted scans yet.</div>';
  } catch (e) {
    showAlert($('repoAlert'), e.message, 'error');
  } finally {
    setBusy(button, false, '');
  }
}

$('scanBtn').addEventListener('click', () => repoAction($('scanBtn'), 'SCANNING…', () => api('/api/repository/scan', {method: 'POST'})));
$('checkBtn').addEventListener('click', () => repoAction($('checkBtn'), 'CHECKING…', () => api('/api/repository/status')));
$('simulateBtn').addEventListener('click', () => repoAction($('simulateBtn'), 'SIMULATING…', () => api('/api/repository/simulate-overnight-update', {method: 'POST'})));
$('resetBtn').addEventListener('click', () => repoAction($('resetBtn'), 'RESETTING…', () => api('/api/repository/reset', {method: 'POST'})));

window.addEventListener('resize', () => {
  // Redraw the latest chart only when a result exists; resizing never calls the API.
  if (window.__lastAnalysis) drawChart(window.__lastAnalysis.candles, window.__lastAnalysis.prediction);
});
const originalRenderAnalysis = renderAnalysis;
renderAnalysis = (d) => { window.__lastAnalysis = d; originalRenderAnalysis(d); };

boot();
