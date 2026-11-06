/* AgriSahayak laptop dashboard. Plain JavaScript, no build step, works offline. */
const S = { status: null, live: null, records: [], page: 'overview', prevCount: null, filter: { q: '', cat: 'all', crop: 'all' } };
const PAGES = {
  overview: ['Overview', 'Field health at a glance'],
  live: ['Live Monitor', 'Real-time view from the rover camera'],
  rover: ['Rover Tools', 'Sensors, pump, servo and safety of the Arduino'],
  support: ['Farmer Support Desk', 'Prepare a request and connect to government agriculture support'],
  records: ['Records', 'Every photo and clip captured by the rover'],
};
const J = (u, o) => fetch(u, o).then(r => r.json());
const post = (u, b) => J(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
const prettyLabel = l => String(l || '').replace(/___/g, ' - ').replace(/__/g, ' ').replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
const lang = () => $('lang').value;

/* ---------- record helpers ---------- */
function recCat(r) {                       // which group a record belongs to
  const res = r.result || {};
  if (res.status === 'produce' || res.status === 'produce_hint') return 'produce';
  if (r.kind === 'video' || !res.label) return null;
  return (res.reasons || []).length ? 'review' : res.category;
}
const photos = () => S.records.filter(r => r.kind === 'photo' && r.result && (r.result.label || r.result.status === 'produce_hint'));
const colorOf = c => (CATS[c] || {}).color || 'var(--text-3)';
const t_time = r => (r.ts || '').slice(11, 19), t_date = r => (r.ts || '').slice(0, 10);

/* ---------- routing ---------- */
function route() {
  const h = (location.hash || '#/overview').replace('#/', '');
  const p = PAGES[h] ? h : 'overview';
  if (S.page === 'live' && p !== 'live') sendStop();
  S.page = p;
  document.querySelectorAll('.page').forEach(el => el.classList.toggle('on', el.id === 'page-' + p));
  document.querySelectorAll('nav a').forEach(a => a.classList.toggle('active', a.dataset.page === p));
  $('title').textContent = PAGES[p][0]; $('sub').textContent = PAGES[p][1];
  $('pages').classList.toggle('fill', p === 'live');
  render();
  if (p === 'live' || p === 'rover') pollLive();
}
window.addEventListener('hashchange', route);

function render() {
  if (S.page === 'overview') { renderKpis(); renderLatest(); renderMix(); renderHealth(); renderBars(); renderRecent(); renderMap(); }
  if (S.page === 'records') renderRecords();
}

/* ---------- government agriculture support ---------- */
let supportNote = '';
if ($('supportBuild')) $('supportBuild').onclick = async () => {
  const crop = $('supportCrop').value.trim(), district = $('supportDistrict').value.trim(), issue = $('supportIssue').value.trim(),
    field_details = $('supportField').value.trim();
  if (!issue) { toast('Describe the help needed', 'For example: crop loss, crop loan, a disease check, or soil testing.'); $('supportIssue').focus(); return; }
  const button = $('supportBuild'); button.disabled = true; button.textContent = 'Finding support...';
  try {
    const j = await post('/api/support/recommend', { crop, district, issue, field_details, cultivator: $('supportCultivator').value });
    if (!j.ok) throw new Error(j.error || 'Could not find support routes.');
    supportNote = j.call_note || '';
    const cards = (j.recommendations || []).map((r, i) => '<div style="margin:8px 0;padding:10px;border:1px solid var(--line);border-radius:10px"><b>' +
      (i === 0 ? 'Best match: ' : 'Also check: ') + esc(r.name) + '</b><div class="dim" style="margin:5px 0">' + esc(r.reason) + '</div><div class="dim">' + esc(r.description) + '</div><a class="link" href="' + esc(r.url) + '" target="_blank" rel="noopener">Open official information</a></div>').join('');
    $('supportDraft').innerHTML = cards + '<p class="dim" style="font-size:11px;line-height:1.5">' + esc(j.notice || '') +
      (j.location_needed ? ' Add your district and state to narrow state-specific options.' : '') + '</p><details><summary>Call note to copy</summary><pre style="white-space:pre-wrap;font:inherit">' + esc(supportNote) + '</pre></details>';
    $('supportCopy').disabled = !supportNote;
    toast('Fasal Saathi updated', 'It can use this crop and field profile for support questions while the server is running.');
  } catch (e) { toast('Support search failed', e.message || 'Check that the dashboard server is running.'); }
  finally { button.disabled = false; button.textContent = 'Find best-fit support'; }
};
if ($('loadDemoProfile')) $('loadDemoProfile').onclick = () => {
  $('supportCrop').value = 'Tomato';
  $('supportDistrict').value = '';
  $('supportCultivator').value = '';
  $('supportField').value = 'DEMO SAMPLE ONLY: Tomato plot, 0.5 acre, irrigated; flowering/fruiting stage (sample). Soil type, soil test and pH are unknown. District/state and cultivator status are not provided. One leaf scan needs local review.';
  $('supportIssue').value = 'DEMO SAMPLE ONLY: Survey this tomato field, find relevant government horticulture schemes and crop-insurance support, check local availability, and refer the uncertain leaf scan to a local agriculture specialist. Do not assume eligibility or benefit amounts.';
  $('supportBuild').click();
};
if ($('supportCopy')) $('supportCopy').onclick = async () => {
  if (!supportNote) return;
  try { await navigator.clipboard.writeText(supportNote); toast('Call note copied', 'You can paste it into a message or read it aloud.'); }
  catch (e) { toast('Could not copy', 'Select the note and copy it manually.'); }
};

/* ---------- overview ---------- */
function renderKpis() {
  const ph = photos(), cats = { healthy: 0, review: 0, dis: 0 };
  let produceCount = 0;
  ph.forEach(r => { const c = recCat(r); if (c === 'produce') produceCount += Object.values((r.result || {}).produce_counts || {}).reduce((a, n) => a + Number(n || 0), 0); else if (c === 'healthy') cats.healthy++; else if (c === 'review') cats.review++; else cats.dis++; });
  $('kTotal').textContent = S.records.length;
  $('kTotalSub').textContent = ph.length + ' photos, ' + (S.records.length - S.records.filter(r => r.kind === 'photo').length) + ' clips';
  $('kHealthy').textContent = cats.healthy; $('kDis').textContent = cats.dis; $('kRev').textContent = cats.review;
  $('kProduce').textContent = produceCount;
  const conf = cats.healthy + cats.dis;
  $('kHealthySub').textContent = conf ? Math.round(cats.healthy / conf * 100) + '% of confident results' : 'no confident results yet';
}
function renderLatest() {
  const r = photos()[0], el = $('cLatest');
  if (!r) { el.innerHTML = '<h3>Latest scan</h3><div class="empty">' + icon('camera') + '<b>No scans yet</b>Take a photo on the tablet and it will appear here.</div>'; return; }
  const res = r.result, c = recCat(r);
  el.innerHTML = '<h3><span class="grow">Latest scan</span><span class="dim" style="text-transform:none;letter-spacing:0">' + esc(t_date(r) + ' ' + t_time(r)) + '</span></h3>' +
    '<div class="latest"><div class="img"><img src="/api/file/' + esc(r.id) + '" alt=""></div><div>' +
    '<div class="row">' + catChip(c) + (r.soil != null ? '<span class="chip">' + icon('drop') + ' ' + esc(r.soil) + '%</span>' : '') + '</div>' +
    '<h2>' + esc(r.name) + '</h2><div class="meta">' + esc(r.plot) + ' &middot; ' + esc(r.field) + (r.acc ? ' &middot; GPS &plusmn;' + Math.round(r.acc) + ' m' : r.lat != null ? ' &middot; GPS' : '') + '</div>' +
    '<div class="row" style="margin-top:12px">' + ring(res.confidence, 58, colorOf(c), pct(res.confidence) + '%') +
    '<span class="dim" style="font-size:12px">' + (res.status === 'produce' ? 'top object confidence' : 'model confidence') + '</span></div>' +
    '<div class="adv">' + esc(r.text) + '</div>' +
    '<div class="row" style="margin-top:12px"><button class="btn sm" onclick="speakRec(\'' + esc(r.id) + '\')">' + icon('volume') + ' Speak</button>' +
    '<button class="btn sm ghost" onclick="openDrawer(\'' + esc(r.id) + '\')">Details</button></div></div></div>';
}
function donut(parts, size, top, sub) {
  const total = parts.reduce((a, p) => a + p.v, 0), r = size / 2 - 13, C = 2 * Math.PI * r;
  let acc = 0, segs = '';
  parts.filter(p => p.v > 0).forEach(p => {
    const len = Math.max(0, p.v / total * C - (parts.filter(q => q.v > 0).length > 1 ? 3 : 0));
    segs += '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="' + p.c + '" stroke-width="16" stroke-dasharray="' + len.toFixed(1) + ' ' + (C - len).toFixed(1) + '" stroke-dashoffset="' + (-acc).toFixed(1) + '" transform="rotate(-90 ' + size / 2 + ' ' + size / 2 + ')"/>';
    acc += p.v / total * C;
  });
  return '<svg viewBox="0 0 ' + size + ' ' + size + '" width="' + size + '" height="' + size + '"><circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="var(--surface-3)" stroke-width="16"/>' + segs +
    '<text x="50%" y="48%" text-anchor="middle" fill="var(--text)" font-size="30" font-weight="700">' + top + '</text>' +
    '<text x="50%" y="62%" text-anchor="middle" fill="var(--text-3)" font-size="11">' + sub + '</text></svg>';
}
function renderMix() {
  const order = ['healthy', 'fungal', 'bacterial', 'viral', 'pest', 'review'], n = {};
  order.forEach(k => n[k] = 0); photos().forEach(r => { const c = recCat(r); if (Object.prototype.hasOwnProperty.call(n, c)) n[c]++; });
  const total = order.reduce((a, k) => a + n[k], 0);
  if (!total) { $('cMix').innerHTML = '<div class="empty">' + icon('activity') + 'Results will be summarised here.</div>'; return; }
  $('cMix').innerHTML = '<div class="mix">' + donut(order.map(k => ({ v: n[k], c: colorOf(k) })), 150, total, 'diagnoses') +
    '<div class="legend">' + order.map(k => '<div><i style="background:' + colorOf(k) + '"></i>' + CATS[k].en + '<b>' + n[k] + '</b></div>').join('') + '</div></div>';
}
function hrow(dot, k, v) { return '<div class="hrow"><span class="dot ' + dot + '"></span><span class="k">' + k + '</span><b>' + v + '</b></div>'; }
function renderHealth() {
  const s = S.status; if (!s) { $('cHealth').innerHTML = '<div class="empty">Connecting...</div>'; return; }
  const live = s.frame_age != null && s.frame_age < 4, t = s.tablet || {};
  const serverLabel = s.port ? 'Available · port ' + s.port : 'Available';
  const g = s.gps;
  $('cHealth').innerHTML = '<div class="health">' +
    hrow(s.model === 'ready' ? 'ok' : 'bad', 'Disease model', s.model === 'ready' ? 'Ready (' + esc(s.device) + ')' : 'Not ready') +
    hrow(s.produce_model && (s.produce_model === 'Ready' || s.produce_model.startsWith('Installed')) ? 'ok' : 'warn', 'Produce counter', esc(s.produce_model || 'Not installed')) +
    hrow(s.tomato_fruit_model && (s.tomato_fruit_model === 'Ready' || s.tomato_fruit_model.startsWith('Installed')) ? 'ok' : 'warn', 'Tomato fruit screen', esc(s.tomato_fruit_model || 'Not installed')) +
    hrow(s.gate === 'ready' ? 'ok' : 'warn', 'Leaf check', s.gate === 'ready' ? 'Ready' : 'Off') +
    hrow(t.online ? 'ok' : 'warn', 'Tablet', t.online ? (live ? 'Online, camera live' : 'Online') : 'Offline') +
    hrow(/^Arduino/.test(s.rover) ? 'ok' : 'warn', 'Rover link', /^Arduino/.test(s.rover) ? (/tablet/.test(s.rover) ? 'Arduino via tablet' : 'Arduino (laptop)') : 'Simulation') +
    hrow(s.soil != null ? 'ok' : 'warn', 'Soil sensor', s.soil != null ? esc(s.soil) + '%' : 'No data') +
    hrow(g ? 'ok' : 'warn', 'GPS', g ? '&plusmn;' + Math.round(g.acc || 0) + ' m (' + esc(g.src) + ')' : 'No fix') +
    hrow('ok', 'Field', esc(s.field || '-')) +
    hrow('ok', 'Dashboard server', esc(serverLabel)) + hrow(s.server_mem_mb && s.server_mem_mb > 3000 ? 'bad' : 'ok', 'Server memory', s.server_mem_mb ? s.server_mem_mb + ' MB' : '-') + '</div>';
}
function renderBars() {
  const ph = photos().filter(r => recCat(r) !== 'produce').slice(0, 12).reverse();
  if (!ph.length) { $('cBars').innerHTML = '<div class="empty">' + icon('activity') + 'Confidence bars appear after the first scans.</div>'; return; }
  $('cBars').innerHTML = '<div class="bars">' + ph.map(r => '<div class="col" title="' + esc(r.name) + '"><span class="v">' + pct(r.result.confidence) + '</span><div class="b" style="height:' + Math.max(4, pct(r.result.confidence) * 1.05) + 'px;background:' + colorOf(recCat(r)) + '"></div><small>' + esc(r.plot) + '</small></div>').join('') + '</div>';
}
const gpsChip = r => r.lat != null ? '<span class="chip">' + icon('pin') + ' ' + (r.acc ? '&plusmn;' + Math.round(r.acc) + ' m' : 'GPS') + '</span>' : '';
function rowHtml(r, full) {
  const res = r.result || {}, c = recCat(r);
  const th = r.kind === 'video' ? '<div class="thv">' + icon('video') + '</div>' : '<img class="th" loading="lazy" src="/api/thumb/' + esc(r.id) + '" alt="">';
  const diag = r.kind === 'video' ? '<span class="dim">Video clip</span>' : res.status === 'no_model' ? '<span class="dim">Model not installed</span>' :
    res.status === 'not_plant' ? '<div class="nm">' + esc(res.scene_name || 'No supported plant or produce detected') + '</div><div class="sub"><span class="chip uncertain">' + esc(res.scene ? 'Not a leaf or produce' : 'Uncertain view') + '</span></div>' :
    res.status === 'produce_hint' ? '<div class="nm">' + esc(res.candidate || 'Possible produce') + '</div><div class="sub"><span class="chip produce">Unconfirmed image hint; no box or count</span></div>' :
    (res.status === 'produce' ? '<div class="nm">Analysis</div><div class="sub">' + esc(produceAnalysisSummary(res)) + '</div><div class="sub">' + catChip(c) + '</div>' : '<div class="nm">' + esc(r.name) + '</div><div class="sub">' + catChip(c) + '</div>');
  const conf = res.confidence != null ? '<div class="mini"><div class="meter"><i style="width:' + pct(res.confidence) + '%;background:' + colorOf(c) + '"></i></div><span class="mono">' + pct(res.confidence) + '%</span></div>' : '<span class="dim">-</span>';
  const soil = r.soil == null ? '<span class="dim">-</span>' : esc(r.soil) + '% <span class="dim">(' + esc(SOILTXT[r.soil_state] || '') + ')</span>';
  if (!full) return '<tr class="click" onclick="openDrawer(\'' + esc(r.id) + '\')"><td style="width:62px">' + th + '</td><td>' + diag + '</td><td>' + esc(r.plot) + '</td><td class="mono dim">' + esc(t_time(r)) + '</td></tr>';
  return '<tr class="click" onclick="openDrawer(\'' + esc(r.id) + '\')"><td style="width:68px">' + th + '</td><td><div>' + esc(t_time(r)) + '</div><div class="sub dim">' + esc(t_date(r)) + '</div></td>' +
    '<td><div class="nm">' + esc(r.plot) + '</div><div class="sub">' + esc(r.field) + ' ' + gpsChip(r) + '</div></td><td>' + soil + '</td><td>' + diag + '</td><td>' + conf + '</td>' +
    '<td style="text-align:right;white-space:nowrap"><button class="btn sm ghost" title="Speak record" onclick="event.stopPropagation();speakRec(\'' + esc(r.id) + '\')">' + icon('volume') + '</button> ' +
    '<button class="btn sm danger" title="Delete record" aria-label="Delete record" onclick="event.stopPropagation();deleteRec(\'' + esc(r.id) + '\')">Delete</button></td></tr>';
}
function renderRecent() {
  const list = S.records.slice(0, 6);
  $('cRecent').innerHTML = list.length ? '<table class="tbl"><tbody>' + list.map(r => rowHtml(r, false)).join('') + '</tbody></table>' : '<div class="empty">' + icon('list') + '<b>No activity yet</b>Captured photos and clips will be listed here.</div>';
}

/* ---------- records page ---------- */
const SEGS = [['all', 'All'], ['produce', 'Produce'], ['healthy', 'Healthy'], ['fungal', 'Fungal'], ['bacterial', 'Bacterial'], ['viral', 'Viral'], ['pest', 'Pest'], ['review', 'Needs review'], ['video', 'Clips']];
function renderRecords() {
  $('segCat').innerHTML = SEGS.map(s => '<button data-c="' + s[0] + '" class="' + (S.filter.cat === s[0] ? 'on' : '') + '">' + s[1] + '</button>').join('');
  const crops = [...new Set(S.records.map(r => r.crop).filter(Boolean))].sort();
  $('fCrop').innerHTML = '<option value="all">All crops</option>' + crops.map(c => '<option' + (S.filter.crop === c ? ' selected' : '') + '>' + esc(c) + '</option>').join('');
  const q = S.filter.q.toLowerCase();
  const list = S.records.filter(r => {
    if (S.filter.crop !== 'all' && r.crop !== S.filter.crop) return false;
    if (S.filter.cat === 'video' && r.kind !== 'video') return false;
    if (!['all', 'video'].includes(S.filter.cat) && recCat(r) !== S.filter.cat) return false;
    if (q && !((r.name || '') + ' ' + r.crop + ' ' + r.field + ' ' + r.plot).toLowerCase().includes(q)) return false;
    return true;
  });
  $('tblWrap').innerHTML = list.length ?
    '<table class="tbl"><thead><tr><th></th><th>Captured</th><th>Plant / place</th><th>Soil</th><th>Diagnosis</th><th>Confidence</th><th></th></tr></thead><tbody>' + list.map(r => rowHtml(r, true)).join('') + '</tbody></table>' :
    '<div class="empty">' + icon('search') + '<b>Nothing matches</b>Try a different filter, or capture more photos on the tablet.</div>';
}
$('segCat').addEventListener('click', e => { const b = e.target.closest('button'); if (b) { S.filter.cat = b.dataset.c; renderRecords(); } });
$('q').addEventListener('input', e => { S.filter.q = e.target.value; renderRecords(); });
$('fCrop').addEventListener('change', e => { S.filter.crop = e.target.value; renderRecords(); });
async function deleteRec(id) {
  const r = S.records.find(x => x.id === id);
  if (!r || !confirm('Permanently delete this saved record and its photo or clip?')) return;
  try {
    const j = await J('/api/records/' + encodeURIComponent(id), { method: 'DELETE' });
    if (!j.ok) throw new Error(j.error || 'Delete failed');
    await loadRecords();
    const s = await J('/api/status'); S.prevCount = s.records; $('navCount').textContent = s.records;
    toast('Record deleted', 'The selected record was removed.');
  } catch (e) { toast('Could not delete record', e.message || 'Please try again.'); }
}

/* ---------- drawer ---------- */
function openDrawer(id) {
  const r = S.records.find(x => x.id === id); if (!r) return;
  const res = r.result || {}, c = recCat(r);
  const media = r.kind === 'video' ? '<video class="big" controls src="/api/file/' + esc(r.id) + '"></video>' : '<img class="big" src="/api/file/' + esc(r.id) + '" alt="">';
  const top = (res.top || []).map(t => '<div><span>' + esc(prettyLabel(t.label)) + '</span><b class="mono">' + pct(t.score) + '%</b><div class="meter"><i style="width:' + pct(t.score) + '%;background:var(--brand)"></i></div></div>').join('');
  $('drawer').innerHTML = '<div class="dh"><h2>' + esc(r.kind === 'video' ? 'Video clip' : r.name || 'Photo') + '</h2><button class="btn sm ghost" onclick="closeDrawer()">' + icon('x') + '</button></div>' + media +
    '<div class="row" style="display:flex;gap:8px;margin-top:14px">' + catChip(c) + (res.confidence != null ? '<span class="chip">' + pct(res.confidence) + '% confidence</span>' : '') + '</div>' +
    '<div class="kv"><span>Plant</span><b>' + esc(r.plot) + '</b><span>Crop (by AI)</span><b>' + esc(r.crop) + '</b><span>Field</span><b>' + esc(r.field) + '</b><span>Captured</span><b>' + esc(t_date(r) + ' ' + t_time(r)) + '</b>' +
    '<span>Location</span><b>' + (r.lat != null ? esc(r.lat.toFixed(5) + ', ' + r.lon.toFixed(5)) + (r.acc ? ' (&plusmn;' + Math.round(r.acc) + ' m, ' + esc(r.gps_src || '') + ')' : '') + ' <a class="link" target="_blank" href="https://www.google.com/maps?q=' + r.lat + ',' + r.lon + '">Open in Maps</a>' : 'No GPS fix') + '</b>' +
    '<span>Soil moisture</span><b>' + (r.soil == null ? '-' : esc(r.soil) + '% (' + esc(SOILTXT[r.soil_state] || '') + ')') + '</b>' + (r.temp != null ? '<span>Air</span><b>' + esc(r.temp) + ' &deg;C, ' + esc(r.hum) + '% humidity</b>' : '') + '</div>' +
    (top ? '<h3 style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--text-3);margin-bottom:8px">Top predictions</h3><div class="rd-top" style="margin:0 0 16px">' + top + '</div>' : '') +
    '<div class="advbox">' + esc(r.text) + '</div>' +
    '<div style="display:flex;gap:10px;margin-top:16px"><button class="btn primary" onclick="speakRec(\'' + esc(r.id) + '\')">' + icon('volume') + ' Speak on tablet</button><a class="btn" href="/api/file/' + esc(r.id) + '" target="_blank">Open file</a></div>';
  $('drawer').classList.add('on'); $('backdrop').classList.add('on');
}
function closeDrawer() { $('drawer').classList.remove('on'); $('backdrop').classList.remove('on'); }
$('backdrop').addEventListener('click', closeDrawer);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

/* ---------- speak / language / export ---------- */
function speakRec(id) { post('/api/speak', { id, lang: lang() }); toast('Sent to tablet', 'The tablet will read the result aloud.'); }
$('btnSummary').onclick = () => { post('/api/speak', { summary: true, lang: lang() }); toast('Sent to tablet', 'Reading the summary aloud.'); };
$('btnCsv').onclick = () => { location.href = '/api/report.csv?lang=' + lang(); };
$('lang').onchange = async () => { await post('/api/lang', { lang: lang() }); await loadRecords(); };
function toast(t, s) {
  const d = document.createElement('div'); d.className = 'toast'; d.innerHTML = '<b>' + esc(t) + '</b><span>' + esc(s) + '</span>';
  $('toasts').appendChild(d); setTimeout(() => d.remove(), 4200);
}

/* ---------- polling ---------- */
async function loadRecords() { try { S.records = (await J('/api/records?lang=' + lang())).records; render(); } catch (e) {} }
async function pollStatus() {
  try {
    const s = await J('/api/status'); S.status = s; $('offline').classList.remove('on');
    if (!pollStatus.once) { $('lang').value = s.lang; pollStatus.once = true; }
    const live = s.frame_age != null && s.frame_age < 4, ard = /^Arduino/.test(s.rover);
    $('dModel').className = 'dot ' + (s.model === 'ready' ? 'ok' : 'bad'); $('tModel').textContent = s.model === 'ready' ? s.device.toUpperCase() : 'Off';
    $('dTab').className = 'dot ' + (live ? 'ok pulse' : 'warn'); $('tTab').textContent = live ? 'Live' : 'Idle';
    $('dRover').className = 'dot ' + (ard ? 'ok' : 'warn'); $('tRover').textContent = ard ? 'Arduino' : 'Simulation';
    $('navLive').classList.toggle('on', live); $('navCount').textContent = s.records;
    if (S.prevCount !== s.records) {
      const was = S.prevCount; S.prevCount = s.records; await loadRecords();
      if (was !== null && s.records > was) { const r = S.records[0]; toast('New scan received', r ? ((r.name || 'Video clip') + (r.result && r.result.confidence ? ' - ' + pct(r.result.confidence) + '%' : '')) : ''); }
    }
    if (S.page === 'overview') renderHealth();
  } catch (e) { $('offline').classList.add('on'); }
}

/* ---------- live monitor ---------- */
const feedImg = $('feedImg');
function nextFrame() { if (S.page !== 'live') { setTimeout(nextFrame, 400); return; } feedImg.src = '/api/latest.jpg?t=' + Date.now(); }
feedImg.onload = () => { $('hudRes').textContent = feedImg.naturalWidth + ' x ' + feedImg.naturalHeight; setTimeout(nextFrame, 120); };
feedImg.onerror = () => setTimeout(nextFrame, 800);
$('btnFull').onclick = () => { const f = $('feed'); document.fullscreenElement ? document.exitFullscreen() : f.requestFullscreen(); };

function setNoFeed(on, title, sub) {
  $('noFeed').classList.toggle('on', on);
  if (on) $('noFeed').innerHTML = '<div class="radar"><i></i></div><b>' + title + '</b><span>' + sub + '</span>';
}
function renderRail(l) {
  const p = l.pred;
  setDetectionOverlay($('bboxLayer'), p, 'meet');
  let a = '<h3>AI reading <span class="grow"></span><span class="chip">' + esc((l.device || '').toUpperCase()) + '</span></h3>';
  if (!p) a += '<div class="rd-sub">' + ((l.vision_model || l.model) !== 'ready' ? 'Vision models are not ready.' : 'Waiting for a camera frame.') + '</div>';
  else if (p.status === 'error') a += '<div class="rd-sub">Model error: ' + esc(p.error) + '</div>';
  else if (p.status === 'produce') {
    a += '<div class="rd-name">Analysis</div>' +
      '<div class="rd-sub" style="margin-top:6px">' + esc(produceAnalysisSummary(p)) + '</div>' +
      '<div style="margin-top:8px">' + catChip('produce') + '</div>' +
      '<div class="rd-sub" style="margin-top:6px">Top object confidence ' + pct(p.confidence) + '%</div>';
    const sampleScreen = p.tomato_sample_screen || {};
    const shortAnalysis = p.tomato_screen_available ? ({ healthy: 'Likely healthy', possible_disease: 'Possible issue' }[sampleScreen.status] || 'Tomato analysis') : (Object.keys(p.tomato_color_stages || {}).length ? 'Screen unclear' : 'Produce analysis');
    $('hudRead').innerHTML = '<div class="rd"><i class="dot" style="background:var(--c-produce)"></i><b>' + esc(shortAnalysis) + ' · ' + esc(p.name) + '</b><span class="mono dim">estimate</span></div>';
  }
  else if (p.status === 'produce_hint') {
    a += '<div class="rd-name">' + esc(p.name || 'Possible produce') + '</div><div style="margin-top:8px">' + catChip('produce') + '</div>' +
      '<div class="rd-sub" style="margin-top:8px">Image hint only. The box detector could not confirm it, so no box or count is shown.</div>';
    $('hudRead').innerHTML = '<div class="rd"><i class="dot" style="background:var(--c-produce)"></i><b>' + esc(p.name || 'Possible produce') + '</b><span class="mono dim">unconfirmed</span></div>';
  }
  else if (p.status === 'not_plant') {
    const label = p.scene_name || 'No supported plant or produce detected';
    const reason = p.scene ? 'Move the hand/person aside and centre a leaf, potato, tomato or bell pepper.' :
      (p.produce_error ? 'Produce counter unavailable: ' + p.produce_error : 'Centre a leaf, potato, tomato or bell pepper in good light.');
    a += '<div class="rd-name">' + esc(label) + '</div><div style="margin-top:8px">' + catChip('uncertain') + '</div>' +
      '<div class="rd-sub" style="margin-top:8px">' + reason + '</div>';
    $('hudRead').innerHTML = '<div class="rd"><i class="dot" style="background:var(--c-review)"></i><b>' + esc(label) + '</b></div>';
  } else {
    const ok = p.status === 'ok', col = ok ? colorOf(p.category) : 'var(--c-review)';
    a += '<div class="rd-name">' + (ok ? esc(p.name) : 'No clear diagnosis') + '</div>' +
      '<div style="display:flex;align-items:center;gap:10px;margin-top:8px">' + ring(p.confidence, 46, col, pct(p.confidence)) + (ok ? catChip(p.category) : catChip('uncertain')) + '</div>' +
      (ok ? '' : '<div class="rd-sub" style="margin-top:6px">Confidence is low. Move closer to one leaf.</div>') +
      '<div class="rd-top">' + p.top.map(t => '<div><span>' + esc(t.name) + '</span><b class="mono">' + pct(t.score) + '%</b><div class="meter"><i style="width:' + pct(t.score) + '%;background:' + col + '"></i></div></div>').join('') + '</div>' +
      (ok && p.advice ? '<div class="rd-adv">' + esc(p.advice) + '</div>' : '');
    $('hudRead').innerHTML = '<div class="rd"><i class="dot" style="background:' + col + '"></i><b>' + (ok ? esc(p.name) : 'Analysing...') + '</b><span class="mono dim">' + pct(p.confidence) + '%</span></div>';
  }
  if (!p) $('hudRead').innerHTML = '';
  $('rRead').innerHTML = a;
  const st = l.soil_state;
  $('rSoil').innerHTML = '<h3>' + icon('drop') + ' Soil moisture <span class="grow"></span>' + (st ? '<span class="chip ' + (st === 'ok' ? 'healthy' : st === 'dry' ? 'fungal' : 'review') + '">' + SOILTXT[st] + '</span>' : '') + '</h3>' +
    (l.soil == null ? '<div class="rd-sub">No sensor data. Connect the Arduino soil sensor.</div>' :
      '<div class="soilv">' + esc(l.soil) + '<small> %</small></div><div style="margin-top:6px">' + spark(l.soil_hist, 240, 38, 'var(--cyan)') + '</div>');
  const sim = !/^Arduino/.test(l.rover);
  $('rMode').textContent = sim ? 'Simulation' : 'Arduino'; $('rMode').className = 'chip ' + (sim ? '' : 'healthy');
}
let liveBusy = false;
async function pollLive() {
  if ((S.page !== 'live' && S.page !== 'rover') || liveBusy) return; liveBusy = true;
  try {
    const l = await J('/api/live?lang=' + lang()); S.live = l;
    if (l.frame_age == null) setNoFeed(true, 'Waiting for the tablet camera', 'On the tablet open the AgriSahayak page and tap <em>Start camera</em>.');
    else if (l.frame_age > 4) setNoFeed(true, 'Camera signal lost', 'Last frame was ' + ago(l.frame_age) + '. Check the tablet connection.');
    else setNoFeed(false);
    $('hudAge').textContent = l.frame_age == null ? 'no signal' : 'signal ' + (l.frame_age < 2 ? 'good' : ago(l.frame_age));
    renderRail(l); renderRemote(l); renderRover(l);
  } catch (e) {}
  liveBusy = false; if (S.page === 'live' || S.page === 'rover') setTimeout(pollLive, 700);
}

/* ---------- rover controls ---------- */
let holdTimer = null, cur = 'S';
function sendCmd(cmd) { fetch('/api/rover', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cmd, speed: +$('speed').value }) }).catch(() => {}); }
function sendStop() { release(true); sendCmd('S'); }
function hold(cmd, btn) { release(true); cur = cmd; sendCmd(cmd); if (btn) btn.classList.add('hold'); holdTimer = setInterval(() => sendCmd(cmd), 150); }
function release(quiet) {
  if (holdTimer) { clearInterval(holdTimer); holdTimer = null; }
  document.querySelectorAll('.pb.hold').forEach(b => b.classList.remove('hold'));
  if (!quiet && cur !== 'S') sendCmd('S'); cur = 'S';
}
const PAD = { bF: 'F', bB: 'B', bL: 'L', bR: 'R' };
Object.keys(PAD).forEach(id => {
  const b = $(id);
  b.addEventListener('pointerdown', e => { e.preventDefault(); hold(PAD[id], b); });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(ev => b.addEventListener(ev, () => release()));
});
$('bS').addEventListener('click', sendStop);
$('speed').addEventListener('input', e => { $('spv').textContent = e.target.value; });
const KEYS = { w: ['F', 'bF'], arrowup: ['F', 'bF'], s: ['B', 'bB'], arrowdown: ['B', 'bB'], a: ['L', 'bL'], arrowleft: ['L', 'bL'], d: ['R', 'bR'], arrowright: ['R', 'bR'] };
let keyHeld = null;
document.addEventListener('keydown', e => {
  if (S.page !== 'live' || /INPUT|SELECT|TEXTAREA/.test(e.target.tagName) && e.target.type !== 'range') return;
  const k = e.key.toLowerCase();
  if (k === ' ') { e.preventDefault(); keyHeld = null; sendStop(); return; }
  if (KEYS[k] && !e.repeat) { e.preventDefault(); keyHeld = k; hold(KEYS[k][0], $(KEYS[k][1])); }
});
document.addEventListener('keyup', e => { if (e.key.toLowerCase() === keyHeld) { keyHeld = null; release(); } });
window.addEventListener('blur', () => release());
window.addEventListener('beforeunload', () => { if (cur !== 'S') sendCmd('S'); });


