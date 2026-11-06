/* AgriSahayak tablet app. The laptop dashboard controls it (camera, photo, auto-capture).
   Nothing is typed in here: the crop comes from the AI model, the position from GPS.
   Offline-first: photos are kept in IndexedDB and sent when the laptop is reachable. */
let db = null, stream = null, wake = null, server = null, syncing = false;
let autoTimer = null, autoSec = 0, captureBusy = false, port = null, linkMsg = '', after = 0, syncBusy = false;
let outLines = [], devAfter = 0, talkCap = null;
let gps = null, gpsErr = null, lastSoil = null, lastSoilT = 0, lastSoilSentT = 0, lastSpeed = null, lastDrive = 'S';
let nTotal = 0, nPend = 0;

// ---------- settings (only a few switches are saved) ----------
const saved = JSON.parse(localStorage.getItem('agri_cfg') || '{}');
if (saved.alt) $('alt').value = saved.alt;
$('alt').addEventListener('change', () => localStorage.setItem('agri_cfg', JSON.stringify({ alt: $('alt').value.trim() })));
['showlocal', 'preview', 'autosync', 'speakres'].forEach(id => {
  const v = localStorage.getItem('agri_' + id); if (v !== null) $(id).checked = v === '1';
  $(id).addEventListener('change', () => { localStorage.setItem('agri_' + id, $(id).checked ? '1' : '0'); applyView(); });
});
const fv = localStorage.getItem('agri_facing'); if (fv) $('facing').value = fv;
$('facing').addEventListener('change', () => { localStorage.setItem('agri_facing', $('facing').value); if (stream) startCam(); });
const savedTalkLang = localStorage.getItem('agri_talk_lang'); if (savedTalkLang) $('talkLang').value = savedTalkLang;
$('talkLang').addEventListener('change', () => localStorage.setItem('agri_talk_lang', $('talkLang').value));
function updateFullscreenButton() {
  const full = !!document.fullscreenElement;
  $('btnFullscreen').textContent = full ? '⛶ Exit full screen' : '⛶ Full screen';
  $('btnFullscreen').setAttribute('aria-label', full ? 'Exit full screen' : 'Enter full screen');
}
$('btnFullscreen').onclick = async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch (e) { tip('Full screen is not available in this browser. Try Chrome menu > Full screen.'); }
};
document.addEventListener('fullscreenchange', updateFullscreenButton);
if (!document.documentElement.requestFullscreen) $('btnFullscreen').disabled = true;
function applyView() { $('stage').classList.toggle('nopreview', !$('showlocal').checked); }
function log(t) { const d = document.createElement('div'); d.textContent = new Date().toLocaleTimeString() + '  ' + t; $('log').prepend(d); }
let tipTimer = null;
function tip(t) { $('tip').textContent = t; $('tip').classList.add('on'); clearTimeout(tipTimer); tipTimer = setTimeout(() => $('tip').classList.remove('on'), 2400); }

// ---------- local storage (IndexedDB) ----------
function openDB() {
  return new Promise((res, rej) => {
    const r = indexedDB.open('agri', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('records', { keyPath: 'id' });
    r.onsuccess = () => { db = r.result; res(); }; r.onerror = () => rej(r.error);
  });
}
const store = m => db.transaction('records', m).objectStore('records');
const dbPut = rec => new Promise((res, rej) => { const q = store('readwrite').put(rec); q.onsuccess = () => res(); q.onerror = () => rej(q.error); });
const dbAll = () => new Promise((res, rej) => { const q = store('readonly').getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); });
const dbDel = id => new Promise((res, rej) => { const q = store('readwrite').delete(id); q.onsuccess = () => res(); q.onerror = () => rej(q.error); });

