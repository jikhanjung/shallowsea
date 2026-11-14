import { MollweideMap } from './mollweide.js';
import { categoryBars, timeChart, valueBars } from './charts.js';

const $ = id => document.getElementById(id);
const VERSION = 'v0.1.0';
const CELLS = 181 * 360;

// ---- 색: CSS 변수를 읽어 Uint32(RGBA, 리틀 엔디언)로 ----
const cssVar = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const hex = h => { const v = parseInt(h.replace('#', ''), 16); return [(v >> 16) & 255, (v >> 8) & 255, v & 255]; };
const pack = ([r, g, b]) => ((255 << 24) | (b << 16) | (g << 8) | r) >>> 0;
const mix = (a, b, t) => a.map((x, i) => Math.round(x + (b[i] - x) * t));
const ramp = (stops, t) => {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [t0, c0] = stops[i - 1], [t1, c1] = stops[i];
      return mix(c0, c1, (t - t0) / (t1 - t0 || 1));
    }
  }
  return stops[stops.length - 1][1];
};

let C = {};
function buildColors() {
  const dark = matchMedia('(prefers-color-scheme: dark)').matches && document.documentElement.dataset.theme !== 'light'
    || document.documentElement.dataset.theme === 'dark';
  const get = n => hex(cssVar(n));
  C = {
    series1: get('--series-1'), series2: get('--series-2'), series3: get('--series-3'),
    highlight: get('--highlight'), crustLand: get('--crust-land'), stipple: get('--stipple'), noRecord: get('--no-record'),
  };
  const seaStops = dark
    ? [[0, hex('#5598e7')], [0.15, hex('#256abf')], [1, hex('#0d1f38')]]
    : [[0, hex('#b7d3f6')], [0.15, hex('#6da7ec')], [1, hex('#104281')]];
  const landStops = dark
    ? [[0, hex('#6f8f55')], [0.08, hex('#8a9a5e')], [0.25, hex('#9b8559')], [0.5, hex('#7e6247')], [1, hex('#c9c4ba')]]
    : [[0, hex('#a9c98d')], [0.08, hex('#c9d79b')], [0.25, hex('#d8c48e')], [0.5, hex('#b8916a')], [1, hex('#ede9e1')]];
  const grayStops = [[0, get('--sea-shallow')], [1, get('--sea-deep')]];
  const grayLand = [[0, get('--land-low')], [1, get('--land-high')]];
  // 값은 40 m 간격이다. ±10,000 m를 501칸 표로.
  C.hypso = new Uint32Array(501);
  C.gray = new Uint32Array(501);
  C.grayRGB = [];
  for (let k = 0; k < 501; k++) {
    const z = (k - 250) * 40;
    const sea = z < 0;
    C.hypso[k] = pack(sea ? ramp(seaStops, Math.sqrt(-z / 6000)) : ramp(landStops, z / 5000));
    const g = sea ? ramp(grayStops, Math.sqrt(-z / 5000)) : ramp(grayLand, z / 3000);
    C.gray[k] = pack(g);
    C.grayRGB[k] = g;
  }
}
const zIndex = z => Math.max(0, Math.min(500, Math.round(z / 40) + 250));

// ---- 자료 ----
const [summary, hist, macro, crustSl0, crustAtlas] = await Promise.all([
  fetch('data/summary.json').then(r => r.json()),
  fetch('data/hist.json').then(r => r.json()),
  fetch('data/macrostrat.json').then(r => r.json()),
  fetch('data/crust_sea_level_0.bin').then(r => r.arrayBuffer()).then(b => new Uint8Array(b)),
  fetch('data/crust_atlas.bin').then(r => r.arrayBuffer()).then(b => new Uint8Array(b)),
]);
const ages = summary.ages;
const demCache = new Map();
async function dem(i) {
  const key = `${ages[i].age}`;
  if (!demCache.has(key)) {
    demCache.set(key, fetch(`data/dem/${key}.bin`).then(r => r.arrayBuffer()).then(b => new Int16Array(b)));
  }
  return demCache.get(key);
}
const demAt = (grid, lon, lat) => grid[Math.round((90 - lat) * 2) * 721 + Math.round((lon + 180) * 2)];
const cellAt = (lon, lat) => Math.min(180, Math.floor(90.5 - lat)) * 360 + (Math.floor(lon + 180.5) % 360);