/* ---------- scan locations (works offline: relative metres around the average point) ---------- */
function niceStep(m) { const p = Math.pow(10, Math.floor(Math.log10(m))), f = m / p; return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p; }
function renderMap() {
  const el = $('cMap'), pts = S.records.filter(r => r.kind === 'photo' && r.lat != null);
  if (!pts.length) { el.innerHTML = '<div class="empty">' + icon('pin') + '<b>No locations yet</b>Photos get a position when the tablet (or a phone running gps.html) has a GPS fix.</div>'; $('mapNote').textContent = ''; return; }
  const lat0 = pts.reduce((a, p) => a + p.lat, 0) / pts.length, lon0 = pts.reduce((a, p) => a + p.lon, 0) / pts.length;
  const xy = pts.map(p => ({ p, x: (p.lon - lon0) * 111320 * Math.cos(lat0 * Math.PI / 180), y: (p.lat - lat0) * 110540 }));
  const ext = Math.max(8, ...xy.map(o => Math.max(Math.abs(o.x), Math.abs(o.y)))) * 1.3, W = 900, H = 260, s = Math.min((W / 2 - 60) / ext, (H / 2 - 34) / ext), cx = W / 2, cy = H / 2;
  const step = niceStep(ext / 3);
  let g = '';
  const kx = Math.floor(cx / (step * s)), ky = Math.floor(cy / (step * s));
  for (let k = -kx; k <= kx; k++) g += '<line x1="' + (cx + k * step * s) + '" y1="0" x2="' + (cx + k * step * s) + '" y2="' + H + '" stroke="#16251f"/>';
  for (let k = -ky; k <= ky; k++) g += '<line x1="0" y1="' + (cy + k * step * s) + '" x2="' + W + '" y2="' + (cy + k * step * s) + '" stroke="#16251f"/>';
  const dots = xy.map(o => '<circle cx="' + (cx + o.x * s).toFixed(1) + '" cy="' + (cy - o.y * s).toFixed(1) + '" r="9" fill="' + colorOf(recCat(o.p)) + '" fill-opacity=".7" stroke="#fff" stroke-opacity=".55"><title>' + esc(o.p.plot + ' - ' + (o.p.name || 'no result') + (o.p.acc ? ' (GPS +-' + Math.round(o.p.acc) + ' m)' : '')) + '</title></circle>').join('');
  el.innerHTML = '<div class="mapwrap"><svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet" style="display:block;max-height:260px">' + g + dots +
    '<g transform="translate(24,' + (H - 26) + ')"><line x1="0" y1="0" x2="' + (step * s).toFixed(1) + '" y2="0" stroke="#a9c0b7" stroke-width="2"/><text x="0" y="-8" fill="#a9c0b7" font-size="12">' + step + ' m</text></g>' +
    '<g transform="translate(' + (W - 34) + ',34)"><path d="M0 -16 L7 6 L0 1 L-7 6 Z" fill="#a9c0b7"/><text x="0" y="22" text-anchor="middle" fill="#a9c0b7" font-size="11">N</text></g></svg></div>' +
    '<div class="maplegend">' + ['healthy', 'fungal', 'bacterial', 'viral', 'pest', 'review'].map(k => '<span><i style="background:' + colorOf(k) + '"></i>' + CATS[k].en + '</span>').join('') + '</div>';
  const last = pts[0];
  $('mapNote').innerHTML = pts.length + ' scan(s), position relative to their average. <a class="link" target="_blank" href="https://www.google.com/maps?q=' + last.lat + ',' + last.lon + '">Open latest in Maps</a>';
}