// ---------- helpers ----------
function newId() { return (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2); }
function isoLocal(d) {
  const p = n => String(n).padStart(2, '0'), o = -d.getTimezoneOffset(), a = Math.abs(o);
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + 'T' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) + (o >= 0 ? '+' : '-') + p(Math.floor(a / 60)) + ':' + p(a % 60);
}
async function sha(blob) {
  try { if (!(window.crypto && crypto.subtle)) return ''; const h = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer()); return [...new Uint8Array(h)].map(x => x.toString(16).padStart(2, '0')).join(''); }
  catch (e) { return ''; }
}
function say(text, lang) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.lang = lang;
  const english = String(lang).toLowerCase().startsWith('en'), voices = speechSynthesis.getVoices();
  const preferred = english ? /zira|aria|jenny|sonia|natural|online/i : /kalpana|hemant|natural|online/i;
  const v = voices.find(x => x.lang && x.lang.toLowerCase().startsWith(english ? 'en' : 'hi') && preferred.test(x.name)) ||
    voices.find(x => x.lang && x.lang.toLowerCase().startsWith(english ? 'en-us' : 'hi-in')) ||
    voices.find(x => x.lang && x.lang.toLowerCase().startsWith(english ? 'en' : 'hi'));
  if (v) u.voice = v;
  speechSynthesis.speak(u);
}

// ---------- GPS (position of every photo; coordinates are never spoken or shown here) ----------
let gpsWatch = null;
function startGps() {
  if (!navigator.geolocation) { gpsErr = 'GPS not supported here'; renderGps(); return; }
  if (gpsWatch !== null) { try { navigator.geolocation.clearWatch(gpsWatch); } catch (e) {} }
  gpsWatch = navigator.geolocation.watchPosition(p => { gps = { lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy, t: Date.now() }; gpsErr = null; renderGps(); },
    e => { gpsErr = e.code === 1 ? 'Location permission is blocked' : e.code === 2 ? 'No position available (turn Location ON in the tablet quick settings)' : 'Position timed out'; renderGps(); },
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 });
}
async function permState() {
  try {
    const p = await navigator.permissions.query({ name: 'geolocation' }); permNow = p.state; p.onchange = permState; renderGps(); return p.state;
  } catch (e) { permNow = 'unknown'; renderGps(); }
}
let permNow = 'unknown';
$('btnGps').onclick = () => { startGps(); permState(); };
const gpsFresh = () => gps && Date.now() - gps.t < 60000;
function renderGps() {
  if (gpsFresh()) {
    const a = Math.round(gps.acc);
    $('gpsTxt').textContent = 'GPS fix, about ' + a + ' m';
    $('gpsSub').textContent = a <= 30 ? 'Good enough to mark where each photo was taken.' : 'Rough position only. A real GPS signal (outdoors) is better.';
    $('btnGps').style.display = 'none';
  } else {
    $('gpsTxt').textContent = gpsErr || 'Waiting for GPS...'; $('gpsSub').textContent = 'Photos are saved without a position until a fix arrives.'; $('btnGps').style.display = '';
  }
  $('gpsPerm').textContent = permNow === 'denied' ? 'Blocked for this address. Tap the (i) icon next to the address bar, then Permissions, then Location, then Allow.' :
    permNow === 'prompt' ? 'Tap Allow location, then choose Allow in the box that appears. If no box appears, look for a location icon in the address bar.' : permNow === 'granted' ? 'Permission is given. If there is still no fix: turn Location ON in the tablet quick settings.' : '';
}