// ---- 시점 ----
let index = ages.findIndex(a => a.age === 500);
// 슬라이더는 왼쪽이 오래된 시기, 오른쪽이 현재다. ages는 0 Ma부터 오래된 순이라 뒤집는다.
const slider = $('age');
slider.max = ages.length - 1;
const toSlider = i => ages.length - 1 - i;
const levelsText = a => (a.atlas.length ? a.atlas.map(x => (x.level > 0 ? '+' : '') + x.level + ' m').join(', ') : '없음(보간 지도)');
function label(a) {
  const hist = a.history_age != null && a.history_age !== a.age ? ` (지도 나이 ${a.history_age} Ma)` : '';
  const fill = a.fill_value == null ? '없음' : `${a.fill_value > 0 ? '+' : ''}${a.fill_value} m`;
  return `<b>${a.age} Ma</b>${hist} · Map ${a.map} · Phase ${a.phase} · 아틀라스 해수면 ${levelsText(a)} · 단일값 ${fill}`;
}

// ---- 지도 ----
const maps = {};
const readout = (id, text) => { $(id).textContent = text || ''; };
const fmtLL = ([lon, lat]) => `${Math.abs(lat).toFixed(1)}°${lat >= 0 ? 'N' : 'S'} ${Math.abs(lon).toFixed(1)}°${lon >= 0 ? 'E' : 'W'}`;
const STATE = ['대륙지각 없음', '대륙지각, 물가 위', '대륙지각, 잠김', '대륙지각, 물가 아래 1,400 m보다 깊음', '깊음, 얕은 곳에서 3°보다 멂'];

let current = { grid: null, dem0: null };
function waterlineCrust(select) { return $(select).value === 'atlas' ? crustAtlas : crustSl0; }

function makeMaps() {
  maps.dem = new MollweideMap($('map-dem'), { label: 'PaleoDEM', onHover: ll => {
    if (!ll || !current.grid) return readout('readout-dem');
    readout('readout-dem', `${fmtLL(ll)} · ${demAt(current.grid, ...ll)} m`);
  } });
  maps.crust = new MollweideMap($('map-crust'), { label: '물가 아래 대륙지각', onHover: ll => {
    if (!ll || !current.grid) return readout('readout-crust');
    const code = waterlineCrust('crust-waterline')[index * CELLS + cellAt(...ll)];
    readout('readout-crust', `${fmtLL(ll)} · ${demAt(current.grid, ...ll)} m · ${STATE[code & 7]}`);
  } });
  maps.align = new MollweideMap($('map-align'), { label: '깊은 지각과 판 겹침', onHover: ll => {
    if (!ll || !current.grid) return readout('readout-align');
    const code = waterlineCrust('align-waterline')[index * CELLS + cellAt(...ll)];
    readout('readout-align', `${fmtLL(ll)} · ${STATE[code & 7]}${code & 8 ? ' · 판 겹침' : ''}`);
  } });
  maps.macro = new MollweideMap($('map-macro'), { center: -100, zoom: 2.6, panY: 0.55, label: 'Macrostrat 북미 단면', onHover: ll => {
    readout('readout-macro', ll ? `${fmtLL(ll)} (현재 위치)` : '');
  } });
  document.querySelectorAll('[data-spin]').forEach(btn => btn.addEventListener('click', () => {
    const map = maps[btn.dataset.spin.replace('map-', '')];
    map.spin(!map.spinning);
    btn.setAttribute('aria-pressed', map.spinning);
  }));
}