/* ---------- tablet remote ---------- */
const tchip = (t, ok) => '<span class="chip ' + (ok ? 'healthy' : '') + '">' + t + '</span>';
function renderRemote(l) {
  const t = l.tablet || {}, on = !!t.online;
  $('tabChip').textContent = on ? 'Online' : 'Offline'; $('tabChip').className = 'chip ' + (on ? 'healthy' : 'fungal');
  if (!on) { $('tabStatus').innerHTML = tchip('Waiting for the tablet page to open', false); if (document.activeElement !== $('tAuto')) $('tAuto').checked = false; return; }
  $('tabStatus').innerHTML = tchip('Camera ' + (t.camera ? 'on' : 'off'), t.camera) + tchip(t.serial === 'connected' ? 'Arduino linked' : 'Arduino not linked', t.serial === 'connected') +
    (l.gps ? tchip('GPS &plusmn;' + Math.round(l.gps.acc || 0) + ' m', true) : tchip('No GPS fix', false)) + (t.auto ? tchip('Auto ' + t.auto + ' s', true) : '') + tchip('Waiting ' + (t.pending || 0), !t.pending);
  if (document.activeElement !== $('tAuto')) $('tAuto').checked = !!t.auto;
  const fn = $('fieldName'); if (document.activeElement !== fn && l.field && fn.value !== l.field) fn.value = l.field;
}
async function tcmd(cmd, extra, title) {
  const j = await post('/api/tablet/cmd', Object.assign({ cmd }, extra || {}));
  toast(title, j.tablet_online ? 'Sent to the tablet.' : 'The tablet is offline. Commands older than 20 seconds are skipped.');
}
$('tCamOn').onclick = () => tcmd('camera_on', null, 'Starting the camera');
$('tCamOff').onclick = () => tcmd('camera_off', null, 'Stopping the camera');
$('tPhoto').onclick = () => tcmd('photo', null, 'Taking a photo');
$('tClip').onclick = () => tcmd('clip', null, 'Recording a 5 second clip');
$('tAuto').onchange = e => e.target.checked ? tcmd('auto_on', { interval: +$('tInt').value || 10 }, 'Auto-capture on') : tcmd('auto_off', null, 'Auto-capture off');
$('tInt').onchange = () => { if ($('tAuto').checked) tcmd('auto_on', { interval: +$('tInt').value || 10 }, 'Auto-capture updated'); };
$('fieldSave').onclick = async () => { const j = await post('/api/setup', { field: $('fieldName').value }); toast('Field name saved', j.field); };
$('gpsLaptop').onclick = () => {
  if (!navigator.geolocation) { toast('Laptop location', 'This browser cannot give a location.'); return; }
  navigator.geolocation.getCurrentPosition(async p => {
    await post('/api/gps', { src: 'laptop', lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy });
    toast('Laptop location saved', 'About ' + Math.round(p.coords.accuracy) + ' m. Used for scans until a better GPS (phone) arrives.');
  }, e => toast('Laptop location failed', e.code === 1 ? 'Allow location for this page (address bar icon) and turn on Windows Settings, Privacy, Location.' : 'No position available.'), { enableHighAccuracy: true, timeout: 15000 });
};
let nudging = false;
function nudge(cmd) { if (nudging) return; nudging = true; hold(cmd, null); setTimeout(() => { release(true); sendCmd('S'); nudging = false; }, 700); }
$('nF').onclick = () => nudge('F'); $('nB').onclick = () => nudge('B');