// ---------- camera ----------
function setCamUI(on, txt) {
  $('startBox').classList.toggle('off', on); $('stage').classList.toggle('camoff', !on);
  $('recDot').className = 'dot ' + (on ? 'bad pulse' : ''); $('recTxt').textContent = txt || (on ? 'LIVE' : 'Camera off');
  $('btnPhoto').disabled = !on; $('btnClip').disabled = !on;
}
async function startCam() {
  stopCam(true);
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: $('facing').value }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    $('v').srcObject = stream; await $('v').play();
    try { wake = await navigator.wakeLock.request('screen'); } catch (e) {}
    setCamUI(true, 'LIVE  ' + $('v').videoWidth + 'x' + $('v').videoHeight); localStorage.setItem('agri_cam', '1');
    const a = parseInt(localStorage.getItem('agri_auto') || '0'); if (a && !autoTimer) startAuto(a, true);
  } catch (e) { setCamUI(false, 'Camera error'); tip('Camera error: ' + e.name); log('Camera error: ' + e.name + ' - ' + e.message); }
}
function stopCam(quiet) {
  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
  if (wake) { try { wake.release(); } catch (e) {} wake = null; }
  setCamUI(false); if (!quiet) localStorage.setItem('agri_cam', '0');
}
async function saveRecord(kind, blob) {
  const rec = { id: newId(), ts: isoLocal(new Date()), kind, blob, synced: false, sha256: await sha(blob) };
  if (gpsFresh()) { rec.lat = gps.lat; rec.lon = gps.lon; rec.acc = gps.acc; }
  await dbPut(rec); log('Saved on tablet: ' + kind + ' (' + Math.round(blob.size / 1024) + ' KB)');
  tip(kind === 'photo' ? 'Photo saved' : 'Clip saved'); updateStatus();
  if (server && $('autosync').checked) syncPending();
}
async function capture() {
  if (captureBusy) return;
  const v = $('v');
  if (!stream || !v.videoWidth) { tip('Start the camera first'); return; }
  captureBusy = true;
  try {
    $('flash').classList.remove('on'); void $('flash').offsetWidth; $('flash').classList.add('on');
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.92));
    if (blob) await saveRecord('photo', blob);
  } finally { captureBusy = false; }
}
async function recordClip() {
  if (!stream) { tip('Start the camera first'); return; }
  const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp8') ? 'video/webm;codecs=vp8' : 'video/webm';
  const chunks = [], mr = new MediaRecorder(stream, { mimeType: mime });
  mr.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
  mr.onstop = async () => { await saveRecord('video', new Blob(chunks, { type: 'video/webm' })); $('btnClip').disabled = false; };
  $('btnClip').disabled = true; mr.start(); setTimeout(() => mr.stop(), 5000);
}
function startAuto(sec, quiet) {
  stopAuto(true); autoSec = Math.max(15, Math.min(3600, sec | 0 || 120));
  $('autoSeconds').value = autoSec; localStorage.setItem('agri_auto_interval', autoSec); localStorage.setItem('agri_auto', autoSec);
  autoTimer = setInterval(() => { if (stream) capture(); }, autoSec * 1000); $('btnAuto').classList.add('on'); $('btnAuto').textContent = 'Auto ' + (autoSec >= 60 ? Math.round(autoSec / 60) + 'm' : autoSec + 's');
  if (!quiet) tip('Auto-capture every ' + autoSec + ' s');
}
function stopAuto(quiet) {
  if (autoTimer) { clearInterval(autoTimer); autoTimer = null; } autoSec = 0; localStorage.setItem('agri_auto', '0');
  $('btnAuto').classList.remove('on'); $('btnAuto').textContent = 'Auto'; if (!quiet) tip('Auto-capture stopped');
}
$('autoSeconds').value = Math.max(15, Math.min(3600, parseInt(localStorage.getItem('agri_auto_interval') || '120', 10) || 120));
$('autoSeconds').onchange = () => { const next = parseInt($('autoSeconds').value, 10) || 120; localStorage.setItem('agri_auto_interval', next); if (autoTimer) startAuto(next, true); };

