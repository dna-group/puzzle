# app.py
# Streamlit app embedding a fully client-side Slitherlink UI in an HTML/JS canvas.
# Usage: pip install streamlit
# then: streamlit run app.py

import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(layout="wide")

st.markdown(
    """
## Slitherlink — Zoomed Editing + Mini-map

Left: controls (simple). The main interactive UI is the embedded canvas below.
"""
)

html_code = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Slitherlink Zoom + Minimap</title>
<style>
  html,body { height:100%; margin:0; font-family: Arial, sans-serif; }
  #container { position:relative; height:80vh; width:100%; background:#000; overflow:hidden; }
  #mainCanvas { background: #000; display:block; margin:0; touch-action: none; }
  #minimap { position:absolute; bottom:20px; right:20px; background:#000; border:1px solid #222; box-shadow:0 2px 8px rgba(0,0,0,0.5); }
  /* HUD text */
  #hud { position:absolute; left:12px; top:12px; background:rgba(0,0,0,0.6); color:#fff; padding:6px 8px; border-radius:6px; border:1px solid #333; font-size:13px; }
  .btn { padding:6px 8px; border-radius:4px; border:1px solid #444; background:#111; color:#fff; cursor:pointer; display:inline-block; margin-right:6px; }
</style>
</head>
<body>
<div id="container">
  <div id="hud">
    <span class="btn" id="zoomInBtn">Zoom In</span>
    <span class="btn" id="zoomOutBtn">Zoom Out</span>
    <span class="btn" id="resetBtn">Reset</span>
    <span style="margin-left:8px">Mode: click to toggle edge (degree ≤ 2)</span>
  </div>
  <canvas id="mainCanvas"></canvas>
  <canvas id="minimap"></canvas>
</div>

<script>
(() => {
  // CONFIG
  const COLS = 128;
  const ROWS = 178;
  const DOT_SPACING = 9;
  const DOT_RADIUS = 1.0;
  const EDGE_HIT_RADIUS = 10; // screen pixels
  const MIN_ZOOM = 0.6;
  const MAX_ZOOM = 6.0;
  const INITIAL_ZOOM = 3.2;

  const fullWidth = (COLS - 1) * DOT_SPACING;
  const fullHeight = (ROWS - 1) * DOT_SPACING;

  // DOM
  const mainC = document.getElementById('mainCanvas');
  const miniC = document.getElementById('minimap');
  const zoomInBtn = document.getElementById('zoomInBtn');
  const zoomOutBtn = document.getElementById('zoomOutBtn');
  const resetBtn = document.getElementById('resetBtn');
  const container = document.getElementById('container');

  const mc = mainC.getContext('2d', { alpha: false });
  const mm = miniC.getContext('2d');

  // State
  let zoom = INITIAL_ZOOM;
  let viewport = { cx: fullWidth/2, cy: fullHeight/2, w: 800/zoom, h: 600/zoom };

  const edges = new Map();
  const degree = new Map();

  function nodeKey(ix, iy) { return `${ix},${iy}`; }
  function edgeKey(a,b) {
    const ka = `${a.x},${a.y}`, kb = `${b.x},${b.y}`;
    return ka < kb ? ka + '|' + kb : kb + '|' + ka;
  }

  function addEdge(a,b) {
    const key = edgeKey(a,b);
    if (edges.has(key)) return false;
    const da = degree.get(nodeKey(a.x,a.y)) || 0;
    const db = degree.get(nodeKey(b.x,b.y)) || 0;
    if (da >= 2 || db >= 2) return false;
    edges.set(key, true);
    degree.set(nodeKey(a.x,a.y), da+1);
    degree.set(nodeKey(b.x,b.y), db+1);
    return true;
  }
  function removeEdge(a,b) {
    const key = edgeKey(a,b);
    if (!edges.has(key)) return false;
    edges.delete(key);
    const ka = nodeKey(a.x,a.y), kb = nodeKey(b.x,b.y);
    degree.set(ka, (degree.get(ka)||1)-1);
    degree.set(kb, (degree.get(kb)||1)-1);
    return true;
  }

  function fullToScreen(fullX, fullY, canvasW, canvasH) {
    const left = viewport.cx - viewport.w/2;
    const top  = viewport.cy - viewport.h/2;
    const vx = (fullX - left) / viewport.w * canvasW;
    const vy = (fullY - top)  / viewport.h * canvasH;
    return { x: vx, y: vy };
  }
  function screenToFull(sx, sy, canvasW, canvasH) {
    const left = viewport.cx - viewport.w/2;
    const top  = viewport.cy - viewport.h/2;
    const fx = left + (sx / canvasW) * viewport.w;
    const fy = top  + (sy / canvasH) * viewport.h;
    return { x: fx, y: fy };
  }

  function findNearestEdgeToFull(fullX, fullY) {
    const gx = fullX / DOT_SPACING;
    const gy = fullY / DOT_SPACING;
    const ix = Math.round(gx);
    const iy = Math.round(gy);

    let best = { dist: Infinity, a: null, b: null };
    for (let dx=-2; dx<=2; dx++) {
      for (let dy=-2; dy<=2; dy++) {
        const nx = ix+dx, ny = iy+dy;
        if (nx >= 0 && nx+1 < COLS && ny >= 0 && ny < ROWS) {
          const ax = nx * DOT_SPACING, ay = ny * DOT_SPACING;
          const bx = (nx+1) * DOT_SPACING, by = ny * DOT_SPACING;
          const mx = 0.5*(ax+bx), my = 0.5*(ay+by);
          const d2 = (mx-fullX)*(mx-fullX) + (my-fullY)*(my-fullY);
          if (d2 < best.dist) best = { dist: d2, a: {x:nx,y:ny}, b: {x:nx+1,y:ny} };
        }
        if (nx >= 0 && nx < COLS && ny >= 0 && ny+1 < ROWS) {
          const ax = nx * DOT_SPACING, ay = ny * DOT_SPACING;
          const bx = nx * DOT_SPACING, by = (ny+1) * DOT_SPACING;
          const mx = 0.5*(ax+bx), my = 0.5*(ay+by);
          const d2 = (mx-fullX)*(mx-fullX) + (my-fullY)*(my-fullY);
          if (d2 < best.dist) best = { dist: d2, a: {x:nx,y:ny}, b: {x:nx,y:ny+1} };
        }
      }
    }
    return best;
  }

  // Mini-map sizing to match puzzle aspect ratio while respecting max dims
  function sizeMinimap() {
    const maxDim = 300; // maximum for longer side
    const ratio = fullWidth / fullHeight;
    let w, h;
    if (ratio >= 1) {
      w = maxDim;
      h = Math.round(maxDim / ratio);
    } else {
      h = maxDim;
      w = Math.round(maxDim * ratio);
    }
    // add small padding for border
    miniC.width = w + 8;
    miniC.height = h + 8;
    miniC.style.width = miniC.width + "px";
    miniC.style.height = miniC.height + "px";
  }

  function resizeMainCanvas() {
    const rect = container.getBoundingClientRect();
    mainC.width = Math.max(400, Math.floor(rect.width));
    mainC.height = Math.max(400, Math.floor(rect.height));
    viewport.w = mainC.width / zoom;
    viewport.h = mainC.height / zoom;
    // ensure viewport stays inside bounds
    viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, viewport.cx));
    viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, viewport.cy));
  }

  function draw() {
    // main canvas (black background)
    mc.clearRect(0,0, mainC.width, mainC.height);
    mc.fillStyle = '#000';
    mc.fillRect(0,0, mainC.width, mainC.height);

    // visible grid range
    const left = viewport.cx - viewport.w/2;
    const top  = viewport.cy - viewport.h/2;
    const right = left + viewport.w;
    const bottom = top + viewport.h;
    const minI = Math.max(0, Math.floor(left / DOT_SPACING) - 1);
    const maxI = Math.min(COLS-1, Math.ceil(right / DOT_SPACING) + 1);
    const minJ = Math.max(0, Math.floor(top  / DOT_SPACING) - 1);
    const maxJ = Math.min(ROWS-1, Math.ceil(bottom / DOT_SPACING) + 1);

    mc.fillStyle = '#fff';
    const rad = Math.max(0.6, DOT_RADIUS * zoom/2);
    for (let j=minJ; j<=maxJ; j++) {
      for (let i=minI; i<=maxI; i++) {
        const fx = i*DOT_SPACING, fy = j*DOT_SPACING;
        const p = fullToScreen(fx, fy, mainC.width, mainC.height);
        if (p.x < -2 || p.x > mainC.width+2 || p.y < -2 || p.y > mainC.height+2) continue;
        mc.beginPath();
        mc.arc(p.x, p.y, rad, 0, Math.PI*2);
        mc.fill();
      }
    }

    // draw edges in blue
    mc.lineWidth = Math.max(1, Math.min(3, zoom*0.9));
    mc.strokeStyle = '#0b4da2';
    mc.lineCap = 'round';
    mc.beginPath();
    edges.forEach((v, k) => {
      const [n1,n2] = k.split('|');
      const [i1,j1] = n1.split(',').map(Number);
      const [i2,j2] = n2.split(',').map(Number);
      const p1 = fullToScreen(i1*DOT_SPACING, j1*DOT_SPACING, mainC.width, mainC.height);
      const p2 = fullToScreen(i2*DOT_SPACING, j2*DOT_SPACING, mainC.width, mainC.height);
      mc.moveTo(p1.x, p1.y);
      mc.lineTo(p2.x, p2.y);
    });
    mc.stroke();

    drawMinimap();
  }

  function drawMinimap() {
    const mw = miniC.width, mh = miniC.height;
    mm.clearRect(0,0,mw,mh);
    mm.fillStyle = '#000';
    mm.fillRect(0,0,mw,mh);

    const pad = 4;
    const availW = mw - pad*2, availH = mh - pad*2;
    const scale = Math.min(availW / fullWidth, availH / fullHeight);
    const offX = (mw - fullWidth*scale)/2;
    const offY = (mh - fullHeight*scale)/2;

    // draw a sparse set of white dots for visibility on black background
    mm.fillStyle = '#fff';
    const dotStep = 12;
    for (let j=0; j<ROWS; j+=dotStep) {
      for (let i=0; i<COLS; i+=dotStep) {
        const x = offX + i*DOT_SPACING*scale;
        const y = offY + j*DOT_SPACING*scale;
        mm.fillRect(x-0.5, y-0.5, 1, 1);
      }
    }

    // draw edges
    mm.strokeStyle = '#0b4da2';
    mm.lineWidth = 1;
    mm.beginPath();
    edges.forEach((v, k) => {
      const [n1,n2] = k.split('|');
      const [i1,j1] = n1.split(',').map(Number);
      const [i2,j2] = n2.split(',').map(Number);
      const x1 = offX + i1*DOT_SPACING*scale, y1 = offY + j1*DOT_SPACING*scale;
      const x2 = offX + i2*DOT_SPACING*scale, y2 = offY + j2*DOT_SPACING*scale;
      mm.moveTo(x1, y1); mm.lineTo(x2, y2);
    });
    mm.stroke();

    // draw viewport rectangle as solid white
    mm.strokeStyle = '#fff';
    mm.lineWidth = 2;
    mm.setLineDash([]);
    const vx = (viewport.cx - viewport.w/2) * scale + offX;
    const vy = (viewport.cy - viewport.h/2) * scale + offY;
    const vw = viewport.w * scale;
    const vh = viewport.h * scale;
    mm.strokeRect(vx, vy, vw, vh);
  }

  // Interaction: click+drag pans on main canvas. A short click (no move) toggles edge.
  let isPointerDown = false;
  let pointerStart = null;
  let isDragging = false;
  const DRAG_THRESHOLD = 6; // pixels

  mainC.addEventListener('pointerdown', (ev) => {
    mainC.setPointerCapture(ev.pointerId);
    isPointerDown = true;
    isDragging = false;
    pointerStart = { x: ev.clientX, y: ev.clientY, cx: viewport.cx, cy: viewport.cy };
    ev.preventDefault();
  });

  window.addEventListener('pointermove', (ev) => {
    if (!isPointerDown || !pointerStart) return;
    const dx = ev.clientX - pointerStart.x;
    const dy = ev.clientY - pointerStart.y;
    if (!isDragging && Math.hypot(dx, dy) > DRAG_THRESHOLD) isDragging = true;
    if (isDragging) {
      // translate screen delta to full-space movement (pan)
      const fx = -dx * (viewport.w / mainC.width);
      const fy = -dy * (viewport.h / mainC.height);
      viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, pointerStart.cx + fx));
      viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, pointerStart.cy + fy));
      draw();
    }
  });

  mainC.addEventListener('pointerup', (ev) => {
    mainC.releasePointerCapture(ev.pointerId);
    if (!isPointerDown) return;
    isPointerDown = false;
    // if it was not a drag, treat as click to toggle edge
    const dx = ev.clientX - pointerStart.x;
    const dy = ev.clientY - pointerStart.y;
    if (!isDragging && Math.hypot(dx, dy) <= DRAG_THRESHOLD) {
      handleMainClick(ev);
    }
    pointerStart = null;
    isDragging = false;
  });

  function handleMainClick(ev) {
    const rect = mainC.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    const full = screenToFull(sx, sy, mainC.width, mainC.height);
    const nearest = findNearestEdgeToFull(full.x, full.y);
    if (!nearest || nearest.dist === Infinity) return;
    const midpointFullX = 0.5 * ((nearest.a.x + nearest.b.x) * DOT_SPACING);
    const midpointFullY = 0.5 * ((nearest.a.y + nearest.b.y) * DOT_SPACING);
    const screenMid = fullToScreen(midpointFullX, midpointFullY, mainC.width, mainC.height);
    const dx = screenMid.x - sx, dy = screenMid.y - sy;
    const dist = Math.sqrt(dx*dx + dy*dy);
    if (dist > EDGE_HIT_RADIUS) return;
    const key = edgeKey(nearest.a, nearest.b);
    if (edges.has(key)) {
      removeEdge(nearest.a, nearest.b);
    } else {
      addEdge(nearest.a, nearest.b);
    }
    draw();
  }

  miniC.addEventListener('click', (ev) => {
    const rect = miniC.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    const mw = miniC.width, mh = miniC.height;
    const pad = 4;
    const availW = mw - pad*2, availH = mh - pad*2;
    const scale = Math.min(availW / fullWidth, availH / fullHeight);
    const offX = (mw - fullWidth*scale)/2;
    const offY = (mh - fullHeight*scale)/2;
    const fx = (sx - offX) / scale;
    const fy = (sy - offY) / scale;
    const halfW = viewport.w/2, halfH = viewport.h/2;
    const cx = Math.max(halfW, Math.min(fullWidth - halfW, fx));
    const cy = Math.max(halfH, Math.min(fullHeight - halfH, fy));
    viewport.cx = cx; viewport.cy = cy;
    draw();
  });

  function setZoom(newZoom, centerFull=null) {
    const oldCenter = { cx: viewport.cx, cy: viewport.cy };
    zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newZoom));
    viewport.w = mainC.width / zoom;
    viewport.h = mainC.height / zoom;
    if (centerFull) {
      viewport.cx = centerFull.x;
      viewport.cy = centerFull.y;
    } else {
      viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, oldCenter.cx));
      viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, oldCenter.cy));
    }
    draw();
  }

  zoomInBtn.addEventListener('click', () => setZoom(zoom * 1.4));
  zoomOutBtn.addEventListener('click', () => setZoom(zoom / 1.4));
  resetBtn.addEventListener('click', () => {
    zoom = INITIAL_ZOOM;
    viewport.cx = fullWidth/2; viewport.cy = fullHeight/2;
    viewport.w = mainC.width / zoom; viewport.h = mainC.height / zoom;
    draw();
  });

  window.addEventListener('resize', () => {
    resizeMainCanvas();
    viewport.w = mainC.width / zoom;
    viewport.h = mainC.height / zoom;
    viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, viewport.cx));
    viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, viewport.cy));
    sizeMinimap();
    draw();
  });

  // init
  resizeMainCanvas();
  sizeMinimap();
  viewport.w = mainC.width / zoom;
  viewport.h = mainC.height / zoom;
  draw();

  // keyboard nudges
  window.addEventListener('keydown', (ev) => {
    const step = Math.max(10, 0.06 * Math.min(viewport.w, viewport.h));
    if (ev.key === 'ArrowLeft') { viewport.cx = Math.max(viewport.w/2, viewport.cx - step); draw(); }
    if (ev.key === 'ArrowRight'){ viewport.cx = Math.min(fullWidth - viewport.w/2, viewport.cx + step); draw(); }
    if (ev.key === 'ArrowUp')   { viewport.cy = Math.max(viewport.h/2, viewport.cy - step); draw(); }
    if (ev.key === 'ArrowDown') { viewport.cy = Math.min(fullHeight - viewport.h/2, viewport.cy + step); draw(); }
  });

  // expose export
  window.slitherExport = () => {
    const arr = [];
    edges.forEach((v,k) => {
      const [n1,n2] = k.split('|');
      const [i1,j1] = n1.split(',').map(Number);
      const [i2,j2] = n2.split(',').map(Number);
      arr.push([i1,j1,i2,j2]);
    });
    return arr;
  };

})();
</script>
</body>
</html>
"""

html(html_code, height=800)