function drawDem() {
  const a = ages[index], g = current.grid;
  const fill = $('dem-fill').checked ? a.fill_value : null;
  const hl = pack(C.highlight);
  maps.dem.set((lon, lat) => {
    const z = demAt(g, lon, lat);
    return fill != null && z === fill ? hl : C.hypso[zIndex(z)];
  });
  $('legend-dem').innerHTML = (fill != null ? `<span><i class="swatch" style="--c:var(--highlight)"></i>단일값 ${fill > 0 ? '+' : ''}${fill} m</span>` : '<span class="muted">이 지도에는 단일값이 없다(문턱 3배 미만)</span>')
    + '<span><i class="swatch" style="--c:#6da7ec"></i>바다(깊을수록 진함)</span><span><i class="swatch" style="--c:#c9d79b"></i>육지(높을수록 갈색·흰색)</span>';
}

function crustSampler(crust, colorOf) {
  const g = current.grid, base = index * CELLS;
  return (lon, lat, px, py) => {
    const z = demAt(g, lon, lat);
    const k = zIndex(z);
    const code = crust[base + cellAt(lon, lat)];
    if (!code) return C.gray[k];
    return colorOf(code, C.grayRGB[k], px, py);
  };
}

function drawCrust() {
  const crust = waterlineCrust('crust-waterline');
  const land = pack(C.crustLand);
  maps.crust.set(crustSampler(crust, (code, g) => {
    const s = code & 7;
    if (s === 1) return pack(mix(g, C.crustLand, 0.8));
    if (s === 2) return pack(mix(g, C.series1, 0.85));
    return pack(mix(g, C.series2, 0.85));
  }));
  $('legend-crust').innerHTML = '<span><i class="swatch" style="--c:var(--crust-land)"></i>대륙지각, 물가 위</span>'
    + '<span><i class="swatch" style="--c:var(--series-1)"></i>대륙지각, 물가 아래</span>'
    + '<span><i class="swatch" style="--c:var(--series-2)"></i>그중 물가 아래 1,400 m보다 깊음</span>'
    + '<span><i class="swatch" style="--c:var(--sea-shallow)"></i>대륙지각 없음(DEM 회색조)</span>';
  void land;
}

function drawAlign() {
  const crust = waterlineCrust('align-waterline');
  maps.align.set(crustSampler(crust, (code, g, px, py) => {
    const s = code & 7;
    let c = s === 4 ? C.series2 : s === 3 ? C.series3 : mix(g, C.crustLand, 0.55);
    if (s >= 3) c = mix(g, c, 0.9);
    if (code & 8 && px % 4 === 0 && py % 4 === 0) c = C.stipple;
    return pack(c);
  }));
  $('legend-align').innerHTML = '<span><i class="swatch" style="--c:var(--crust-land)"></i>대륙지각(물가 위·얕은 잠김)</span>'
    + '<span><i class="swatch" style="--c:var(--series-3)"></i>깊음, 얕은 곳에서 3° 안</span>'
    + '<span><i class="swatch" style="--c:var(--series-2)"></i>깊음, 3°보다 멂</span>'
    + '<span><i class="swatch stipple"></i>판 겹침</span>';
}

const toCss = c => `rgb(${c.join(',')})`;
function drawMacro() {
  const codes = macro.codes[index];
  const view = $('macro-view').value;
  const g = current.dem0;
  const shapes = [];
  const surface = cssVar('--surface-1');
  macro.polygons.forEach((rings, i) => {
    const ch = codes[i];
    if (ch === '9') { shapes.push({ rings, stroke: toCss(C.noRecord), width: 1 }); return; }
    const d = +ch, record = d >> 1, wet = d & 1;
    let c;
    if (view === 'record') c = record === 2 ? C.series1 : record === 1 ? C.series2 : C.noRecord;
    else if (record === 0) c = C.noRecord;
    else if ((record === 2 && wet) || (record === 1 && !wet)) c = C.series1;
    else if (record === 2) c = C.series3;
    else c = C.series2;
    shapes.push({ rings, fill: toCss(c), stroke: surface, width: 0.6 });
  });
  maps.macro.set((lon, lat) => C.gray[zIndex(demAt(g, lon, lat))], shapes);
  $('legend-macro').innerHTML = view === 'record'
    ? '<span><i class="swatch" style="--c:var(--series-1)"></i>해성층 있음</span><span><i class="swatch" style="--c:var(--series-2)"></i>비해성층만</span><span><i class="swatch" style="--c:var(--no-record)"></i>그 나이 기록 없음</span>'
    : '<span><i class="swatch" style="--c:var(--series-1)"></i>일치(해성·잠김, 비해성·물가 위)</span><span><i class="swatch" style="--c:var(--series-3)"></i>해성층인데 모델은 물가 위</span><span><i class="swatch" style="--c:var(--series-2)"></i>비해성층만인데 모델은 잠김</span><span><i class="swatch" style="--c:var(--no-record)"></i>기록 없음</span>';
}

