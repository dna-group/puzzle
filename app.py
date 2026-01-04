# app.py
# Streamlit + embedded client-side Slitherlink UI with state saved/restored in the URL fragment.
# - Grid: 128 x 178
# - Minimal UI (no buttons)
# - Top-left of puzzle aligned to top-left of canvas on start
# - Puzzle state (edges + viewport) encoded into the URL fragment (#state=...)
#   -> use "Save / bookmark" by copying the page URL after interacting
#   -> page will restore puzzle from that URL
#
# Usage:
#   pip install streamlit
#   streamlit run app.py

import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(layout="wide")
html_code = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Slitherlink</title>
<style>
  html,body {
    height:100%;
    margin:0;
    background:#ddd;   /* page background to highlight puzzle border */
  }
  #container {
    position:relative;
    height:100vh;
    width:100vw;
    background:#ddd;
    overflow:hidden;
  }
  canvas {
    display:block;
    background:#fff;   /* puzzle background */
    touch-action:none;
  }
</style>
</head>
<body>
<div id="container">
  <canvas id="mainCanvas"></canvas>
</div>

<script>
(() => {
  // CONFIG / GRID
  const COLS = 128;
  const ROWS = 178;
  const DOT_SPACING = 9;
  const DOT_RADIUS = 1.0;
  const EDGE_HIT_RADIUS = 10;
  const INITIAL_ZOOM = 3.2;
  const BORDER = DOT_SPACING * 2; // margin so edges do not clip

  const gridWidth  = (COLS - 1) * DOT_SPACING;
  const gridHeight = (ROWS - 1) * DOT_SPACING;
  const fullWidth  = gridWidth  + BORDER * 2;
  const fullHeight = gridHeight + BORDER * 2;

  // DOM
  const container = document.getElementById("container");
  const canvas = document.getElementById("mainCanvas");
  const ctx = canvas.getContext("2d", { alpha:false });

  // State
  let zoom = INITIAL_ZOOM;
  // Start with top-left of puzzle aligned to the top-left of the canvas:
  let viewport = { cx: null, cy: null, w: null, h: null };

  // edges: Map keyed "i1,j1|i2,j2"
  const edges = new Map();
  const degree = new Map();

  const nodeKey = (x,y) => `${x},${y}`;
  const edgeKey = (a,b) => {
    const ka = nodeKey(a.x,a.y), kb = nodeKey(b.x,b.y);
    return ka < kb ? ka + '|' + kb : kb + '|' + ka;
  };

  function addEdge(a,b){
    const k = edgeKey(a,b);
    if (edges.has(k)) return false;
    const da = degree.get(nodeKey(a.x,a.y))||0;
    const db = degree.get(nodeKey(b.x,b.y))||0;
    if (da >= 2 || db >= 2) return false;
    edges.set(k,true);
    degree.set(nodeKey(a.x,a.y), da+1);
    degree.set(nodeKey(b.x,b.y), db+1);
    scheduleSaveState(); // persist change to URL
    return true;
  }
  function removeEdge(a,b){
    const k = edgeKey(a,b);
    if (!edges.has(k)) return false;
    edges.delete(k);
    degree.set(nodeKey(a.x,a.y), (degree.get(nodeKey(a.x,a.y))||1)-1);
    degree.set(nodeKey(b.x,b.y), (degree.get(nodeKey(b.x,b.y))||1)-1);
    scheduleSaveState(); // persist change to URL
    return true;
  }

  function fullToScreen(x,y){
    const l = viewport.cx - viewport.w/2;
    const t = viewport.cy - viewport.h/2;
    return {
      x: (x - l) / viewport.w * canvas.width,
      y: (y - t) / viewport.h * canvas.height
    };
  }
  function screenToFull(sx, sy){
    const l = viewport.cx - viewport.w/2;
    const t = viewport.cy - viewport.h/2;
    return {
      x: l + sx / canvas.width * viewport.w,
      y: t + sy / canvas.height * viewport.h
    };
  }

  function resizeCanvas(){
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    // viewport size depends on zoom & canvas size
    viewport.w = canvas.width / zoom;
    viewport.h = canvas.height / zoom;
    // keep top-left aligned at start if cx/cy null
    if (viewport.cx === null) viewport.cx = viewport.w/2;
    if (viewport.cy === null) viewport.cy = viewport.h/2;
  }

  function draw(){
    // background white
    ctx.fillStyle = "#fff";
    ctx.fillRect(0,0,canvas.width,canvas.height);

    // dots (black)
    ctx.fillStyle = "#000";
    const r = Math.max(0.6, DOT_RADIUS * zoom/2);

    // determine visible grid region to draw fewer dots
    const left = viewport.cx - viewport.w/2;
    const top  = viewport.cy - viewport.h/2;
    const right = left + viewport.w;
    const bottom = top + viewport.h;
    const minI = Math.max(0, Math.floor((left - BORDER) / DOT_SPACING) - 1);
    const maxI = Math.min(COLS-1, Math.ceil((right - BORDER) / DOT_SPACING) + 1);
    const minJ = Math.max(0, Math.floor((top - BORDER) / DOT_SPACING) - 1);
    const maxJ = Math.min(ROWS-1, Math.ceil((bottom - BORDER) / DOT_SPACING) + 1);

    for (let j = minJ; j <= maxJ; j++){
      for (let i = minI; i <= maxI; i++){
        const fx = BORDER + i * DOT_SPACING;
        const fy = BORDER + j * DOT_SPACING;
        const p = fullToScreen(fx, fy);
        if (p.x < -4 || p.x > canvas.width + 4 || p.y < -4 || p.y > canvas.height + 4) continue;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI*2);
        ctx.fill();
      }
    }

    // edges (grey, slightly thicker)
    ctx.strokeStyle = "#888";
    ctx.lineWidth = Math.max(3, zoom * 1.1);
    ctx.lineCap = "round";
    ctx.beginPath();
    edges.forEach((_, k) => {
      const [a,b] = k.split("|").map(s => s.split(",").map(Number));
      const p1 = fullToScreen(BORDER + a[0]*DOT_SPACING, BORDER + a[1]*DOT_SPACING);
      const p2 = fullToScreen(BORDER + b[0]*DOT_SPACING, BORDER + b[1]*DOT_SPACING);
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
    });
    ctx.stroke();
  }

  // Utilities: serialize/deserialize puzzle state to/from compact base64-friendly string
  function encodeStateToString(stateObj){
    // Use URI-safe base64-ish encoding via btoa(encodeURIComponent(JSON))
    try {
      const json = JSON.stringify(stateObj);
      // btoa needs binary-safe string; encode as UTF-8 surrogate handling
      const base = btoa(unescape(encodeURIComponent(json)));
      return base.replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,''); // URL-safe
    } catch(e){
      return "";
    }
  }
  function decodeStateFromString(s){
    try {
      // restore padding
      s = s.replace(/-/g,'+').replace(/_/g,'/');
      const pad = s.length % 4;
      if (pad) s += '='.repeat(4 - pad);
      const json = decodeURIComponent(escape(atob(s)));
      return JSON.parse(json);
    } catch(e){
      return null;
    }
  }

  // Read state from URL (fragment first, then query param), return object or null
  function loadStateFromURL(){
    const hash = window.location.hash || "";
    if (hash.startsWith("#state=")){
      const payload = hash.slice(7);
      return decodeStateFromString(payload);
    }
    // also support ?state=... (optional)
    const q = new URLSearchParams(window.location.search);
    if (q.has("state")){
      return decodeStateFromString(q.get("state"));
    }
    return null;
  }

  // Apply state (edges array and optional viewport)
  function applyState(obj){
    if (!obj) return;
    // clear existing
    edges.clear();
    degree.clear();
    if (Array.isArray(obj.edges)){
      for (const e of obj.edges){
        // e is [i1,j1,i2,j2]
        if (!Array.isArray(e) || e.length < 4) continue;
        const a = { x: e[0], y: e[1] }, b = { x: e[2], y: e[3] };
        const k = edgeKey(a,b);
        edges.set(k,true);
        degree.set(nodeKey(a.x,a.y), (degree.get(nodeKey(a.x,a.y))||0)+1);
        degree.set(nodeKey(b.x,b.y), (degree.get(nodeKey(b.x,b.y))||0)+1);
      }
    }
    // viewport: we allow optional cx,cy,zoom. If provided, restore; otherwise keep current.
    if (obj.viewport && typeof obj.viewport === "object"){
      if (typeof obj.viewport.zoom === "number" && obj.viewport.zoom > 0){
        zoom = obj.viewport.zoom;
      }
      if (typeof obj.viewport.cx === "number") viewport.cx = obj.viewport.cx;
      if (typeof obj.viewport.cy === "number") viewport.cy = obj.viewport.cy;
      // recompute viewport sizes based on current canvas + zoom
      viewport.w = canvas.width / zoom;
      viewport.h = canvas.height / zoom;
      // clamp
      viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, viewport.cx));
      viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, viewport.cy));
    }
  }

  // Save state into URL fragment (debounced)
  let saveTimer = null;
  function scheduleSaveState(delay = 500){
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      saveTimer = null;
      saveStateToURL();
    }, delay);
  }
  function saveStateToURL(){
    const edgesArr = [];
    edges.forEach((_, k) => {
      const [a,b] = k.split("|");
      const aa = a.split(",").map(Number), bb = b.split(",").map(Number);
      edgesArr.push([aa[0], aa[1], bb[0], bb[1]]);
    });
    const stateObj = {
      edges: edgesArr,
      viewport: { cx: viewport.cx, cy: viewport.cy, zoom: zoom }
    };
    const token = encodeStateToString(stateObj);
    if (!token) return;
    const newHash = "#state=" + token;
    // replace fragment without adding history entry
    history.replaceState(null, "", window.location.pathname + window.location.search + newHash);
  }

  // Try to restore on load
  function tryRestoreFromURL(){
    const obj = loadStateFromURL();
    if (!obj) return false;
    applyState(obj);
    return true;
  }

  // Interaction: click toggles nearest edge if within threshold; pointer drag pans
  function findNearestEdgeToFull(fullX, fullY){
    // search local neighborhood for nearest horizontal/vertical midpoint
    const gx = (fullX - BORDER) / DOT_SPACING;
    const gy = (fullY - BORDER) / DOT_SPACING;
    const ix = Math.round(gx), iy = Math.round(gy);
    let best = { dist: Infinity, a: null, b: null };
    for (let dx=-2; dx<=2; dx++){
      for (let dy=-2; dy<=2; dy++){
        const nx = ix+dx, ny = iy+dy;
        if (nx >= 0 && nx+1 < COLS && ny >=0 && ny < ROWS){
          const ax = BORDER + nx*DOT_SPACING, ay = BORDER + ny*DOT_SPACING;
          const bx = BORDER + (nx+1)*DOT_SPACING, by = BORDER + ny*DOT_SPACING;
          const mx = 0.5*(ax+bx), my = 0.5*(ay+by);
          const d2 = (mx-fullX)*(mx-fullX) + (my-fullY)*(my-fullY);
          if (d2 < best.dist){ best = { dist:d2, a:{x:nx,y:ny}, b:{x:nx+1,y:ny} }; }
        }
        if (nx >= 0 && nx < COLS && ny >=0 && ny+1 < ROWS){
          const ax = BORDER + nx*DOT_SPACING, ay = BORDER + ny*DOT_SPACING;
          const bx = BORDER + nx*DOT_SPACING, by = BORDER + (ny+1)*DOT_SPACING;
          const mx = 0.5*(ax+bx), my = 0.5*(ay+by);
          const d2 = (mx-fullX)*(mx-fullX) + (my-fullY)*(my-fullY);
          if (d2 < best.dist){ best = { dist:d2, a:{x:nx,y:ny}, b:{x:nx,y:ny+1} }; }
        }
      }
    }
    return best;
  }

  // Pointer logic
  let isPointerDown = false;
  let pointerStart = null;
  let isDragging = false;
  const DRAG_THRESHOLD = 6;

  canvas.addEventListener('pointerdown', (ev) => {
    canvas.setPointerCapture(ev.pointerId);
    isPointerDown = true;
    isDragging = false;
    pointerStart = { x: ev.clientX, y: ev.clientY, cx: viewport.cx, cy: viewport.cy };
  });

  window.addEventListener('pointermove', (ev) => {
    if (!isPointerDown || !pointerStart) return;
    const dx = ev.clientX - pointerStart.x;
    const dy = ev.clientY - pointerStart.y;
    if (!isDragging && Math.hypot(dx,dy) > DRAG_THRESHOLD) isDragging = true;
    if (isDragging){
      // pan viewport (screen -> full-space)
      const fx = -dx * (viewport.w / canvas.width);
      const fy = -dy * (viewport.h / canvas.height);
      viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, pointerStart.cx + fx));
      viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, pointerStart.cy + fy));
      draw();
      scheduleSaveState(300); // saving while panning but debounced
    }
  });

  canvas.addEventListener('pointerup', (ev) => {
    canvas.releasePointerCapture(ev.pointerId);
    if (!isPointerDown) return;
    isPointerDown = false;
    const dx = ev.clientX - pointerStart.x;
    const dy = ev.clientY - pointerStart.y;
    if (!isDragging && Math.hypot(dx,dy) <= DRAG_THRESHOLD){
      // treat as click -> toggle edge
      const rect = canvas.getBoundingClientRect();
      const sx = ev.clientX - rect.left;
      const sy = ev.clientY - rect.top;
      const full = screenToFull(sx, sy);
      const nearest = findNearestEdgeToFull(full.x, full.y);
      if (nearest && nearest.dist !== Infinity){
        const distScreen = Math.sqrt(nearest.dist) * (viewport.w / canvas.width); // approximate mapping
        // Use EDGE_HIT_RADIUS in screen pixels for click tolerance:
        if (distScreen <= EDGE_HIT_RADIUS){
          const k = edgeKey(nearest.a, nearest.b);
          if (edges.has(k)) { removeEdge(nearest.a, nearest.b); }
          else { addEdge(nearest.a, nearest.b); }
          draw();
          scheduleSaveState();
        }
      }
    }
    pointerStart = null;
    isDragging = false;
  });

  // Load state from URL if present, else default: align top-left
  function initialize(){
    resizeCanvas();
    // default top-left: ensure viewport cx,cy put top-left at puzzle origin
    viewport.w = canvas.width / zoom;
    viewport.h = canvas.height / zoom;
    // top-left of puzzle (full-space) is at coordinate (0,0) + puzzle border offset BORDER,
    // so set viewport so left/top = 0 + BORDER
    viewport.cx = viewport.w/2; // left = viewport.cx - viewport.w/2 -> should equal 0 + BORDER
    viewport.cy = viewport.h/2;
    // Attempt to restore
    const restored = tryRestoreFromURL();
    if (!restored) {
      // nothing in URL: keep top-left alignment
      // but clamp to full extents
      viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, viewport.cx));
      viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, viewport.cy));
    }
    draw();
  }

  // Window resize handling
  window.addEventListener('resize', () => {
    resizeCanvas();
    // after resize keep the same top-left alignment relative to puzzle if user hasn't moved;
    // otherwise keep viewport center as-is but ensure within bounds.
    viewport.w = canvas.width / zoom;
    viewport.h = canvas.height / zoom;
    viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, viewport.cx || viewport.w/2));
    viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, viewport.cy || viewport.h/2));
    draw();
  });

  // Keyboard helpers (zoom/pan)
  window.addEventListener('keydown', (ev) => {
    const step = Math.max(10, 0.06 * Math.min(viewport.w, viewport.h));
    if (ev.key === 'ArrowLeft') { viewport.cx = Math.max(viewport.w/2, viewport.cx - step); draw(); scheduleSaveState(); }
    if (ev.key === 'ArrowRight'){ viewport.cx = Math.min(fullWidth - viewport.w/2, viewport.cx + step); draw(); scheduleSaveState(); }
    if (ev.key === 'ArrowUp')   { viewport.cy = Math.max(viewport.h/2, viewport.cy - step); draw(); scheduleSaveState(); }
    if (ev.key === 'ArrowDown') { viewport.cy = Math.min(fullHeight - viewport.h/2, viewport.cy + step); draw(); scheduleSaveState(); }
    if (ev.key === '+' || ev.key === '=') { zoom = Math.min(8, zoom * 1.2); viewport.w = canvas.width/zoom; viewport.h = canvas.height/zoom; draw(); scheduleSaveState(); }
    if (ev.key === '-' || ev.key === '_') { zoom = Math.max(0.6, zoom / 1.2); viewport.w = canvas.width/zoom; viewport.h = canvas.height/zoom; draw(); scheduleSaveState(); }
  });

  // initialize and draw
  initialize();

  // Expose simple API for debugging from browser console:
  window.slither = {
    exportState: () => {
      const arr = [];
      edges.forEach((_, k) => {
        const [a,b] = k.split("|");
        const aa = a.split(",").map(Number), bb = b.split(",").map(Number);
        arr.push([aa[0], aa[1], bb[0], bb[1]]);
      });
      return { edges: arr, viewport: { cx: viewport.cx, cy: viewport.cy, zoom: zoom } };
    },
    importState: (obj) => { applyState(obj); draw(); scheduleSaveState(); }
  };

})();
</script>
</body>
</html>
"""

html(html_code, height=900)