// ---------- Arduino over USB-OTG ----------
function renderLink() {
  const ok = port && port.ready;
  $('linkTxt').textContent = ok ? 'Connected (' + port.kind + ')' : 'Not connected';
  $('linkSub').textContent = ok ? (lastSoil !== null && Date.now() - lastSoilT < 5000 ? 'Receiving sensor data.' : 'Waiting for sensor data...') : (linkMsg || 'Plug the Arduino into the tablet with the OTG cable.');
  $('btnUsb').style.display = ok ? 'none' : '';
}
function onLine(l) {
  outLines.push(l); if (outLines.length > 80) outLines.shift();           // every Arduino line goes to the laptop, which understands them
  const m = /^SOIL,(-?[\d.]+)/.exec(l); if (m) { lastSoil = parseFloat(m[1]); lastSoilT = Date.now(); }
}
async function connectSerial(dev) {
  try {
    port = await UsbSerial.open(dev, { baud: 9600, onLine, log: t => log('USB: ' + t), onClose: e => { linkMsg = 'Arduino disconnected'; log('USB closed: ' + e.message); renderLink(); } });
    linkMsg = ''; lastDrive = 'S'; lastSpeed = null; log('Arduino linked (' + port.kind + ')');
  } catch (e) { port = null; linkMsg = 'Could not open: ' + e.message; log('USB error: ' + e.name + ' - ' + e.message); }
  renderLink();
}
async function autoConnect() {
  if (!UsbSerial.supported()) { linkMsg = 'USB is not available on this page (see the Chrome flag note)'; renderLink(); return; }
  try { const k = await UsbSerial.known(); if (k.length && !(port && port.ready)) await connectSerial(k[0]); } catch (e) { log('USB check: ' + e.message); }
}
$('btnUsb').onclick = async () => { try { await connectSerial(await UsbSerial.request()); } catch (e) { linkMsg = e.message; renderLink(); } };
if (UsbSerial.supported()) {
  navigator.usb.addEventListener('connect', () => setTimeout(autoConnect, 600));
  navigator.usb.addEventListener('disconnect', () => { port = null; lastDrive = 'S'; linkMsg = 'Arduino unplugged'; renderLink(); });
}
async function driveRover(r) {
  if (!port || !port.ready || !r) return;
  try {
    if (r.cmd !== 'S') { if (r.speed !== lastSpeed) { await port.write('V' + r.speed + '\n'); lastSpeed = r.speed; } await port.write(r.cmd + '\n'); lastDrive = r.cmd; }
    else if (lastDrive !== 'S') { await port.write('S\n'); lastDrive = 'S'; }
  } catch (e) { log('Rover write failed: ' + e.message); }
}
function failSafeStop() { if (port && port.ready && lastDrive !== 'S') { lastDrive = 'S'; port.write('S\n').catch(() => {}); } }
window.addEventListener('blur', failSafeStop);
document.addEventListener('visibilitychange', () => { if (document.hidden) failSafeStop(); });
window.addEventListener('pagehide', failSafeStop);

// ---------- connection to the laptop (USB cable or Wi-Fi, whichever answers) ----------
function bases() { const a = [location.origin], alt = $('alt').value.trim().replace(/\/$/, ''); if (alt && !a.includes(alt)) a.push(alt); return a; }
async function ping(b) { try { const r = await fetch(b + '/api/ping', { signal: AbortSignal.timeout(1500), cache: 'no-store' }); return r.ok; } catch (e) { return false; } }
async function findServer() { for (const b of bases()) { if (await ping(b)) return b; } return null; }
async function updateStatus() {
  const all = db ? await dbAll() : [];
  nTotal = all.length; nPend = all.filter(r => !r.synced).length; $('total').textContent = nTotal; $('pend').textContent = nPend;
  const usb = server && /localhost|127\.0\.0\.1/.test(server);
  $('conn').textContent = server ? (usb ? 'Laptop: USB' : 'Laptop: Wi-Fi') : 'Offline - saving here';
  $('connDot').className = 'dot ' + (server ? 'ok' : 'warn'); renderLink();
}
let ticking = false;
async function tick() { if (ticking) return; ticking = true; server = await findServer(); await updateStatus(); if (server && $('autosync').checked) syncPending(); ticking = false; }

// ---------- laptop <-> tablet control loop (4 times a second) ----------
function stateObj() {
  return { camera: !!stream, auto: autoSec, serial: port && port.ready ? 'connected' : 'not connected', serial_kind: port ? port.kind : null,
    gps: gpsFresh() ? { acc: Math.round(gps.acc) } : null, gps_err: gpsFresh() ? null : gpsErr, pending: nPend, total: nTotal, facing: $('facing').value };
}
function runCmd(c) {
  if (c.cmd === 'camera_on') startCam(); else if (c.cmd === 'camera_off') { stopAuto(true); stopCam(); } else if (c.cmd === 'photo') capture();
  else if (c.cmd === 'clip') recordClip(); else if (c.cmd === 'auto_on') startAuto(c.interval); else if (c.cmd === 'auto_off') stopAuto();
}
async function syncLoop() {
  if (!server) { failSafeStop(); return; }
  if (syncBusy) return; syncBusy = true;
  try {
    const body = { state: stateObj(), after, dev_after: devAfter, lines: outLines.splice(0) };
    if (gpsFresh()) body.gps = { lat: gps.lat, lon: gps.lon, acc: gps.acc };
    const r = await fetch(server + '/api/tablet/sync', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.timeout(1500) });
    const j = await r.json();
    if (j.last < after) after = j.last;                         // the laptop server was restarted
    (j.cmds || []).forEach(c => { after = Math.max(after, c.n); if (j.now - c.t < 20) runCmd(c); });
    if (j.dev_last < devAfter) devAfter = j.dev_last;                // the laptop server was restarted
    for (const x of (j.dev || [])) { devAfter = Math.max(devAfter, x.n); if (j.now - x.t < 10 && port && port.ready) { try { await port.write(x.line + '\n'); } catch (e) { log('Device write failed: ' + e.message); } } }
    await driveRover(j.rover);
  } catch (e) { failSafeStop(); }
  syncBusy = false;
}