// ---- 차트 ----
const S = (key, a = ages) => a.map(x => [x.age, x[key]]);
const charts = [];
function pick(age) { setIndex(ages.findIndex(a => a.age === age)); }
function makeCharts() {
  charts.length = 0;
  charts.push(timeChart($('chart-fill'), {
    kind: 'dots', unit: 'm', yMin: -200, yMax: 200, onPick: pick,
    series: [
      { label: '지도마다 칠한 단일값', color: 'var(--highlight)', values: S('fill_value'), digits: 0 },
      { label: '아틀라스 해수면', color: 'var(--series-1)', values: ages.flatMap(a => a.atlas.map(x => [a.age, x.level])), digits: 0 },
    ],
    note: '단일값은 이웃 두 값 평균의 3배 넘게 몰린 값이다(문턱은 임의). 아틀라스 해수면은 정수 번호 지도만 있고, 판이 여럿이면 모두 찍었다.',
  }));
  charts.push(timeChart($('chart-shallow'), {
    unit: '백만 km²', onPick: pick,
    series: [
      { label: '0 < 수심 ≤ 200 m (해수면 0)', short: '해수면 0', color: 'var(--series-1)', values: S('shallow_0_200') },
      { label: '해수면 이상에 칠한 단일값을 바다로 더함', short: '단일값 더함', color: 'var(--series-2)', dash: true, values: S('shallow_with_fill'), labelDy: -10 },
    ],
    note: 'PaleoDEM 0.1° 격자 전체(대륙지각과 무관). 230–245 Ma와 180·200 Ma의 골이 단일값을 더하면 메워진다.',
  }));
  charts.push(timeChart($('chart-submerged'), {
    unit: '백만 km²', onPick: pick,
    series: [
      { label: '아틀라스 해수면(판이 여럿이면 최대)', short: '아틀라스', color: 'var(--series-1)', values: S('sub_atlas_max'), connect: true },
      { label: '아틀라스 해수면, 해수면과 같은 값의 칸도 잠김', short: '해수면 칸 포함', color: 'var(--series-1)', dash: true, values: S('sub_atlas_max_incl'), connect: true },
      { label: '아틀라스 해수면, 판 겹침 제거', short: '겹침 제거', color: 'var(--series-3)', values: S('dedup_atlas_max'), connect: true, labelDy: 12 },
      { label: '해수면 0', short: '해수면 0', color: 'var(--series-2)', dash: true, values: S('sub_sl0'), labelDy: -8 },
    ],
    note: '아틀라스 해수면이 없는 보간 지도는 아틀라스 선에서 건너뛴다(선은 이웃 시점을 잇는다). 해수면과 같은 값의 칸을 Scotese가 바다로 칠했는지는 지도마다 다르다(008).',
  }));
  const check = summary.atlas_check;
  charts.push(timeChart($('chart-atlas-diff'), {
    kind: 'dots', unit: 'm', yMin: -280, yMax: 160, onPick: pick,
    series: [{ label: '가장 잘 맞는 해수면 − 적은 해수면', color: 'var(--series-1)', values: check.map(c => [c.age, c.best - c.caption]), digits: 0 }],
    note: '+40은 "해수면과 같은 값의 칸까지 바다"와 같다(격자 값이 40 m 간격). 0이나 +40에서 멀리 떨어진 점은 그 해수면 근처에 칸이 적어 일치율 차이가 작은 경우가 많다.',
  }));
  charts.push(timeChart($('chart-atlas-agree'), {
    kind: 'dots', unit: '%', yMin: 90, yMax: 100, onPick: pick,
    series: [
      { label: '적은 해수면(같은 값 칸은 육지)', color: 'var(--series-1)', values: check.map(c => [c.age, c.agree_caption * 100]), digits: 1 },
      { label: '적은 해수면(같은 값 칸도 바다)', color: 'var(--series-3)', values: check.map(c => [c.age, c.agree_incl * 100]), digits: 1 },
      { label: '앞뒤 지도 중 가장 잘 맞는 DEM', color: 'var(--series-2)', values: check.map(c => [c.age, c.agree_rival * 100]), digits: 1 },
    ],
    note: '가로축은 그림을 대응시킨 DEM의 나이다. 주황 점이 파랑·청록보다 높은 그림은 이웃 DEM이 더 잘 맞는 경우다.',
  }));
  charts.push(timeChart($('chart-deep'), {
    unit: '백만 km²', onPick: pick,
    series: [
      { label: '대륙연변(대륙붕·사면·해양고원)', short: '대륙연변', color: 'var(--series-1)', values: S('deep_margin') },
      { label: '현생누대 조산대·호·열개대', short: '조산대·호', color: 'var(--series-2)', values: S('deep_orogen') },
      { label: '선캄브리아 안정지괴', short: '안정지괴', color: 'var(--series-3)', values: S('deep_craton') },
    ],
  }));
  charts.push(timeChart($('chart-overlap'), {
    unit: '백만 km²', onPick: pick,
    series: [
      { label: '판 겹침(두 번 센 면적)', short: '판 겹침', color: 'var(--series-1)', values: S('overlap') },
      { label: 'DEM 대륙인데 근처에 추적 지각 없음', short: '지각 없는 대륙', color: 'var(--series-2)', values: S('dem_without_crust'), labelDy: 12 },
    ],
    note: '판 겹침의 계산 방식 오차(실제 겹침이 없는 강체 회전에서 나오는 값)는 약 1백만 km²다.',
  }));
  charts.push(timeChart($('chart-macro-sa'), {
    unit: '백만 km²', yMin: 0, onPick: pick,
    series: [
      { label: 'Macrostrat 해성층 단면', short: '해성층', color: 'var(--series-1)', values: S('sa_marine') },
      { label: 'Scotese 지형 + 아틀라스 해수면(최대 판)', short: 'Scotese', color: 'var(--series-2)', values: S('sa_atlas_max'), connect: true },
      { label: '현대 대륙 모양 + 독립 해수면', short: '현대 모양', color: 'var(--series-3)', values: S('sa_modern') },
    ],
    note: '남미 단면 범위(대륙지각 표본점)는 4.4백만 km²다.',
  }));
  charts.push(timeChart($('chart-needed-sl'), {
    unit: 'm', yMin: -200, yMax: 1200, onPick: pick,
    series: [
      { label: '북미', short: '북미', color: 'var(--series-1)', values: S('na_needed_sl'), digits: 0 },
      { label: '남미', short: '남미', color: 'var(--series-2)', values: S('sa_needed_sl'), digits: 0 },
      { label: '독립 해수면(판구조, 평균)', short: '독립 해수면', color: 'var(--series-3)', dash: true, values: S('tect_avg_m'), digits: 0 },
    ],
    note: '단면마다 안에 든 대륙지각의 현대 고도(물·얼음 하중을 뺀 것) 중앙값을 그 단면이 잠기는 해수면으로 보고, 해성 단위가 있는 단면들의 면적 가중 중앙값을 냈다. 단면 일부만 잠겼어도 단면 전체를 세므로 크게 잡혔을 수 있다.',
  }));
  charts.push(timeChart($('chart-needed-type'), {
    unit: 'm', yMin: -400, yMax: 1600, onPick: pick,
    series: [
      { label: '북미 안정지괴 안쪽', short: '북미 안쪽', color: 'var(--series-1)', values: S('na_craton_excess'), digits: 0 },
      { label: '북미 조산대', short: '북미 조산대', color: 'var(--series-2)', values: S('na_orogen_excess'), digits: 0 },
      { label: '남미 안정지괴 안쪽', short: '남미 안쪽', color: 'var(--series-3)', values: S('sa_craton_excess'), digits: 0 },
      { label: '북미 안쪽, 현재 잔차 지형 보정(015)', short: '북미 안쪽 보정', color: 'var(--series-1)', dash: true, values: S('na_craton_corr_excess'), digits: 0 },
    ],
    note: '0보다 크면 현대 모양과 독립 해수면으로는 그 단면들의 해성층을 담지 못한다. 단면 유형은 단면 안 CRUST1.0 표본점 면적이 가장 큰 현대 지각 유형이다.',
  }));
  independentCharts();
  marginChart();
  volumeCharts();
  charts.push(timeChart($('chart-macro'), {
    unit: '백만 km²', onPick: pick,
    series: [
      { label: '모델 잠김(아틀라스 해수면 최대 판)', short: '모델', color: 'var(--series-2)', values: S('model_na_atlas_max'), connect: true },
      { label: 'Macrostrat 해성층 단면', short: '해성층', color: 'var(--series-1)', values: S('macro_marine') },
      { label: 'PBDB 연결 단위를 뺀 해성층 단면', short: 'PBDB 뺌', color: 'var(--series-1)', dash: true, values: S('macro_marine_nopbdb'), labelDy: 12 },
      { label: '현대 대륙 모양 + 독립 해수면(012)', short: '현대 모양', color: 'var(--series-3)', values: S('model_na_modern') },
    ],
    note: '모델 범위(단면 안 대륙지각 표본점)는 24.6백만 km²다. 해성층 단면은 퇴적·보존을 거친 하한이다.',
  }));
}

