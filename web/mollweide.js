// 회전 가능한 몰바이데 지도. EarthThruTime3D(static/core/projection.js)의 방식을 따른다:
// 평면이 극축을 중심으로 돌아 중앙 경선이 바뀌고, 픽셀마다 역투영해 경위도의 값을 읽는다.
// 경위선과 벡터 도형은 같은 이동을 거쳐 그리고, 새 이음매에서 끊는다.

const DEG = Math.PI / 180;

// 정규화 좌표: 적도 반폭 x = 1, 극 y = 1 (화면에서는 높이가 폭의 절반).
export function forward(lonDeg, latDeg) {
  const target = Math.PI * Math.sin(latDeg * DEG);
  let theta = latDeg * DEG;
  for (let i = 0; i < 30; i++) {
    const f = 2 * theta + Math.sin(2 * theta) - target;
    const d = 2 + 2 * Math.cos(2 * theta);
    if (Math.abs(d) < 1e-12) break;
    const step = f / d;
    theta -= step;
    if (Math.abs(step) < 1e-10) break;
  }
  return [lonDeg / 180 * Math.cos(theta), Math.sin(theta)];
}

export function inverse(x, y) {
  if (x * x + y * y > 1) return null;
  const theta = Math.asin(Math.max(-1, Math.min(1, y)));
  const lon = x / Math.max(Math.cos(theta), 1e-9) * 180;
  if (Math.abs(lon) > 180) return null;
  const lat = Math.asin((2 * theta + Math.sin(2 * theta)) / Math.PI) / DEG;
  return [lon, lat];
}

const wrap = lon => ((lon + 180) % 360 + 360) % 360 - 180;