// ---------- send to laptop ----------
async function syncPending() {
  if (syncing || !server) return; syncing = true;
  let sent = 0, lastJ = null;
  try {
    const todo = (await dbAll()).filter(r => !r.synced).sort((a, b) => a.ts < b.ts ? -1 : 1);
    for (const r of todo) {
      const fd = new FormData();
      ['id', 'ts', 'kind'].forEach(k => fd.append(k, r[k] || ''));
      if (r.sha256) fd.append('sha256', r.sha256);
      if (r.lat !== undefined) { fd.append('lat', r.lat); fd.append('lon', r.lon); fd.append('acc', r.acc || ''); }
      fd.append('file', r.blob, r.kind === 'video' ? 'clip.webm' : 'photo.jpg');
      const j = await (await fetch(server + '/api/upload', { method: 'POST', body: fd })).json();
      if (j.ok) { r.synced = true; await dbPut(r); sent++; lastJ = j; showResult(j); } else { log('Laptop rejected a file: ' + j.error); break; }
    }
    if (sent === 1 && $('speakres').checked && lastJ && lastJ.view && lastJ.view.kind === 'photo') say(lastJ.view.text, /[\u0900-\u097F]/.test(lastJ.view.text) ? 'hi-IN' : 'en-US');
    if (sent) { log('Sent ' + sent + ' item(s) to the laptop'); tip('Sent to laptop'); }
  } catch (e) { log('Sending paused: ' + e.message); }
  syncing = false; updateStatus();
}
function showResult(j) {
  const v = j.view; if (!v) return;
  const res = v.result || {}, flag = res.reasons && res.reasons.length;
  if (res.status === 'not_plant') { $('result').innerHTML = '<b style="color:var(--text);font-size:12.5px">No plant detected</b><br>' + esc(v.text); return; }
  $('result').innerHTML = (v.name ? '<b style="color:var(--text);font-size:12.5px">' + esc(v.name) + '</b> ' + (res.confidence ? '<span class="mono">' + pct(res.confidence) + '%</span>' : '') + (flag ? ' ' + catChip('review') : '') + '<br>' : '') + esc(v.text);
}
async function clearSynced() { const all = await dbAll(); let n = 0; for (const r of all) if (r.synced) { await dbDel(r.id); n++; } log('Deleted ' + n + ' sent item(s)'); updateStatus(); }

// ---------- live preview to the laptop ----------
let previewBusy = false;
setInterval(async () => {
  const v = $('v');
  if (!$('preview').checked || !server || !stream || !v.videoWidth || previewBusy) return;
  previewBusy = true;
  try {
    const w = 480, h = Math.round(w * v.videoHeight / v.videoWidth), c = $('pc');
    c.width = w; c.height = h; c.getContext('2d').drawImage(v, 0, 0, w, h);
    const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.5));
    const fd = new FormData(); fd.append('file', blob, 'f.jpg');
    await fetch(server + '/api/frame', { method: 'POST', body: fd });
  } catch (e) {}
  previewBusy = false;
}, 400);