/* ---------- Rover tools page ---------- */
const dev = (cmd, value, msg) => post('/api/device', { cmd, value }).then(j => { $('rvMsg').textContent = (msg || cmd) + (j.arduino_linked ? '' : ' - the Arduino is not linked, nothing will happen.'); return j; });
function renderRover(l) {
  if (S.page !== 'rover') return;
  const s = l.sensors || {}, on = !!s.alive, put = (id, v) => { $(id).textContent = v; };
  $('rvBanner').classList.toggle('on', !on);
  put('vTemp', s.temp != null ? s.temp + ' \u00b0C' : '-'); put('vHum', s.hum != null ? s.hum + ' %' : '-'); put('vSoil', l.soil != null ? l.soil + ' %' : '-');
  put('vDist', s.dist != null && s.dist > 0 ? s.dist + ' cm' : (s.dist === -1 ? 'clear' : '-')); put('vEdge', s.edge == null ? '-' : s.edge ? 'EDGE!' : 'OK');
  put('vPump', s.pump == null ? '-' : s.pump ? 'ON' : 'off'); put('vServo', s.servo != null ? s.servo + '\u00b0' : '-');
  const tl = n => $(n).parentElement;
  tl('vEdge').className = 'tile' + (s.edge ? ' warn' : on ? ' good' : ''); tl('vDist').className = 'tile' + (s.dist > 0 && s.dist < 15 ? ' warn' : '');
  tl('vPump').className = 'tile' + (s.pump ? ' good' : '');
  if (document.activeElement !== $('swAuto')) $('swAuto').checked = !!s.auto;
  if (document.activeElement !== $('swSafe')) $('swSafe').checked = s.safety !== 0;
  if (s.scan) {
    const names = ['Left', 'Centre', 'Right'];
    $('scanViz').innerHTML = '<div class="scanbars">' + s.scan.map((v, i) => '<div class="scanrow"><span>' + names[i] + '</span><div class="meter"><i style="width:' + (v < 0 ? 100 : Math.min(100, v / 1.5)) + '%;background:' + (v >= 0 && v < 20 ? 'var(--red)' : 'var(--brand)') + '"></i></div><b class="mono">' + (v < 0 ? 'clear' : v + ' cm') + '</b></div>').join('') + '</div>';
  } else $('scanViz').innerHTML = '<div class="empty">' + icon('activity') + 'No scan yet. Press Scan now.</div>';
  if (s.err && s.err_t && Date.now() / 1000 - 0 > 0) { /* last Arduino error is shown in the message line by the buttons */ }
}
$('rvScan').onclick = () => dev('scan', null, 'Scanning');
$('pump3').onclick = () => dev('pump', 3, 'Pump 3 s'); $('pump5').onclick = () => dev('pump', 5, 'Pump 5 s'); $('pumpOff').onclick = () => dev('pump_off', null, 'Pump off');
$('servoC').onclick = () => { $('servoR').value = 90; $('svv').textContent = 90; dev('servo', 90, 'Servo centre'); };
$('servoR').oninput = e => { $('svv').textContent = e.target.value; };
$('servoR').onchange = e => dev('servo', +e.target.value, 'Servo ' + e.target.value);
$('swAuto').onchange = e => dev('auto_water', e.target.checked, 'Automatic watering ' + (e.target.checked ? 'on' : 'off'));
$('swSafe').onchange = e => { if (!e.target.checked && !confirm('Turn the safety stop OFF? The rover can then drive off a table edge. Only for bench tests.')) { e.target.checked = true; return; } dev('safety', e.target.checked, 'Safety ' + (e.target.checked ? 'on' : 'OFF')); };
$('calAir').onclick = () => dev('cal_air', null, 'Dry-air reading saved'); $('calWater').onclick = () => dev('cal_water', null, 'Water reading saved');
$('stopAll').onclick = () => { sendStop(); dev('stop_all', null, 'Everything stopped'); };

