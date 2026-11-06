/* Shared helpers for AgriSahayak pages (no libraries). */
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const ICONS = {
  leaf: '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
  grid: '<rect width="7" height="9" x="3" y="3" rx="1.5"/><rect width="7" height="5" x="14" y="3" rx="1.5"/><rect width="7" height="9" x="14" y="12" rx="1.5"/><rect width="7" height="5" x="3" y="16" rx="1.5"/>',
  video: '<path d="m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.75-.43L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2.5"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  drop: '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
  wifi: '<path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><path d="M12 20h.01"/>',
  usb: '<circle cx="10" cy="7" r="1"/><circle cx="4" cy="20" r="1"/><path d="M4.7 19.3 19 5"/><path d="m21 3-3 1 2 2Z"/><path d="M9.26 7.68 5 12l2 5"/><path d="m10 14 5 2 3.5-3.5"/><path d="m18 12 1-1 1 1-1 1Z"/>',
  cpu: '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/>',
  check: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  volume: '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
  expand: '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  up: '<path d="m18 15-6-6-6 6"/>', down: '<path d="m6 9 6 6 6-6"/>', left: '<path d="m15 18-6-6 6-6"/>', right: '<path d="m9 18 6-6-6-6"/>',
  stop: '<rect x="5" y="5" width="14" height="14" rx="2"/>',
  camera: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3.5"/>',
  clip: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3" fill="currentColor"/>',
  repeat: '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14M7 22l-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  mic: '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"/>',
  send: '<path d="m22 2-7 20-4-9-9-4 20-7Z"/><path d="M22 2 11 13"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
};
const icon = n => '<svg class="i" viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[n] || '') + '</svg>';
document.querySelectorAll('[data-i]').forEach(el => el.insertAdjacentHTML('afterbegin', icon(el.dataset.i)));

const CATS = {
  healthy: { en: 'Healthy', color: 'var(--c-healthy)' }, fungal: { en: 'Fungal', color: 'var(--c-fungal)' },
  bacterial: { en: 'Bacterial', color: 'var(--c-bacterial)' }, viral: { en: 'Viral', color: 'var(--c-viral)' },
  pest: { en: 'Pest', color: 'var(--c-pest)' }, review: { en: 'Needs review', color: 'var(--c-review)' },
  produce: { en: 'Produce count', color: 'var(--c-produce)' },
};
const catChip = c => c ? '<span class="chip ' + esc(c) + '">' + esc((CATS[c] || { en: c }).en) + '</span>' : '';
const SOILTXT = { dry: 'Dry', ok: 'Optimal', wet: 'Too wet' };
const pct = v => Math.round((v || 0) * 100);

function produceAnalysisSummary(p) {
  const counts = p && p.produce_counts || {};
  const tomatoCount = Object.entries(counts).reduce((n, entry) =>
    n + (String(entry[0]).toLowerCase() === 'tomato' ? Number(entry[1] || 0) : 0), 0);
  const screen = p && p.tomato_sample_screen || {};
  const stages = p && p.tomato_color_stages || {};
  const parts = [];
  if (tomatoCount && p.tomato_screen_available) {
    const screenLabel = screen.status === 'healthy' ? 'likely healthy-looking' : 'possible issue';
    parts.push('Tomato photo screen: ' + screenLabel + ' (' + Math.round(Number(screen.confidence || 0) * 100) +
      '% confidence). Prototype image-level screening only; confirm visually, it does not name a disease or score each fruit separately.');
  } else if (tomatoCount) {
    parts.push(screen.status === 'uncertain' ? 'Tomato photo screen is unclear; no health result was produced.' :
      'Tomato health screen unavailable; no health result was produced.');
  } else {
    parts.push('No health screen is available for these produce types; only object detection and estimated count are shown.');
  }
  const stageNames = { mostly_green: 'mostly green', turning: 'turning color', mostly_red: 'mostly red', uncertain: 'color unclear' };
  const stageList = Object.entries(stages).map(([key, value]) => (stageNames[key] || key) + ' × ' + Number(value || 0)).join(', ');
  if (stageList) parts.push('Tomato surface-color estimate: ' + stageList + '; color alone cannot confirm maturity.');
  const detected = Object.entries(counts).map(([name, count]) => name + ' × ' + Number(count || 0)).join(', ');
  parts.push('Detected produce: ' + (detected || 'none') + '. Boxes and counts are estimates.');
  return parts.join(' ');
}