function independentCharts() {
  const cap = ages.map(a => [a.age, 28.18]);
  charts.push(timeChart($('chart-sealevel'), {
    unit: 'm', yMin: -100, yMax: 240, onPick: pick,
    series: [
      { label: '판구조 해수면(스트론튬, 평균)', short: '판구조', color: 'var(--series-1)', values: S('tect_avg_m'), digits: 0 },
      { label: '판구조 + 빙하', short: '+ 빙하', color: 'var(--series-3)', dash: true, values: S('tge_avg_m'), digits: 0 },
      { label: 'Scotese 아틀라스 해수면', color: 'var(--series-2)', dot: true, values: ages.flatMap(a => a.atlas.map(x => [a.age, x.level])), digits: 0 },
    ],
    note: 'van der Meer et al. (2022) 부록 1. 판구조 성분의 최소–최대 범위는 캄브리아기에 ±50 m 안팎이다.',
  }));
  charts.push(timeChart($('chart-models'), {
    unit: '백만 km²', yMin: 0, onPick: pick,
    series: [
      { label: 'Scotese 지형(모델 A), 물가 아래 0–200 m', short: 'A 0–200 m', color: 'var(--series-2)', values: S('A_band_tect_avg') },
      { label: '현대 대륙 모양(모델 B), 잠긴 전체', short: 'B 전체', color: 'var(--series-3)', values: S('B_tect_avg') },
      { label: '현대 대륙 모양(모델 B), 물가 아래 0–200 m', short: 'B 0–200 m', color: 'var(--series-1)', values: S('B_band_tect_avg') },
      { label: '현대 모양에서 0–200 m 띠의 상한(28.2)', short: '상한', color: 'var(--text-muted)', dash: true, values: cap },
    ],
    note: '모델 B는 현대 대륙지각의 고도 분포(물·얼음 하중을 뺀 것)를 고정하고 해수면만 바꾼다. 대륙 배치·연변 길이·열침강은 넣지 않았다.',
  }));
}