/* ---------- Fasal Saathi (voice and chat helper) ---------- */
const chatEl = $('chatBody');
function chatAdd(role, text) { const m = document.createElement('div'); m.className = 'msg ' + role; m.textContent = text; chatEl.appendChild(m); chatEl.scrollTop = 1e9; return m; }
const CHIPS = ['Latest scan', 'Any disease?', 'Soil moisture', 'Temperature', 'What should I do?', 'Summary', 'Take a photo'];
$('chatChips').innerHTML = CHIPS.map(c => '<span class="chip">' + esc(c) + '</span>').join('');
$('chatChips').addEventListener('click', e => { const c = e.target.closest('.chip'); if (c) askAI(c.textContent); });
let chatOpened = false, vstat = null, curCap = null, rec = null, voiceTimer = null;
async function refreshVoice() {
  try {
    vstat = await J('/api/voice/status'); const a = vstat.asr, t = vstat.tts, l = vstat.llm;
    const speaker = t.engine === 'parler' ? (t.natural_ready ? 'Hindi: Indic neural · English: Zira' : 'Hindi: loading neural voice · English: Zira') : (t.engine + (t.voice ? ' (' + t.voice + ')' : ''));
    const llmState = !l.enabled ? 'off' : (l.local_ready ? ((l.groq_configured || l.xai_configured) ? 'Offline Qwen + online model ready' : 'Offline Qwen ready · online fallback not configured') : ((l.groq_configured || l.xai_configured) ? 'Offline model unavailable · online model ready' : 'models not ready'));
    $('chatNote').textContent = 'Speech: ' + (a.state === 'ready' ? 'SraVaani on ' + a.device : a.state === 'loading' ? 'loading...' : 'not ready (' + a.state + '), Chrome online mic is used') +
      '  |  Voice: ' + speaker + '  |  LLM: ' + llmState;
  } catch (e) {}
}
function toggleChat(on, suppressGreeting = false) {
  $('chat').classList.toggle('on', on); $('fab').style.display = on ? 'none' : 'flex';
  if (on && !chatOpened) { chatOpened = true; if (!suppressGreeting) chatAdd('ai', 'Hello! I am Fasal Saathi. Ask me about your scans, diseases, soil, temperature or what to do. Type or press the mic.\nनमस्ते! मैं फसल साथी हूँ। आप टाइप करें या माइक दबाकर बोलें।'); }
  if (on) { $('chatIn').focus(); refreshVoice(); voiceTimer = setInterval(refreshVoice, 8000); }
  else { clearInterval(voiceTimer); try { speechSynthesis.cancel(); } catch (e) {} if (introAudio) { introAudio.pause(); introAudio = null; } stopListen(); }
}
$('fab').onclick = () => toggleChat(true); $('chatX').onclick = () => toggleChat(false);
const speakLang = l => (l === 'en' ? 'en-US' : 'hi-IN');
const CHAT_REPLY_LANG_KEY = 'agrisahayak.fasalSaathiReplyLanguage';
const savedReplyLang = localStorage.getItem(CHAT_REPLY_LANG_KEY);
if (savedReplyLang && ['hi', 'en', 'bho', 'mai'].includes(savedReplyLang)) $('chatReplyLang').value = savedReplyLang;
$('chatReplyLang').addEventListener('change', () => localStorage.setItem(CHAT_REPLY_LANG_KEY, $('chatReplyLang').value));
function preferredVoice(lang) {
  const vs = speechSynthesis.getVoices(), en = lang === 'en';
  const natural = en ? /zira|aria|jenny|sonia|libby|emma|natural|online/i : /kalpana|hemant|swara|natural|online/i;
  return vs.find(v => v.lang && v.lang.toLowerCase().startsWith(en ? 'en' : 'hi') && natural.test(v.name)) ||
    vs.find(v => v.lang && v.lang.toLowerCase().startsWith(en ? 'en-us' : 'hi-in')) ||
    vs.find(v => v.lang && v.lang.toLowerCase().startsWith(en ? 'en' : 'hi')) || null;
}
async function askAI(text) {
  text = (text || '').trim(); if (!text) return;
  chatAdd('me', text); $('chatIn').value = '';
  const thinking = chatAdd('sys', '...');
  try {
    const j = await post('/api/ask', { text, lang: $('chatReplyLang').value, audio: $('optVoice').checked, speak_on_tablet: $('optTab').checked });
    thinking.remove(); chatAdd('ai', j.reply); noteAction(j); noteLLM(j); playReply(j);
  } catch (e) { thinking.remove(); chatAdd('sys', 'Could not reach the server.'); }
}
function noteAction(j) { if (j.action) toast('Fasal Saathi', 'Done: ' + j.action.replace('_', ' ')); }
function noteLLM(j) {
  if (!j.llm_provider) return;
  const name = j.llm_provider === 'groq' ? 'Groq online fallback' : j.llm_provider === 'xai' ? 'xAI online fallback' : 'local Qwen';
  chatAdd('sys', 'Answered by ' + name + (j.llm_ms != null ? ' in ' + j.llm_ms + ' ms' : ''));
}
async function playReply(j) {
  if (!$('optVoice').checked) { afterSpeak(); return; }
  if (j.audio_url) { const a = new Audio(j.audio_url); a.onended = afterSpeak; a.onerror = () => speakLocal(j.reply, j.lang); a.play().catch(() => speakLocal(j.reply, j.lang)); }
  else if (j.audio_job_id) {
    const pending = chatAdd('sys', 'Preparing the natural voice...');
    const until = Date.now() + 3000; let audioUrl = null;
    while (Date.now() < until && $('optVoice').checked && $('chat').classList.contains('on')) {
      try {
        const state = await J('/api/tts/' + encodeURIComponent(j.audio_job_id));
        if (state.state === 'done') { audioUrl = state.audio_url; break; }
        if (state.state === 'missing') break;
      } catch (e) { break; }
      await new Promise(resolve => setTimeout(resolve, 400));
    }
    pending.remove();
    if (!$('optVoice').checked || !$('chat').classList.contains('on')) return;
    if (audioUrl) { const a = new Audio(audioUrl); a.onended = afterSpeak; a.onerror = () => speakLocal(j.reply, j.lang); a.play().catch(() => speakLocal(j.reply, j.lang)); }
    else speakLocal(j.reply, j.lang);
  } else speakLocal(j.reply, j.lang);
}
function speakLocal(text, lang) {
  if (!('speechSynthesis' in window)) { afterSpeak(); return; }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text); u.lang = speakLang(lang);
  const v = preferredVoice(lang);
  if (v) u.voice = v; else if (lang !== 'en') chatAdd('sys', 'No Hindi voice is installed on this laptop. Windows Settings, Time and language, Speech, Add voices.');
  u.onend = afterSpeak; u.onerror = afterSpeak; speechSynthesis.speak(u);
}

