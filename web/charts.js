// SVG 차트: 선(시계열), 점(시점별 값), 막대(값별 면적). 지침: 가는 선 2px, 엷은 격자,
// 범례는 계열이 둘 이상일 때, 툴팁·십자선, 문자는 문자 색(계열 색을 쓰지 않는다).

const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, parent) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
};
const fmt = (v, d = 1) => (v == null ? '—' : v.toFixed(d));

function niceMax(v) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}

function ticks(lo, hi, n = 5) {
  const step = niceMax((hi - lo) / n);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}

function legend(host, series) {
  if (series.length < 2) return;
  const box = document.createElement('div');
  box.className = 'legend';
  for (const s of series) {
    const item = document.createElement('span');
    item.className = 'legend-item';
    item.innerHTML = `<i class="swatch ${s.dash ? 'dash' : ''} ${s.dot ? 'dot' : ''}" style="--c:${s.color}"></i>${s.label}`;
    box.appendChild(item);
  }
  host.appendChild(box);
}

function tooltip(host) {
  let tip = host.querySelector('.tip');
  if (!tip) { tip = document.createElement('div'); tip.className = 'tip'; tip.hidden = true; host.appendChild(tip); }
  return tip;
}

function placeTip(tip, host, x, y) {
  tip.hidden = false;
  const w = tip.offsetWidth, hw = host.clientWidth;
  tip.style.left = Math.min(Math.max(4, x + 12), hw - w - 4) + 'px';
  tip.style.top = Math.max(4, y - tip.offsetHeight - 8) + 'px';
}