function marginChart() {
  charts.push(timeChart($('chart-margin'), {
    unit: '백만 km²', yMin: 0, yMax: 45, onPick: pick,
    series: [
      { label: '연변 길이 × 121 km (모든 추적 지각)', short: '모든 지각', color: 'var(--series-1)', values: S('shelf_harris_width') },
      { label: '그때 없던 지괴를 뺌', short: '지괴 뺌', color: 'var(--series-2)', dash: true, values: S('shelf_harris_width_without_far') },
      { label: '현대 대륙 모양의 0–200 m 띠(009, 판구조 해수면)', short: '0–200 m 띠', color: 'var(--series-3)', values: S('B_band_tect_avg') },
    ],
    note: '연변 길이는 3° 칸에서 잰다. 현재 대륙을 통째로 돌려 잰 길이(기준값)의 오차는 ±2.5%다. 폭 121 km는 현재 대륙붕 32.24백만 km²(Harris et al. 2014)를 기준값으로 나눈 값이다.',
  }));
}

function volumeCharts() {
  charts.push(timeChart($('chart-volume'), {
    unit: '현재 = 1', yMin: 0.6, yMax: 1.1, onPick: pick,
    series: [
      { label: '추적 면적 전체', short: '추적 전체', color: 'var(--series-1)', values: S('tracked_volume_ratio'), digits: 3 },
      { label: '판 겹침 제거', short: '겹침 제거', color: 'var(--series-3)', values: S('dedup_volume_ratio'), digits: 3 },
      { label: '겹침과 그때 없던 지괴 제거', short: '지괴도 제거', color: 'var(--series-2)', values: S('dedup_without_far_volume_ratio'), digits: 3 },
    ],
    note: '두께는 PaleoDEM 고도에서 바닷물 하중을 빼고 현대 CRUST1.0의 고도별 평균 두께로 바꿨다. 고생대 대륙의 열 상태가 달랐다면 같은 고도에 다른 두께가 대응한다.',
  }));
  charts.push(timeChart($('chart-volume-sens'), {
    unit: '현재 = 1', yMin: 0.85, yMax: 1.1, onPick: pick,
    series: [
      { label: 'Δ = 0 m', short: 'Δ 0', color: 'var(--series-2)', values: S('thick_offset_0'), digits: 3 },
      { label: 'Δ = 200 m', short: 'Δ 200', color: 'var(--series-1)', values: S('thick_offset_200'), digits: 3 },
      { label: 'Δ = 300 m', short: 'Δ 300', color: 'var(--series-3)', values: S('thick_offset_300'), digits: 3 },
    ],
    note: 'Scotese 고도를 "등압평형 고도 − Δ"로 보고 두께로 바꾼 평균 두께 / 현재(그때 없던 지괴·겹침 제외). Δ는 동적 지형 등으로 눌린 높이다.',
  }));
  charts.push(timeChart($('chart-volume-parts'), {
    unit: '현재 = 1', yMin: 0.6, yMax: 1.1, onPick: pick,
    series: [
      { label: '면적', short: '면적', color: 'var(--series-1)', values: S('volume_area_ratio'), digits: 3 },
      { label: '평균 두께', short: '평균 두께', color: 'var(--series-2)', values: S('volume_thickness_ratio'), digits: 3 },
    ],
  }));
}