// ---------- live readings ----------
let liveBusy = false;
setInterval(async () => {
  if (!server || liveBusy) return; liveBusy = true;
  try { renderLive(await (await fetch(server + '/api/live', { cache: 'no-store' })).json()); } catch (e) {}
  liveBusy = false;
}, 700);
function renderLive(l) {
  const p = l.pred;
  setDetectionOverlay($('bboxLayer'), p, 'slice');
  let a = '<h4>AI reading</h4>';
  if (!stream) a += '<div class="rname dim">Camera is off</div>';
  else if ((l.vision_model || l.model) !== 'ready') a += '<div class="rname dim">Vision models are not ready on the laptop</div>';
  else if (!p) a += '<div class="rname dim">Waiting for the first frame...</div>';
  else if (p.status === 'error') a += '<div class="rsub">Model error: ' + esc(p.error) + '</div>';
  else if (p.status === 'produce') {
    a += '<div class="rname">Analysis</div>' +
      '<div class="radv">' + esc(produceAnalysisSummary(p)) + '</div>';
  }
  else if (p.status === 'produce_hint') a += '<div class="rname">' + esc(p.name || 'Possible produce') + '</div><div class="radv">Unconfirmed image hint: the box detector could not draw a box or estimate a count.</div>';
  else if (p.status === 'not_plant') a += '<div class="rname">' + esc(p.scene_name || 'No supported plant or produce detected') + '</div><div class="radv">' + (p.scene ? 'Move the hand/person aside and centre a leaf, potato, tomato or bell pepper.' : 'Centre a leaf, potato, tomato or bell pepper in good light.') + '</div>';
  else {
    const ok = p.status === 'ok', col = ok ? (CATS[p.category] || {}).color : 'var(--c-review)';
    a += '<div class="rname">' + (ok ? esc(p.name) : 'No clear diagnosis') + '</div>' +
      '<div class="rrow"><span class="pctv" style="color:' + col + '">' + pct(p.confidence) + '%</span><div class="meter"><i style="width:' + pct(p.confidence) + '%;background:' + col + '"></i></div>' + catChip(ok ? p.category : 'uncertain') + '</div>' +
      (ok && p.advice ? '<div class="radv">' + esc(p.advice) + '</div>' : '<div class="radv">Move closer to one leaf in good light.</div>');
  }
  $('pRead').innerHTML = a;
  const sv = l.sensors || {};
  $('sensLine').textContent = sv.alive ? [sv.temp != null ? sv.temp + '\u00b0C' : null, sv.hum != null ? sv.hum + '% air' : null, sv.dist > 0 ? 'front ' + sv.dist + ' cm' : null, sv.edge ? 'TABLE EDGE' : null, sv.pump ? 'pump ON' : null].filter(Boolean).join('  \u00b7  ') : '';
  const st = l.soil_state;
  $('pSoil').innerHTML = '<h4>' + icon('drop') + '<span>Soil moisture</span></h4>' + (l.soil == null ? '<div class="rname dim">No sensor data</div>' :
    '<div class="soilrow"><b>' + esc(l.soil) + '<small> %</small></b>' + (st ? '<span class="chip ' + (st === 'ok' ? 'healthy' : st === 'dry' ? 'fungal' : 'review') + '">' + SOILTXT[st] + '</span>' : '') + '</div><div style="margin-top:6px">' + spark(l.soil_hist, 240, 30, 'var(--cyan)') + '</div>');
}

function playAudio(url) { const a = new Audio((server || '') + url); a.play().catch(() => {}); }
async function speakAssistant(j, lang) {
  if (j.audio_url) { playAudio(j.audio_url); return; }
  if (j.audio_job_id && server) {
    const deadline = Date.now() + 3000; let url = null;
    while (Date.now() < deadline) {
      try { const state = await (await fetch(server + '/api/tts/' + encodeURIComponent(j.audio_job_id), { cache: 'no-store' })).json();
        if (state.state === 'done') { url = state.audio_url; break; }
        if (state.state === 'missing') break;
      } catch (_) { break; }
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    if (url) { playAudio(url); return; }
  }
  say(j.reply, lang);
}

const TABLET_INTRO_HI = 'AgriSahayak में आपका स्वागत है—खेत का स्मार्ट साथी। लाइव डैशबोर्ड रोवर सेंसर, पत्तियों की बीमारी-जाँच और समर्थित फलों-सब्ज़ियों के कैमरा बॉक्स व अनुमानित गिनती दिखाता है। फसल साथी खेती के सवालों के लिए ऑफलाइन और ऑनलाइन AI का उपयोग करता है। किसान सहायता डेस्क फसल, खेत और हाल की जाँच के अनुसार योजनाओं व विशेषज्ञ मदद के रास्ते सुझाता है। टैबलेट फोटो ऑफलाइन सहेजकर कनेक्शन आने पर भेजता है। गिनती अनुमान है; बीमारी-जाँच पत्तियों के लिए है।';
const introButton = $('btnIntro');
if (introButton) introButton.onclick = async () => {
  const status = $('introStatus'), copy = $('introText');
  introButton.disabled = true;
  copy.textContent = TABLET_INTRO_HI;
  if (!server) {
    status.textContent = 'हिंदी परिचय (ऑफलाइन)';
    say(TABLET_INTRO_HI, 'hi-IN');
    introButton.disabled = false;
    return;
  }
  status.textContent = 'हिंदी परिचय तैयार हो रहा है…';
  try {
    const j = await (await fetch(server + '/api/introduction', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lang: 'hi' }) })).json();
    if (!j.ok) throw new Error('Introduction is unavailable.');
    copy.textContent = j.text || TABLET_INTRO_HI;
    status.textContent = 'हिंदी में परिचय';
    await speakAssistant({ reply: copy.textContent, audio_url: j.audio_url, audio_job_id: j.audio_job_id }, 'hi-IN');
  } catch (e) {
    status.textContent = 'कनेक्शन उपलब्ध नहीं; ऑफलाइन परिचय सुनाया जा रहा है।';
    say(TABLET_INTRO_HI, 'hi-IN');
  } finally { introButton.disabled = false; }
};