export class MollweideMap {
  // sampler(lon, lat) → 0xAABBGGRR(Uint32, 리틀 엔디언 RGBA) 또는 0(투명)
  constructor(host, { center = 0, zoom = 1, panY = 0, label = '지도', onHover = null } = {}) {
    this.host = host;
    this.center = center;
    this.zoom = zoom;
    this.panY = panY;
    this.home = { center, zoom, panY };
    this.sampler = () => 0;
    this.vectors = [];
    this.onHover = onHover;
    this.canvas = document.createElement('canvas');
    this.canvas.className = 'moll-canvas';
    this.canvas.tabIndex = 0;
    this.canvas.setAttribute('role', 'img');
    this.canvas.setAttribute('aria-label', label + ' (몰바이데 투영, 좌우로 끌거나 화살표 키로 회전, + − 키로 확대)');
    host.appendChild(this.canvas);
    const zoomBox = document.createElement('div');
    zoomBox.className = 'zoom-box';
    for (const [text, title, act] of [['+', '확대', () => this.zoomBy(1.5)], ['−', '축소', () => this.zoomBy(1 / 1.5)], ['⟲', '처음 보기', () => this.reset()]]) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'zoom-btn'; b.textContent = text; b.title = title; b.setAttribute('aria-label', title);
      b.addEventListener('click', act);
      zoomBox.appendChild(b);
    }
    host.appendChild(zoomBox);
    this.ctx = this.canvas.getContext('2d');
    this.spinning = false;
    this.bind();
    new ResizeObserver(() => this.resize()).observe(host);
    this.resize();
  }

  resize() {
    const css = Math.max(280, this.host.clientWidth);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.min(1800, Math.round(css * dpr));
    if (width === this.width) return;
    this.width = width;
    this.height = Math.round(width / 2);
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    this.canvas.style.height = (css / 2) + 'px';
    this.image = this.ctx.createImageData(this.width, this.height);
    this.pixels = new Uint32Array(this.image.data.buffer);
    this.grid();
  }

  // 화면 픽셀 ↔ 정규화 좌표. 확대(zoom)와 세로 이동(panY)은 평면에서, 회전은 중앙 경선으로 한다.
  toNorm(px, py) {
    const rx = (this.width / 2 - 2) * this.zoom, ry = (this.height / 2 - 2) * this.zoom;
    return [(px - this.width / 2) / rx, -(py - this.height / 2) / ry + this.panY];
  }

  grid() {
    // 픽셀마다 (기준 경도, 위도)를 미리 구한다. 중앙 경선은 그릴 때 더한다.
    const n = this.width * this.height;
    if (!this.baseLon || this.baseLon.length !== n) {
      this.baseLon = new Float32Array(n);
      this.lat = new Float32Array(n);
      this.inside = new Uint8Array(n);
    }
    this.inside.fill(0);
    for (let py = 0; py < this.height; py++) {
      for (let px = 0; px < this.width; px++) {
        const [x, y] = this.toNorm(px + 0.5, py + 0.5);
        const ll = inverse(x, y);
        const i = py * this.width + px;
        if (ll) { this.inside[i] = 1; this.baseLon[i] = ll[0]; this.lat[i] = ll[1]; }
      }
    }
    this.draw();
  }

  zoomBy(f) {
    this.zoom = Math.max(1, Math.min(8, this.zoom * f));
    this.clampPan();
    this.grid();
  }

  clampPan() {
    const room = Math.max(0, 1 - 1 / this.zoom);
    this.panY = Math.max(-room, Math.min(room, this.panY));
  }

  reset() {
    Object.assign(this, this.home);
    this.grid();
  }

  set(sampler, vectors = []) {
    this.sampler = sampler;
    this.vectors = vectors;
    this.draw();
  }

  project(lon, lat) {
    const [x, y] = forward(wrap(lon - this.center), lat);
    const rx = (this.width / 2 - 2) * this.zoom, ry = (this.height / 2 - 2) * this.zoom;
    return [this.width / 2 + x * rx, this.height / 2 - (y - this.panY) * ry];
  }

  draw() {
    if (!this.pixels) return;
    const { pixels, baseLon, lat, inside, sampler } = this;
    const c = this.center;
    for (let i = 0; i < pixels.length; i++) {
      if (!inside[i]) { pixels[i] = 0; continue; }
      let lon = baseLon[i] + c;
      if (lon >= 180) lon -= 360; else if (lon < -180) lon += 360;
      pixels[i] = sampler(lon, lat[i], i % this.width, (i / this.width) | 0);
    }
    const ctx = this.ctx;
    ctx.putImageData(this.image, 0, 0);
    this.drawVectors();
    this.drawGraticule();
  }

  drawVectors() {
    const ctx = this.ctx;
    for (const shape of this.vectors) {
      ctx.beginPath();
      let ok = true;
      for (const ring of shape.rings) {
        let prev = null;
        const pts = ring.map(([lon, lat]) => this.project(lon, lat));
        for (const p of pts) {
          if (prev && Math.abs(p[0] - prev[0]) > this.width / 3) { ok = false; break; }
          prev = p;
        }
        if (!ok) break;
        pts.forEach((p, k) => (k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
        ctx.closePath();
      }
      if (!ok) continue;
      if (shape.fill) { ctx.fillStyle = shape.fill; ctx.fill(); }
      if (shape.stroke) { ctx.strokeStyle = shape.stroke; ctx.lineWidth = shape.width || 1; ctx.stroke(); }
    }
  }

  drawGraticule() {
    const ctx = this.ctx;
    const style = getComputedStyle(this.host);
    ctx.strokeStyle = style.getPropertyValue('--graticule').trim() || 'rgba(0,0,0,0.25)';
    ctx.lineWidth = Math.max(1, this.width / 1400);
    const line = pts => {
      ctx.beginPath();
      let prev = null;
      for (const p of pts) {
        if (!prev || Math.abs(p[0] - prev[0]) > this.width / 3) ctx.moveTo(p[0], p[1]);
        else ctx.lineTo(p[0], p[1]);
        prev = p;
      }
      ctx.stroke();
    };
    for (let lon = -180; lon < 180; lon += 30) {
      const pts = [];
      for (let lat = -90; lat <= 90; lat += 2) pts.push(this.project(lon, lat));
      line(pts);
    }
    for (let lat = -60; lat <= 60; lat += 30) {
      const pts = [];
      for (let k = -180; k <= 180; k += 2) pts.push(this.project(this.center + k, lat));
      line(pts);
    }
    ctx.lineWidth = Math.max(1.5, this.width / 900);
    ctx.strokeStyle = style.getPropertyValue('--map-edge').trim() || 'rgba(0,0,0,0.5)';
    ctx.beginPath();
    const rx = (this.width / 2 - 2) * this.zoom, ry = (this.height / 2 - 2) * this.zoom;
    ctx.ellipse(this.width / 2, this.height / 2 + this.panY * ry, rx, ry, 0, 0, 2 * Math.PI);
    ctx.stroke();
  }

  rotate(delta) {
    this.center = wrap(this.center + delta);
    this.draw();
    this.host.dispatchEvent(new CustomEvent('rotate', { detail: this.center }));
  }

  spin(on) {
    this.spinning = on;
    let last = performance.now();
    const step = now => {
      if (!this.spinning) return;
      this.rotate(-(now - last) / 1000 * 15);
      last = now;
      requestAnimationFrame(step);
    };
    if (on) requestAnimationFrame(step);
  }

  lonLatAt(event) {
    const r = this.canvas.getBoundingClientRect();
    const px = (event.clientX - r.left) / r.width * this.width;
    const py = (event.clientY - r.top) / r.height * this.height;
    const [x, y] = this.toNorm(px, py);
    const ll = inverse(x, y);
    return ll && [wrap(ll[0] + this.center), ll[1]];
  }

  bind() {
    let drag = null;
    this.canvas.addEventListener('pointerdown', e => {
      drag = { x: e.clientX, y: e.clientY, center: this.center, panY: this.panY };
      this.canvas.setPointerCapture(e.pointerId);
    });
    this.canvas.addEventListener('pointermove', e => {
      if (drag) {
        const r = this.canvas.getBoundingClientRect();
        this.center = wrap(drag.center - (e.clientX - drag.x) / r.width * 360 / this.zoom);
        if (this.zoom > 1) {
          const before = this.panY;
          this.panY = drag.panY + (e.clientY - drag.y) / (r.height / 2) / this.zoom;
          this.clampPan();
          if (this.panY !== before) { this.grid(); return; }
        }
        this.draw();
      } else if (this.onHover) {
        this.onHover(this.lonLatAt(e), e);
      }
    });
    const end = () => { drag = null; };
    this.canvas.addEventListener('pointerup', end);
    this.canvas.addEventListener('pointercancel', end);
    this.canvas.addEventListener('pointerleave', () => this.onHover && this.onHover(null));
    this.canvas.addEventListener('keydown', e => {
      if (e.key === 'ArrowLeft') { this.rotate(-10); e.preventDefault(); }
      if (e.key === 'ArrowRight') { this.rotate(10); e.preventDefault(); }
      if (e.key === '+' || e.key === '=') { this.zoomBy(1.5); e.preventDefault(); }
      if (e.key === '-') { this.zoomBy(1 / 1.5); e.preventDefault(); }
    });
  }
}