function setDetectionOverlay(svg, prediction, fit = 'meet') {
  if (!svg) return;
  const detections = prediction && prediction.status === 'produce' && Array.isArray(prediction.detections)
    ? prediction.detections : [];
  const width = Number(prediction && prediction.frame_width), height = Number(prediction && prediction.frame_height);
  if (!detections.length || !Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    svg.innerHTML = ''; svg.removeAttribute('viewBox'); return;
  }
  svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
  svg.setAttribute('preserveAspectRatio', fit === 'slice' ? 'xMidYMid slice' : 'xMidYMid meet');
  svg.innerHTML = detections.map(d => {
    const b = Array.isArray(d.box) ? d.box.map(Number) : [];
    if (b.length !== 4 || !b.every(Number.isFinite)) return '';
    const x1 = Math.max(0, Math.min(width, b[0])), y1 = Math.max(0, Math.min(height, b[1]));
    const x2 = Math.max(0, Math.min(width, b[2])), y2 = Math.max(0, Math.min(height, b[3]));
    if (x2 <= x1 || y2 <= y1) return '';
    const confidence = Math.round(Math.max(0, Math.min(1, Number(d.score) || 0)) * 100);
    const stage = d.label && String(d.label).toLowerCase() === 'tomato' && d.color_stage_label
      ? String(d.color_stage_label) + ' · ' : '';
    const caption = stage + String(d.label || 'Produce') + ' · ' + confidence + '%';
    const tagWidth = Math.min(width - 2, Math.max(72, caption.length * 7 + 14));
    const tagX = Math.max(1, Math.min(x1, width - tagWidth - 1)), tagY = Math.max(1, y1 - 21);
    return '<g class="detect-box"><rect class="detect-box-outline" x="' + x1 + '" y="' + y1 + '" width="' + (x2 - x1) + '" height="' + (y2 - y1) + '" rx="5"/><rect class="detect-box-tag" x="' + tagX + '" y="' + tagY + '" width="' + tagWidth + '" height="20" rx="5"/><text class="detect-box-label" x="' + (tagX + 7) + '" y="' + (tagY + 14) + '">' + esc(caption) + '</text></g>';
  }).join('');
}

function spark(values, w, h, color) {
  if (!values || values.length < 2) return '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="' + h + '"></svg>';
  const mn = Math.min(...values), mx = Math.max(...values), span = (mx - mn) || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, h - 3 - ((v - mn) / span) * (h - 6)]);
  const line = pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const id = 'g' + Math.random().toString(36).slice(2, 7);
  return '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="' + h + '" preserveAspectRatio="none">' +
    '<defs><linearGradient id="' + id + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + color + '" stop-opacity=".35"/><stop offset="1" stop-color="' + color + '" stop-opacity="0"/></linearGradient></defs>' +
    '<polygon points="0,' + h + ' ' + line + ' ' + w + ',' + h + '" fill="url(#' + id + ')"/>' +
    '<polyline points="' + line + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>';
}
function ring(value, size, color, label) {  // value 0..1
  const r = size / 2 - 6, c = 2 * Math.PI * r, d = Math.max(0, Math.min(1, value)) * c;
  return '<svg viewBox="0 0 ' + size + ' ' + size + '" width="' + size + '" height="' + size + '">' +
    '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="var(--surface-3)" stroke-width="6"/>' +
    '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="' + color + '" stroke-width="6" stroke-linecap="round" stroke-dasharray="' + d.toFixed(1) + ' ' + c.toFixed(1) + '" transform="rotate(-90 ' + size / 2 + ' ' + size / 2 + ')"/>' +
    '<text x="50%" y="52%" text-anchor="middle" dominant-baseline="middle" fill="var(--text)" font-size="' + size * 0.27 + '" font-weight="700">' + esc(label) + '</text></svg>';
}
function ago(sec) { if (sec == null) return '-'; if (sec < 2) return 'just now'; if (sec < 60) return Math.round(sec) + ' s ago'; return Math.round(sec / 60) + ' min ago'; }
function fmtUptime(s) { const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); return h ? h + 'h ' + m + 'm' : m + ' min'; }