function drawRegions() {
  const rows = summary.regions[`${ages[index].age}`] || [];
  categoryBars($('chart-regions'), {
    categories: rows.map(r => r[0]), unit: '%', yMin: -10, yMax: 40,
    series: [
      { label: '면적 몫(그때 없던 지괴·판 겹침)', color: 'var(--series-1)', values: rows.map(r => r[1]) },
      { label: '두께 몫(Scotese 고도로 낸 두께가 얇음)', color: 'var(--series-2)', values: rows.map(r => r[2]) },
    ],
    note: '지역은 PALEOMAP 판 번호의 첫 자리로 묶었다. 기준은 0 Ma 지도에서 같은 방법으로 낸 두께다. 두께 몫이 음수면 그 지역을 지금보다 높게 칠했다는 뜻이다.',
  });
}

function drawHist() {
  const a = ages[index];
  const values = [];
  for (let v = -480; v <= 200; v += 40) values.push(v);
  valueBars($('chart-hist'), { values, data: hist[`${a.age}`] || {}, reference: hist['0'] || {}, highlight: a.fill_value,
    color: 'var(--series-1)', highlightColor: 'var(--highlight)', unit: '백만 km²' });
}

function plateTable() {
  const region = { 402: '서시베리아·카자흐스탄', 628: '몽골–아무르, 중국 동북', 514: '투란(중앙아시아)', 406: '오호츠크–추코트카',
    310: '바렌츠 대륙붕', 804: '서남극(마리버드랜드)', 127: '북미 코딜레라', 125: '알래스카 남부', 803: '남극반도', 410: '오호츠크해', 403: '시베리아 북동' };
  const rows = summary.plates_500.map(p => `<tr><td>${p.plate_id}</td><td>${region[p.plate_id] || '—'}</td><td>${p.main_types}</td>`
    + `<td class="num">${p.area.toFixed(2)}</td><td class="num">${p.deep.toFixed(2)}</td><td class="num">${p.deep_farther_than_3deg.toFixed(2)}</td></tr>`).join('');
  $('table-plates').innerHTML = '<thead><tr><th>판</th><th>지역(현대 위치로 짐작)</th><th>주 지각 유형</th><th class="num">판 면적</th><th class="num">깊음</th><th class="num">그중 3°보다 멂</th></tr></thead><tbody>' + rows + '</tbody>';
}