// 시점 축: 왼쪽이 오래된 시대(540 Ma), 오른쪽이 현재.
export function timeChart(host, { series, unit, height = 260, onPick, yMin = 0, yMax = null, kind = 'line', note = '' }) {
  host.innerHTML = '';
  host.classList.add('chart');
  legend(host, series);
  const W = 760, H = height, m = { l: 48, r: kind === 'line' ? 96 : 16, t: 28, b: 34 };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': series.map(s => s.label).join(', ') }, host);
  const all = series.flatMap(s => s.values.filter(p => p[1] != null).map(p => p[1]));
  const lo = yMin ?? Math.min(...all), hi = yMax ?? niceMax(Math.max(...all));
  const x = a => m.l + (540 - a) / 540 * (W - m.l - m.r);
  const y = v => m.t + (hi - v) / (hi - lo) * (H - m.t - m.b);
  const grid = el('g', { class: 'grid' }, svg);
  for (const t of ticks(lo, hi)) {
    el('line', { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), class: t === 0 ? 'baseline' : 'gridline' }, grid);
    el('text', { x: m.l - 6, y: y(t) + 4, class: 'tick', 'text-anchor': 'end' }, grid).textContent = t;
  }
  for (let a = 0; a <= 540; a += 60) {
    el('text', { x: x(a), y: H - m.b + 18, class: 'tick', 'text-anchor': 'middle' }, grid).textContent = a;
  }
  el('text', { x: W - m.r, y: H - 4, class: 'axis-label', 'text-anchor': 'end' }, svg).textContent = '백만 년 전 (Ma)';
  el('text', { x: 4, y: 4, class: 'axis-label', 'dominant-baseline': 'hanging' }, svg).textContent = unit;
  const marker = el('line', { y1: m.t, y2: H - m.b, class: 'age-marker' }, svg);
  const labels = [];
  for (const s of series) {
    const pts = s.values.filter(p => p[1] != null);
    if (kind === 'dots' || s.dot) {
      for (const [a, v] of pts) el('circle', { cx: x(a), cy: y(v), r: 4, style: `fill:${s.color}`, class: 'dot' }, svg);
      continue;
    }
    let d = '', pen = false;
    for (const [a, v] of s.values) {
      if (v == null) { if (!s.connect) pen = false; continue; }
      d += (pen ? 'L' : 'M') + x(a).toFixed(1) + ' ' + y(v).toFixed(1);
      pen = true;
    }
    el('path', { d, fill: 'none', style: `stroke:${s.color}`, 'stroke-width': 2, 'stroke-dasharray': s.dash ? '5 4' : 'none',
      'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
    const last = pts.reduce((b, p) => (b == null || p[0] < b[0] ? p : b), null);  // 가장 젊은 시점(오른쪽 끝)
    if (last && series.length <= 4 && kind === 'line') labels.push({ x: x(last[0]) + 6, y: y(last[1]) + 4, text: s.short || s.label });
  }
  // 오른쪽 끝 이름이 겹치지 않게 위아래로 밀어낸다(최소 간격 14).
  labels.sort((p, q) => p.y - q.y);
  for (let i = 1; i < labels.length; i++) labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 14);
  const overflow = labels.length ? labels[labels.length - 1].y - (H - m.b + 4) : 0;
  if (overflow > 0) labels.forEach(l => { l.y -= overflow; });
  for (const l of labels) el('text', { x: l.x, y: l.y, class: 'direct-label' }, svg).textContent = l.text;
  const cross = el('line', { y1: m.t, y2: H - m.b, class: 'crosshair', visibility: 'hidden' }, svg);
  const hit = el('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: 'transparent' }, svg);
  const ages = [...new Set(series.flatMap(s => s.values.map(p => p[0])))].sort((a, b) => a - b);
  const tip = tooltip(host);
  const nearest = evt => {
    const r = svg.getBoundingClientRect();
    const px = (evt.clientX - r.left) / r.width * W;
    const age = 540 - (px - m.l) / (W - m.l - m.r) * 540;
    return ages.reduce((b, a) => (Math.abs(a - age) < Math.abs(b - age) ? a : b), ages[0]);
  };
  hit.addEventListener('pointermove', evt => {
    const a = nearest(evt);
    cross.setAttribute('x1', x(a)); cross.setAttribute('x2', x(a)); cross.setAttribute('visibility', 'visible');
    const rows = series.map(s => {
      const vals = s.values.filter(p => p[0] === a && p[1] != null).map(p => fmt(p[1], s.digits ?? 1));
      return `<div><i class="swatch ${s.dash ? 'dash' : ''}" style="--c:${s.color}"></i>${s.label}: <b>${vals.length ? vals.join(', ') : '—'}</b></div>`;
    }).join('');
    tip.innerHTML = `<div class="tip-head">${a} Ma</div>${rows}${onPick ? '<div class="tip-foot">눌러서 이 시점으로</div>' : ''}`;
    const r = svg.getBoundingClientRect(), hr = host.getBoundingClientRect();
    placeTip(tip, host, evt.clientX - hr.left, evt.clientY - hr.top);
  });
  hit.addEventListener('pointerleave', () => { cross.setAttribute('visibility', 'hidden'); tip.hidden = true; });
  if (onPick) hit.addEventListener('click', evt => onPick(nearest(evt)));
  if (note) { const p = document.createElement('p'); p.className = 'chart-note'; p.textContent = note; host.appendChild(p); }
  return { setAge(a) { marker.setAttribute('x1', x(a)); marker.setAttribute('x2', x(a)); } };
}

// 값별 면적 막대: 선택한 시점의 막대, 현재(0 Ma) 값은 가로 눈금으로 겹친다.
export function valueBars(host, { values, data, reference, highlight, color, highlightColor, unit }) {
  host.innerHTML = '';
  host.classList.add('chart');
  const W = 760, H = 260, m = { l: 48, r: 16, t: 28, b: 40 };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': '값별 면적' }, host);
  const hi = niceMax(Math.max(...values.map(v => Math.max(data[v] || 0, reference[v] || 0))));
  const bw = (W - m.l - m.r) / values.length;
  const y = v => m.t + (hi - v) / hi * (H - m.t - m.b);
  for (const t of ticks(0, hi)) {
    el('line', { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), class: t === 0 ? 'baseline' : 'gridline' }, svg);
    el('text', { x: m.l - 6, y: y(t) + 4, class: 'tick', 'text-anchor': 'end' }, svg).textContent = t;
  }
  el('text', { x: 4, y: 4, class: 'axis-label', 'dominant-baseline': 'hanging' }, svg).textContent = unit;
  el('text', { x: W - m.r, y: H - 4, class: 'axis-label', 'text-anchor': 'end' }, svg).textContent = '격자 값 (m, 40 m 간격)';
  const tip = tooltip(host);
  values.forEach((v, i) => {
    const a = data[v] || 0, r = reference[v] || 0;
    const x0 = m.l + i * bw + 1, w = bw - 2;
    const top = y(a), h = Math.max(0, y(0) - top);
    const g = el('g', {}, svg);
    el('path', { d: `M${x0} ${y(0)}V${top + Math.min(4, h)}q0 -4 4 -4h${w - 8}q4 0 4 4V${y(0)}Z`,
      style: `fill:${v === highlight ? highlightColor : color}` }, g);
    el('line', { x1: x0, x2: x0 + w, y1: y(r), y2: y(r), class: 'ref-tick' }, g);
    if (i % 2 === 0 || v === 0) el('text', { x: x0 + w / 2, y: H - m.b + 16, class: 'tick', 'text-anchor': 'middle' }, svg).textContent = v;
    const hitbox = el('rect', { x: x0, y: m.t, width: w, height: H - m.t - m.b, fill: 'transparent' }, g);
    hitbox.addEventListener('pointermove', evt => {
      tip.innerHTML = `<div class="tip-head">값 ${v} m${v === highlight ? ' · 단일값' : ''}</div><div>선택한 시점: <b>${fmt(a, 2)}</b></div><div>현재(0 Ma): <b>${fmt(r, 2)}</b></div>`;
      const hr = host.getBoundingClientRect();
      placeTip(tip, host, evt.clientX - hr.left, evt.clientY - hr.top);
    });
    hitbox.addEventListener('pointerleave', () => { tip.hidden = true; });
  });
}

