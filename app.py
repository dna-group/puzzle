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
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Slitherlink Zoom + Minimap</title>
<style>
  html,body { height:100%; margin:0; font-family: Arial, sans-serif; }
  #container { position:relative; height:80vh; width:100%; background:#fafafa; overflow:hidden; }
  #mainCanvas { background: #ffffff; display:block; margin:0; }
  #minimap { position:absolute; bottom:20px; right:20px; background:#fff; border:1px solid #aaa; box-shadow:0 2px 8px rgba(0,0,0,0.15); }
  /* HUD text */
  #hud { position:absolute; left:12px; top:12px; background:rgba(255,255,255,0.8); padding:6px 8px; border-radius:6px; border:1px solid #ccc; font-size:13px; }
  .btn { padding:6px 8px; border-radius:4px; border:1px solid #888; background:#eee; cursor:pointer; display:inline-block; margin-right:6px; }
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
  <canvas id="minimap" width="300" height="230"></canvas>
</div>

<script>
/*
Client-side Slitherlink interactive canvas.
- Grid: cols x rows dots (128 x 178).
- Mini-map bottom-right shows full grid with a rectangle indicating current zoom/viewport.
- Click minimap to center zoom viewport on that region.
- Click zoomed area to toggle an edge (add or remove).
- Degree constraint: a node may have at most 2 edges connected. Add only if both endpoints currently have <2 edges.
- Lines render in both views simultaneously.
*/

(() => {
  // CONFIG
  const COLS = 128; // horizontal dots
  const ROWS = 178; // vertical dots
  const DOT_SPACING = 9; // px between adjacent dots in the full-space (mini map scales)
  const DOT_RADIUS = 1.0;
  const EDGE_HIT_RADIUS = 10; // pixels in zoom space for clicking an edge midpoint
  const MIN_ZOOM = 0.6; // smaller = more zoomed out
  const MAX_ZOOM = 6.0;
  const INITIAL_ZOOM = 3.2; // starting zoom
  const VIEWPORT_MARGIN = 40; // when centering, keep small margin

  // compute full logical size
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

  // State (client-side)
  let zoom = INITIAL_ZOOM;
  let viewport = { cx: fullWidth/2, cy: fullHeight/2, w: 800/zoom, h: 600/zoom }; // center coords in full-space
  // Adjust viewport size dynamically based on main canvas size later.

  // store edges as keys "x1,y1|x2,y2" where coords are integer grid indices
  const edges = new Map(); // key => true (present)
  // degree counts per node as 'x,y' => count
  const degree = new Map();

  // Helper functions for keys
  function nodeKey(ix, iy) { return `${ix},${iy}`; }
  function edgeKey(a,b) {
    // order canonical: smaller lexicographically first
    const ka = `${a.x},${a.y}`, kb = `${b.x},${b.y}`;
    return ka < kb ? ka + '|' + kb : kb + '|' + ka;
  }

  function addEdge(a,b) {
    const key = edgeKey(a,b);
    if (edges.has(key)) return false;
    // degree check
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

  // Convert between full-space (unscaled grid px) and viewport (what user sees in main canvas)
  function fullToScreen(fullX, fullY, canvasW, canvasH) {
    // map full-space to viewport-space then to canvas pixels
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

  // Find nearest edge (horizontal or vertical) to a given full-space point.
  // We'll compute nearest grid indices by rounding coordinates.
  function findNearestEdgeToFull(fullX, fullY) {
    // convert full coords to grid index float
    const gx = fullX / DOT_SPACING;
    const gy = fullY / DOT_SPACING;
    // candidate edges near rounded indices
    const ix = Math.round(gx);
    const iy = Math.round(gy);

    let best = { dist: Infinity, a: null, b: null };
    // search neighborhood of small radius (2)
    for (let dx=-2; dx<=2; dx++) {
      for (let dy=-2; dy<=2; dy++) {
        const nx = ix+dx, ny = iy+dy;
        // horizontal edge (nx,ny) <-> (nx+1,ny)
        if (nx >= 0 && nx+1 < COLS && ny >= 0 && ny < ROWS) {
          const ax = nx * DOT_SPACING, ay = ny * DOT_SPACING;
          const bx = (nx+1) * DOT_SPACING, by = ny * DOT_SPACING;
          const mx = 0.5*(ax+bx), my = 0.5*(ay+by);
          const d2 = (mx-fullX)*(mx-fullX) + (my-fullY)*(my-fullY);
          if (d2 < best.dist) {
            best = { dist: d2, a: {x:nx,y:ny}, b: {x:nx+1,y:ny} };
          }
        }
        // vertical edge (nx,ny) <-> (nx,ny+1)
        if (nx >= 0 && nx < COLS && ny >= 0 && ny+1 < ROWS) {
          const ax = nx * DOT_SPACING, ay = ny * DOT_SPACING;
          const bx = nx * DOT_SPACING, by = (ny+1) * DOT_SPACING;
          const mx = 0.5*(ax+bx), my = 0.5*(ay+by);
          const d2 = (mx-fullX)*(mx-fullX) + (my-fullY)*(my-fullY);
          if (d2 < best.dist) {
            best = { dist: d2, a: {x:nx,y:ny}, b: {x:nx,y:ny+1} };
          }
        }
      }
    }
    return best; // dist is squared distance in full-space pixels
  }

  // Rendering
  function resizeMainCanvas() {
    const rect = container.getBoundingClientRect();
    // Choose main canvas size to fill container
    mainC.width = Math.max(400, Math.floor(rect.width));
    mainC.height = Math.max(400, Math.floor(rect.height));
    // update viewport size in full-space based on zoom and canvas pixel size
    viewport.w = mainC.width / zoom;
    viewport.h = mainC.height / zoom;
  }

  function draw() {
    // draw main canvas (zoomed-in)
    mc.clearRect(0,0, mainC.width, mainC.height);
    mc.fillStyle = '#fff';
    mc.fillRect(0,0, mainC.width, mainC.height);

    // draw grid dots faintly
    const lowAlpha = 0.06;
    mc.fillStyle = `rgba(0,0,0,${lowAlpha})`;

    // Determine visible grid index range to only draw what's necessary
    const left = viewport.cx - viewport.w/2;
    const top  = viewport.cy - viewport.h/2;
    const right = left + viewport.w;
    const bottom = top + viewport.h;
    const minI = Math.max(0, Math.floor(left / DOT_SPACING) - 1);
    const maxI = Math.min(COLS-1, Math.ceil(right / DOT_SPACING) + 1);
    const minJ = Math.max(0, Math.floor(top  / DOT_SPACING) - 1);
    const maxJ = Math.min(ROWS-1, Math.ceil(bottom / DOT_SPACING) + 1);

    for (let j=minJ; j<=maxJ; j++) {
      for (let i=minI; i<=maxI; i++) {
        const fx = i*DOT_SPACING, fy = j*DOT_SPACING;
        const p = fullToScreen(fx, fy, mainC.width, mainC.height);
        // Skip if out of canvas bounds
        if (p.x < -2 || p.x > mainC.width+2 || p.y < -2 || p.y > mainC.height+2) continue;
        mc.beginPath();
        mc.arc(p.x, p.y, Math.max(0.6, DOT_RADIUS * zoom/2), 0, Math.PI*2);
        mc.fill();
      }
    }

    // Draw edges (present)
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

    // Optionally draw ghost nearest edge under mouse? (omitted)

    // Draw minimap
    drawMinimap();
  }

  function drawMinimap() {
    const mw = miniC.width, mh = miniC.height;
    mm.clearRect(0,0,mw,mh);
    mm.fillStyle = '#fff';
    mm.fillRect(0,0,mw,mh);

    // compute scale to fit fullWidth/fullHeight into minimap with padding
    const pad = 8;
    const availW = mw - pad*2, availH = mh - pad*2;
    const scale = Math.min(availW / fullWidth, availH / fullHeight);
    const offX = (mw - fullWidth*scale)/2;
    const offY = (mh - fullHeight*scale)/2;

    // draw faint dots as tiny pixels for performance: draw as thin grid lines every N
    // But we'll draw edges and a few grid dots
    mm.fillStyle = '#dcdcdc';
    const dotStep = 8; // only show a subset to avoid clutter
    for (let j=0; j<ROWS; j+=dotStep) {
      for (let i=0; i<COLS; i+=dotStep) {
        const x = offX + i*DOT_SPACING*scale;
        const y = offY + j*DOT_SPACING*scale;
        mm.fillRect(x-0.4, y-0.4, 0.8, 0.8);
      }
    }

    // draw edges present
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

    // draw viewport rectangle
    mm.strokeStyle = '#e85a5a';
    mm.lineWidth = 2;
    mm.setLineDash([4,3]);
    const vx = (viewport.cx - viewport.w/2) * scale + offX;
    const vy = (viewport.cy - viewport.h/2) * scale + offY;
    const vw = viewport.w * scale;
    const vh = viewport.h * scale;
    mm.strokeRect(vx, vy, vw, vh);
    mm.setLineDash([]);
  }

  // Event handlers
  function handleMainClick(ev) {
    const rect = mainC.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    const full = screenToFull(sx, sy, mainC.width, mainC.height);
    // find nearest edge
    const nearest = findNearestEdgeToFull(full.x, full.y);
    if (!nearest || nearest.dist === Infinity) return;
    // Check threshold: distance in screen pixels should be <= EDGE_HIT_RADIUS
    const midpointFullX = 0.5 * ((nearest.a.x + nearest.b.x) * DOT_SPACING);
    const midpointFullY = 0.5 * ((nearest.a.y + nearest.b.y) * DOT_SPACING);
    const screenMid = fullToScreen(midpointFullX, midpointFullY, mainC.width, mainC.height);
    const dx = screenMid.x - sx, dy = screenMid.y - sy;
    const dist = Math.sqrt(dx*dx + dy*dy);
    if (dist > EDGE_HIT_RADIUS) {
      // ignore if too far from an edge midpoint
      return;
    }
    // toggle edge
    const key = edgeKey(nearest.a, nearest.b);
    if (edges.has(key)) {
      removeEdge(nearest.a, nearest.b);
    } else {
      addEdge(nearest.a, nearest.b);
    }
    draw();
  }

  function handleMiniClick(ev) {
    const rect = miniC.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    // compute map scale & offsets same as drawMinimap
    const mw = miniC.width, mh = miniC.height;
    const pad = 8;
    const availW = mw - pad*2, availH = mh - pad*2;
    const scale = Math.min(availW / fullWidth, availH / fullHeight);
    const offX = (mw - fullWidth*scale)/2;
    const offY = (mh - fullHeight*scale)/2;
    // map click to full-space coords
    const fx = (sx - offX) / scale;
    const fy = (sy - offY) / scale;
    // clamp center so viewport stays inside
    const halfW = viewport.w/2, halfH = viewport.h/2;
    const cx = Math.max(halfW, Math.min(fullWidth - halfW, fx));
    const cy = Math.max(halfH, Math.min(fullHeight - halfH, fy));
    viewport.cx = cx; viewport.cy = cy;
    draw();
  }

  // Zoom controls
  function setZoom(newZoom, centerFull=null) {
    // Keep viewport center or set to provided center (full-space coords)
    const oldCenter = { cx: viewport.cx, cy: viewport.cy };
    zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newZoom));
    viewport.w = mainC.width / zoom;
    viewport.h = mainC.height / zoom;
    if (centerFull) {
      viewport.cx = centerFull.x;
      viewport.cy = centerFull.y;
    } else {
      // try keep same center but ensure within bounds
      viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, oldCenter.cx));
      viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, oldCenter.cy));
    }
    draw();
  }

  function recenterOnFullPoint(fullX, fullY) {
    const halfW = viewport.w/2, halfH = viewport.h/2;
    viewport.cx = Math.max(halfW, Math.min(fullWidth - halfW, fullX));
    viewport.cy = Math.max(halfH, Math.min(fullHeight - halfH, fullY));
  }

  // Resize handling
  window.addEventListener('resize', () => {
    resizeMainCanvas();
    // ensure viewport fits within full bounds
    viewport.w = mainC.width / zoom;
    viewport.h = mainC.height / zoom;
    viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, viewport.cx));
    viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, viewport.cy));
    draw();
  });

  // Simple panning by drag on main canvas
  let isPanning = false;
  let panStart = null;
  mainC.addEventListener('mousedown', (ev) => {
    if (ev.button !== 0) return;
    // allow panning by holding shift? For clarity, use right-click drag for panning
    if (ev.shiftKey) {
      isPanning = true;
      panStart = { x: ev.clientX, y: ev.clientY, cx: viewport.cx, cy: viewport.cy };
      ev.preventDefault();
    }
  });
  window.addEventListener('mousemove', (ev) => {
    if (!isPanning) return;
    const dx = ev.clientX - panStart.x;
    const dy = ev.clientY - panStart.y;
    // translate dx,dy in screen pixels to full-space
    const fx = -dx * (viewport.w / mainC.width);
    const fy = -dy * (viewport.h / mainC.height);
    viewport.cx = Math.max(viewport.w/2, Math.min(fullWidth - viewport.w/2, panStart.cx + fx));
    viewport.cy = Math.max(viewport.h/2, Math.min(fullHeight - viewport.h/2, panStart.cy + fy));
    draw();
  });
  window.addEventListener('mouseup', (ev) => {
    if (isPanning) { isPanning = false; panStart = null; }
  });

  // Touch support for main canvas taps
  mainC.addEventListener('click', (ev) => {
    // simple click toggles edge
    handleMainClick(ev);
  });

  miniC.addEventListener('click', (ev) => {
    handleMiniClick(ev);
  });

  // Buttons
  zoomInBtn.addEventListener('click', () => {
    setZoom(zoom * 1.4);
  });
  zoomOutBtn.addEventListener('click', () => {
    setZoom(zoom / 1.4);
  });
  resetBtn.addEventListener('click', () => {
    zoom = INITIAL_ZOOM;
    viewport.cx = fullWidth/2; viewport.cy = fullHeight/2;
    viewport.w = mainC.width / zoom; viewport.h = mainC.height / zoom;
    draw();
  });

  // init sizing and initial draw
  resizeMainCanvas();
  viewport.w = mainC.width / zoom;
  viewport.h = mainC.height / zoom;
  draw();

  // Keyboard: arrow keys to nudge viewport
  window.addEventListener('keydown', (ev) => {
    const step = Math.max(10, 0.06 * Math.min(viewport.w, viewport.h));
    if (ev.key === 'ArrowLeft') { viewport.cx = Math.max(viewport.w/2, viewport.cx - step); draw(); }
    if (ev.key === 'ArrowRight'){ viewport.cx = Math.min(fullWidth - viewport.w/2, viewport.cx + step); draw(); }
    if (ev.key === 'ArrowUp')   { viewport.cy = Math.max(viewport.h/2, viewport.cy - step); draw(); }
    if (ev.key === 'ArrowDown') { viewport.cy = Math.min(fullHeight - viewport.h/2, viewport.cy + step); draw(); }
  });

  // Expose a simple export to console for debugging
  window.slitherExport = () => {
    // returns arrays of edges as [[i1,j1,i2,j2],...]
    const arr = [];
    edges.forEach((v,k) => {
      const [n1,n2] = k.split('|');
      const [i1,j1] = n1.split(',').map(Number);
      const [i2,j2] = n2.split(',').map(Number);
      arr.push([i1,j1,i2,j2]);
    });
    return arr;
  };

  // Performance note: if you want persistence integrate postMessage to Streamlit backend.
})();
</script>
</body>
</html>
"""

# Embed the HTML as a component
html(html_code, height=800)
