# app.py
# Streamlit app: Slitherlink with zoomed-in editing only (no minimap)
# - Grid: 128 x 178 dots
# - Click to toggle edge (degree ≤ 2)
# - Click+drag pans the zoomed viewport
# - Dots are white on a black background
# - Lines are white and slightly thicker
#
# Usage:
#   pip install streamlit
#   streamlit run app.py

import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(layout="wide")

st.markdown("## Slitherlink — Zoomed Editing (no minimap)")

html_code = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Slitherlink — Zoom Only</title>
<style>
  html,body { height:100%; margin:0; font-family: Arial, sans-serif; background:#000; color:#fff; }
  #container { position:relative; height:80vh; width:100%; background:#000; overflow:hidden; }
  canvas { display:block; width:100%; height:100%; }
  #mainCanvas { background: #000; touch-action: none; }
  #hud { position:absolute; left:12px; top:12px; background:rgba(0,0,0,0.6); color:#fff; padding:6px 8px; border-radius:6px; border:1px solid #333; font-size:13px; z-index:5; }
  .btn { padding:6px 8px; border-radius:4px; border:1px solid #444; background:#111; color:#fff; cursor:pointer; display:inline-block; margin-right:6px; }
</style>
</head>
<body>
<div id="container">
  <div id="hud">
    <span class="btn" id="zoomInBtn">Zoom In</span>
    <span class="btn" id="zoomOutBtn">Zoom Out</span>
    <span class="btn" id="resetBtn">Reset</span>
    <span style="margin-left:8px">Click zoom area to toggle edge. Drag to pan.</span>
  </div>

  <canvas id="mainCanvas"></canvas>
</div>

<script>
(() => {
  // CONFIG
  const COLS = 128;
  const ROWS = 178;
  const DOT_SPACING = 9;       // full-space spacing (logical pixels)
  const DOT_RADIUS = 1.0;
  const EDGE_HIT_RADIUS = 10;  // screen pixels for toggle detection
  const MIN_ZOOM = 0.6;
  const MAX_ZOOM = 8.0;
  const INITIAL_ZOOM = 3.2;

  // logical full-space size (coordinates in "full pixels")
  const fullWidth = (COLS - 1) * DOT_SPACING;
  const fullHeight = (ROWS - 1) * DOT_SPACING;

  // DOM elements
  const container = document.getElementById('container');
  const mainC = document.getElementById('mainCanvas');
  const mc = mainC.getContext('2d', { alpha: false });
  const zoomInBtn = document.getElementById('zoomInBtn');
  const zoomOutBtn = document.getElementById('zoomOutBtn');
  const resetBtn = document.getElementById('resetBtn');

  // State
  let zoom = INITIAL_ZOOM;
  let viewport = { cx: fullWidth/2, cy: fullHeight/2, w: 800/zoom, h: 600/zoom };

  // edges store (canonical key "x,y|x2,y2") and degree counts
  const edges = new Map();
  const degree = new Map();

  function nodeKey(ix,iy){ return `${ix},${iy}`; }
  function edgeKey(a,b){
    const ka = `${a.x},${a.y}`, kb = `${b.x},${b.y}`;
    return ka < kb ? ka + '|' + kb : kb + '|' + ka;
  }

  function addEdge(a,b){
    const key = edgeKey(a,b);
    if (edges.has(key)) return false;
    const da = degree.get(nodeKey(a.x,a.y)) || 0;
    const db = degree.get(nodeKey(b.x,b.y)) || 0;
    if (da >= 2 || db >= 2) return false;
    edges.set(key,true);
    degree.set(nodeKey(a.x,a.y), da+1);
    degree.set(nodeKey(b.x,b.y), db+1);
    return true;
  }
  function removeEdge(a,b){
    const key = edgeKey(a,b);
    if (!edges.has(key)) return false;
    edges.delete(key);
    const ka = nodeKey(a.x,a.y), kb = nodeKey(b.x,b.y);
    degree.set(ka, (degree.get(ka)||1)-1);
    degree.set(kb, (degree.get(kb)||1)-1);
    return true;
  }

  // Convert between full-space coords and main canvas screen coords
  function fullToScreen(fullX, fullY, canvasW, canvasH){
    const left = viewport.cx - viewport.w/2;
    const top = viewport.cy - viewport.h/2;
    return {
      x: (fullX - left) / viewport.w * canvasW,
      y: (fullY - top)  / viewport.h * canvasH
    };
  }
  function screenToFull(sx, sy, canvasW, canvasH){
    const left = viewport.cx - viewport.w/2;
    const top = viewport.cy - viewport.h/2;
    return {
      x: left + (sx / canvasW) * viewport.w,
      y: top  + (sy / canvasH) * viewport.h
    };
  }

  // Find nearest canonical horizontal/vertical edge (by nearest midpoint) to a full-space point.
  function findNearestEdgeToFull(fullX, fullY){
    const gx = fullX / DOT_SPACING;
    const gy = fullY / DOT_SPACING;
    const ix = Math.round(gx), iy = Math.round(gy);
    let best = { dist: Infinity, a: null, b: null };
    for(let dx=-2; dx<=2; dx++){
      for(let dy=-2; dy<=2; dy++){
        const nx = ix+dx, ny = iy+dy;
        // horizontal
        if (nx>=0 && nx+1<COLS && ny>=0 && ny<ROWS){
          const ax = nx*DOT_SPACING, ay = ny*DOT_SPACING;
          const bx = (nx+1)*DOT_SPACING, by = ny*DOT_SPACING;
          const mx = 0.5*(ax+bx), my = 0.5*(ay+by);
          const d2 = (mx-fullX)*(mx-fullX) + (my-fullY)*(my-fullY);
          if (d2 < best.dist) best = { dist:d2, a:{x:nx,y:ny}, b:{x:nx+1,y:ny} };
        }
        // vertical
        if (nx>=0 && nx<COLS && ny>=0 && ny+1<ROWS){
          const ax = nx*DOT_SPACING, ay = ny*DOT_SPACING;
          const bx = nx*DOT_SPACING, by = (ny+1)*DOT_SPACING;
          const mx = 0.5*(ax+bx), my = 0.5*(ay+by);
          const d2 = (mx-fullX)*(mx-fullX) + (my-fullY)*(my-fullY);
          if (d2 < best.dist) best = { dist:d2, a:{x:nx,y:ny}, b:{x:nx,y:ny+1} };
        }
      }
    }
    return best;
  }

  // Main canvas sizing
  function resizeMainCanvas(){
    const rect = container.getBoundingClientRect();
    mainC.width = Math.max(420, Math.floor(rect.width));
    mainC.height = Math.max(420, Math.floor(rect.height));
    // update viewport to reflect canvas size & current zoom
    viewport.w = mainC.width / zoom;
    viewport.h = mainC.height / zoom;
    // clamp center inside full-space
    viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, viewport.cx));
    viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, viewport.cy));
  }

  // Drawing functions
  function draw(){
    // draw main (zoomed) canvas: black background, white dots, white edges
    mc.clearRect(0,0, mainC.width, mainC.height);
    mc.fillStyle = '#000'; mc.fillRect(0,0, mainC.width, mainC.height);

    // visible grid bounds
    const left = viewport.cx - viewport.w/2;
    const top = viewport.cy - viewport.h/2;
    const right = left + viewport.w;
    const bottom = top + viewport.h;
    const minI = Math.max(0, Math.floor(left / DOT_SPACING) - 1);
    const maxI = Math.min(COLS-1, Math.ceil(right / DOT_SPACING) + 1);
    const minJ = Math.max(0, Math.floor(top  / DOT_SPACING) - 1);
    const maxJ = Math.min(ROWS-1, Math.ceil(bottom / DOT_SPACING) + 1);

    mc.fillStyle = '#fff';
    const rad = Math.max(0.6, DOT_RADIUS * zoom/2);
    for (let j=minJ; j<=maxJ; j++){
      for (let i=minI; i<=maxI; i++){
        const p = fullToScreen(i*DOT_SPACING, j*DOT_SPACING, mainC.width, mainC.height);
        if (p.x < -4 || p.x > mainC.width+4 || p.y < -4 || p.y > mainC.height+4) continue;
        mc.beginPath();
        mc.arc(p.x, p.y, rad, 0, Math.PI*2);
        mc.fill();
      }
    }

    // draw edges on main canvas: white and slightly thicker
    // thickness scales with zoom but is clamped
    mc.lineWidth = Math.max(2, Math.min(6, zoom * 1.2));
    mc.strokeStyle = '#fff';
    mc.lineCap = 'round';
    mc.beginPath();
    edges.forEach((v,k) => {
      const [n1,n2] = k.split('|');
      const [i1,j1] = n1.split(',').map(Number);
      const [i2,j2] = n2.split(',').map(Number);
      const p1 = fullToScreen(i1*DOT_SPACING, j1*DOT_SPACING, mainC.width, mainC.height);
      const p2 = fullToScreen(i2*DOT_SPACING, j2*DOT_SPACING, mainC.width, mainC.height);
      mc.moveTo(p1.x, p1.y);
      mc.lineTo(p2.x, p2.y);
    });
    mc.stroke();
  }

  // Interaction: click on main toggles nearest edge (within threshold)
  // click+drag on main pans viewport
  let isPointerDown = false;
  let pointerStart = null;
  let isDragging = false;
  const DRAG_THRESHOLD = 6;

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
    if (!isDragging && Math.hypot(dx,dy) > DRAG_THRESHOLD) isDragging = true;
    if (isDragging){
      // translate screen delta to full-space pan
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
    const dx = ev.clientX - pointerStart.x;
    const dy = ev.clientY - pointerStart.y;
    if (!isDragging && Math.hypot(dx,dy) <= DRAG_THRESHOLD) {
      // treat as click -> toggle nearest edge
      handleMainClick(ev);
    }
    pointerStart = null;
    isDragging = false;
  });

  function handleMainClick(ev){
    const rect = mainC.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    const full = screenToFull(sx, sy, mainC.width, mainC.height);
    const nearest = findNearestEdgeToFull(full.x, full.y);
    if (!nearest || nearest.dist === Infinity) return;
    // compute screen distance to midpoint
    const midFullX = 0.5 * ((nearest.a.x + nearest.b.x) * DOT_SPACING);
    const midFullY = 0.5 * ((nearest.a.y + nearest.b.y) * DOT_SPACING);
    const screenMid = fullToScreen(midFullX, midFullY, mainC.width, mainC.height);
    const ddx = screenMid.x - sx, ddy = screenMid.y - sy;
    const dist = Math.sqrt(ddx*ddx + ddy*ddy);
    if (dist > EDGE_HIT_RADIUS) return;
    const key = edgeKey(nearest.a, nearest.b);
    if (edges.has(key)) removeEdge(nearest.a, nearest.b);
    else addEdge(nearest.a, nearest.b);
    draw();
  }

  // Zoom controls (keep viewport centre when zooming)
  function setZoom(newZoom){
    const oldCenter = { cx: viewport.cx, cy: viewport.cy };
    zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newZoom));
    viewport.w = mainC.width / zoom;
    viewport.h = mainC.height / zoom;
    viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, oldCenter.cx));
    viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, oldCenter.cy));
    draw();
  }
  zoomInBtn.addEventListener('click', ()=> setZoom(zoom * 1.4));
  zoomOutBtn.addEventListener('click', ()=> setZoom(zoom / 1.4));
  resetBtn.addEventListener('click', ()=> {
    zoom = INITIAL_ZOOM;
    viewport.cx = fullWidth/2; viewport.cy = fullHeight/2;
    viewport.w = mainC.width / zoom; viewport.h = mainC.height / zoom;
    draw();
  });

  // Resize handling
  window.addEventListener('resize', ()=> {
    resizeMainCanvas();
    viewport.w = mainC.width / zoom;
    viewport.h = mainC.height / zoom;
    viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, viewport.cx));
    viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, viewport.cy));
    draw();
  });

  // init
  resizeMainCanvas();
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

  // expose simple export for debugging
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

html(html_code, height=820)