// 범주별 묶음 막대: 범주(지역)마다 계열 수만큼 막대를 나란히 둔다. 값이 음수일 수 있다.
export function categoryBars(host, { categories, series, unit, yMin = null, yMax = null, note = '' }) {
  host.innerHTML = '';
  host.classList.add('chart');
  legend(host, series);
  const W = 760, H = 280, m = { l: 48, r: 16, t: 28, b: 44 };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': series.map(s => s.label).join(', ') }, host);
  const all = series.flatMap(s => s.values);
  const lo = yMin ?? Math.min(0, ...all), hi = yMax ?? niceMax(Math.max(...all));
  const y = v => m.t + (hi - v) / (hi - lo) * (H - m.t - m.b);
  for (const t of ticks(lo, hi)) {
    el('line', { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), class: t === 0 ? 'baseline' : 'gridline' }, svg);
    el('text', { x: m.l - 6, y: y(t) + 4, class: 'tick', 'text-anchor': 'end' }, svg).textContent = t;
  }
  el('text', { x: 4, y: 4, class: 'axis-label', 'dominant-baseline': 'hanging' }, svg).textContent = unit;
  const gw = (W - m.l - m.r) / categories.length;
  const bw = Math.min(28, (gw - 12) / series.length);
  const tip = tooltip(host);
  categories.forEach((c, i) => {
    const x0 = m.l + i * gw + (gw - bw * series.length - 2 * (series.length - 1)) / 2;
    series.forEach((s, k) => {
      const v = s.values[i];
      const top = y(Math.max(0, v)), bottom = y(Math.min(0, v));
      el('rect', { x: x0 + k * (bw + 2), y: top, width: bw, height: Math.max(1, bottom - top), rx: 3, style: `fill:${s.color}` }, svg);
    });
    el('text', { x: m.l + i * gw + gw / 2, y: H - m.b + 18, class: 'tick', 'text-anchor': 'middle' }, svg).textContent = c;
    const hit = el('rect', { x: m.l + i * gw, y: m.t, width: gw, height: H - m.t - m.b, fill: 'transparent' }, svg);
    hit.addEventListener('pointermove', evt => {
      tip.innerHTML = `<div class="tip-head">${c}</div>` + series.map(s => `<div><i class="swatch" style="--c:${s.color}"></i>${s.label}: <b>${fmt(s.values[i], 1)}</b></div>`).join('');
      const hr = host.getBoundingClientRect();
      placeTip(tip, host, evt.clientX - hr.left, evt.clientY - hr.top);
    });
    hit.addEventListener('pointerleave', () => { tip.hidden = true; });
  });
  if (note) { const p = document.createElement('p'); p.className = 'chart-note'; p.textContent = note; host.appendChild(p); }
}