/* ---------- sidebar menu, settings, and spoken project introduction ---------- */
const PREF_LANG_KEY = 'agrisahayak.introductionLanguage';
let introAudio = null;
function closeBrandMenu() { $('brandMenu').hidden = true; $('moreTrigger').setAttribute('aria-expanded', 'false'); }
$('moreTrigger').onclick = e => { e.stopPropagation(); const open = $('brandMenu').hidden; $('brandMenu').hidden = !open; $('moreTrigger').setAttribute('aria-expanded', String(open)); };
document.addEventListener('click', e => { if (!e.target.closest('.brand-more')) closeBrandMenu(); });
$('settingsOpen').onclick = () => {
  closeBrandMenu();
  const savedIntroLang = localStorage.getItem(PREF_LANG_KEY);
  $('introLang').value = savedIntroLang && savedIntroLang !== 'auto' ? savedIntroLang : 'hi';
  $('prefsDialog').showModal();
};
$('prefsSave').onclick = () => {
  localStorage.setItem(PREF_LANG_KEY, $('introLang').value);
  toast('Settings saved', 'The project introduction will follow this language choice.');
};
$('chatIntro').onclick = speakIntroduction;
async function speakIntroduction() {
  closeBrandMenu();
  stopListen();
  if (introAudio) { introAudio.pause(); introAudio = null; }
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  toggleChat(true, true);
  const pending = chatAdd('sys', 'Preparing the spoken project introduction...');
  const preference = localStorage.getItem(PREF_LANG_KEY) || 'hi';
  const selected = preference === 'auto' ? 'hi' : preference;
  try {
    const j = await post('/api/introduction', { lang: selected });
    chatAdd('ai', j.text);
    let audioUrl = j.audio_url || null;
    if (!audioUrl && j.audio_job_id) {
      pending.textContent = 'Preparing the natural voice...';
      const until = Date.now() + 7000;
      while (Date.now() < until && $('chat').classList.contains('on')) {
        try {
          const state = await J('/api/tts/' + encodeURIComponent(j.audio_job_id));
          if (state.state === 'done') { audioUrl = state.audio_url; break; }
          if (state.state === 'missing') break;
        } catch (e) { break; }
        await new Promise(resolve => setTimeout(resolve, 400));
      }
    }
    pending.remove();
    if (audioUrl) {
      introAudio = new Audio(audioUrl);
      introAudio.onended = () => { introAudio = null; };
      introAudio.onerror = () => { introAudio = null; speakLocalIntro(j.text, j.lang); };
      introAudio.play().catch(() => { introAudio = null; speakLocalIntro(j.text, j.lang); });
    } else speakLocalIntro(j.text, j.lang);
  } catch (e) {
    pending.textContent = 'Could not prepare the introduction. Check that AgriSahayak is running and try again.';
  }
}
function speakLocalIntro(text, language) {
  if (!('speechSynthesis' in window)) { chatAdd('sys', 'This browser does not have text-to-speech enabled.'); return; }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text); u.lang = speakLang(language);
  const v = preferredVoice(language);
  if (v) u.voice = v;
  u.onerror = () => chatAdd('sys', 'The selected Windows speech voice could not speak this language.');
  speechSynthesis.speak(u);
}