// ---- 갱신 ----
let token = 0;
async function setIndex(i) {
  index = Math.max(0, Math.min(ages.length - 1, i));
  slider.value = toSlider(index);
  const a = ages[index];
  $('age-label').innerHTML = label(a);
  const my = ++token;
  const grid = await dem(index);
  if (my !== token) return;
  current.grid = grid;
  drawDem(); drawCrust(); drawAlign(); drawMacro(); drawHist(); drawRegions();
  charts.forEach(c => c.setAge(a.age));
  for (const d of [-1, 1]) if (ages[index + d]) dem(index + d);
}

function redrawAll() {
  buildColors();
  makeCharts();
  setIndex(index);
}

// ---- 단계 메뉴: 한 번에 한 단계만 보인다. 주소의 #id로 바로 연다. ----
const sections = [...document.querySelectorAll('main > section[data-tab]')];
const tabBox = $('tabs');
const tabButtons = sections.map(sec => {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'tab'; b.role = 'tab'; b.textContent = sec.dataset.tab;
  b.setAttribute('aria-controls', sec.id);
  b.addEventListener('click', () => { if (location.hash !== '#' + sec.id) history.pushState(null, '', '#' + sec.id); showTab(sec.id); });
  tabBox.appendChild(b);
  return b;
});
function showTab(id) {
  const target = sections.find(s => s.id === id) || sections[0];
  sections.forEach((sec, i) => {
    const on = sec === target;
    sec.hidden = !on;
    tabButtons[i].setAttribute('aria-selected', on);
    tabButtons[i].tabIndex = on ? 0 : -1;
    if (on) tabButtons[i].scrollIntoView({ block: 'nearest', inline: 'nearest' });
  });
  $('agebar').hidden = target.dataset.age === 'no';
  window.scrollTo({ top: 0 });
}
tabBox.addEventListener('keydown', e => {
  const i = tabButtons.indexOf(document.activeElement);
  if (i < 0) return;
  const j = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : null;
  if (j == null || !tabButtons[j]) return;
  tabButtons[j].focus(); tabButtons[j].click(); e.preventDefault();
});
window.addEventListener('popstate', () => showTab(location.hash.slice(1)));
showTab(location.hash.slice(1));

buildColors();
makeMaps();
current.dem0 = await dem(ages.findIndex(a => a.age === 0));
makeCharts();
plateTable();
fetch('healthz').then(r => r.json()).then(h => { $('version').textContent = h.version; }).catch(() => { $('version').textContent = VERSION; });
slider.addEventListener('input', () => setIndex(toSlider(+slider.value)));
['dem-fill'].forEach(id => $(id).addEventListener('change', drawDem));
$('crust-waterline').addEventListener('change', drawCrust);
$('align-waterline').addEventListener('change', drawAlign);
$('macro-view').addEventListener('change', drawMacro);
let timer = null;
$('play').addEventListener('click', () => {
  if (timer) { clearInterval(timer); timer = null; $('play').textContent = '▶'; return; }
  $('play').textContent = '❚❚';
  // 재생은 오래된 시기에서 현재 쪽으로(오른쪽으로) 간다.
  timer = setInterval(() => setIndex(index <= 0 ? ages.length - 1 : index - 1), 700);
});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', redrawAll);
await setIndex(index);