// ---------- talk to Fasal Saathi (the tablet is the microphone and the speaker; the laptop does the thinking) ----------
function talkReset() { $('btnTalk').classList.remove('on'); $('btnTalk').querySelector('span').textContent = 'Talk'; }
$('btnTalk').onclick = async () => {
  if (talkCap) { talkCap.stop(); return; }
  if (!server) { tip('Not connected to the laptop'); return; }
  const lang = $('talkLang').value; $('btnTalk').classList.add('on'); $('btnTalk').querySelector('span').textContent = 'Tap to send'; $('talkHeard').textContent = 'Listening...'; $('talkReply').textContent = '';
  let r; try { talkCap = VoiceCap.start({}); r = await talkCap.promise; } catch (e) { talkCap = null; talkReset(); $('talkHeard').textContent = 'Microphone error: ' + e.name; return; }
  talkCap = null; talkReset();
  if (!r.heard) { $('talkHeard').textContent = 'I did not hear anything.'; return; }
  $('talkHeard').textContent = 'Thinking...';
  const fd = new FormData(); fd.append('audio', r.blob, 'q.wav'); fd.append('in_lang', lang); fd.append('out_lang', lang);
  try {
    const j = await (await fetch(server + '/api/voice', { method: 'POST', body: fd })).json();
    if (!j.ok) { $('talkHeard').textContent = j.error || 'Could not understand.'; return; }
    $('talkHeard').textContent = 'You: ' + j.text_in; $('talkReply').textContent = j.reply;
    speakAssistant(j, j.lang || (lang === 'en' ? 'en-US' : 'hi-IN'));
  } catch (e) { $('talkHeard').textContent = 'Could not reach the laptop.'; }
};

// ---------- voice messages from the laptop ----------
let lastN = null;
setInterval(async () => {
  if (!server) return;
  try {
    const j = await (await fetch(server + '/api/speak?after=' + (lastN === null ? 1e9 : lastN), { cache: 'no-store' })).json();
    if (lastN === null || j.last < lastN) { lastN = j.last; return; }
    lastN = j.last; j.items.forEach(i => i.audio ? playAudio(i.audio) : say(i.text, i.lang));
  } catch (e) {}
}, 2000);

// ---------- buttons and start-up ----------
$('btnStart').onclick = startCam; $('btnStop').onclick = () => { stopAuto(true); stopCam(); };
$('btnPhoto').onclick = capture; $('btnClip').onclick = recordClip; $('btnAuto').onclick = () => autoTimer ? stopAuto() : startAuto(+$('autoSeconds').value || 120);
$('btnSend').onclick = syncPending; $('btnClear').onclick = clearSynced;
applyView(); setCamUI(false); renderGps(); renderLink(); startGps(); permState();
openDB().then(async () => {
  await updateStatus(); await tick(); setInterval(tick, 4000); setInterval(syncLoop, 250);
  startCam();                       // starts by itself; the laptop can also start/stop it
  autoConnect();
});