function afterSpeak() { if ($('optCall').checked && $('chat').classList.contains('on')) startListen(); }
async function recordTurn() {
  $('micBtn').classList.add('on'); chatAdd('sys', 'Listening... speak now');
  let r;
  try { curCap = VoiceCap.start({}); r = await curCap.promise; } catch (e) { $('micBtn').classList.remove('on'); chatAdd('sys', 'Microphone error: ' + e.name + '. Allow the microphone for this page.'); $('optCall').checked = false; return; }
  curCap = null; $('micBtn').classList.remove('on');
  if (!r.heard) { chatAdd('sys', 'I did not hear anything. Press the mic and try again.'); return; }
  const thinking = chatAdd('sys', 'Understanding...');
  const fd = new FormData(); fd.append('audio', r.blob, 'q.wav'); fd.append('in_lang', 'auto'); fd.append('out_lang', $('chatReplyLang').value); if ($('optTab').checked) fd.append('to_tablet', '1');
  try {
    const j = await (await fetch('/api/voice', { method: 'POST', body: fd })).json(); thinking.remove();
    if (!j.ok) { chatAdd('sys', j.error || 'Could not understand.'); return; }
    chatAdd('me', j.text_in); chatAdd('ai', j.reply); noteAction(j); noteLLM(j);
    chatAdd('sys', 'heard in ' + (j.timings.asr_ms || 0) + ' ms, answered in ' + (j.timings.total_ms || 0) + ' ms');
    playReply(j);
  } catch (e) { thinking.remove(); chatAdd('sys', 'Could not reach the server.'); }
}
function startListen() {
  stopListen();
  if (vstat && vstat.asr.state === 'ready') { recordTurn(); return; }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { chatAdd('sys', 'Speech recognition is not ready on the laptop and this browser has no fallback. Please type.'); $('optCall').checked = false; return; }
  rec = new SR(); rec.lang = $('chatReplyLang').value === 'en' ? 'en-US' : 'hi-IN'; rec.interimResults = false; rec.maxAlternatives = 1;
  rec.onstart = () => $('micBtn').classList.add('on');
  rec.onresult = e => askAI(e.results[0][0].transcript);
  rec.onerror = e => { chatAdd('sys', 'Mic: ' + e.error + (e.error === 'network' ? ' (this fallback needs internet)' : e.error === 'not-allowed' ? ' (allow the microphone for this page)' : '')); $('optCall').checked = false; };
  rec.onend = () => $('micBtn').classList.remove('on');
  try { rec.start(); } catch (e) {}
}
function stopListen() { if (curCap) { curCap.stop(); return; } if (rec) { try { rec.abort(); } catch (e) {} rec = null; } $('micBtn').classList.remove('on'); }
$('micBtn').onclick = () => $('micBtn').classList.contains('on') ? stopListen() : startListen();
$('chatSend').onclick = () => askAI($('chatIn').value);
$('chatIn').addEventListener('keydown', e => { if (e.key === 'Enter') askAI($('chatIn').value); });

/* ---------- start ---------- */
setInterval(() => { const d = new Date(); $('clock').textContent = d.toLocaleDateString(undefined, { day: '2-digit', month: 'short' }) + '  ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }, 1000);
route(); pollStatus(); setInterval(pollStatus, 2000); nextFrame();
