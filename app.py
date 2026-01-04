# app.py
import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink Canvas", layout="wide")

# Board parameters
DOTS_X = 200  # number of dots horizontally (200)
DOTS_Y = 200  # number of dots vertically (200)
ROWS = DOTS_Y - 1
COLS = DOTS_X - 1
CELL_PX = 16   # base cell size in world units
IFRAME_HEIGHT = 1200

HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=4.0"/>
<style>
  html,body{margin:0;padding:0;height:100%;background:#fff;overflow:hidden}
  #root{width:100%;height:100vh;display:flex;align-items:stretch;justify-content:stretch}
  canvas{display:block; width:100%; height:100%;}
  /* disable selection/dragging */
  body,canvas { -webkit-user-select: none; -ms-user-select: none; user-select: none; -webkit-touch-callout: none; }
</style>
</head>
<body>
<div id="root"><canvas id="board"></canvas></div>

<script>
(function(){
  // ---------- CONFIG ----------
  const ROWS = __ROWS__;
  const COLS = __COLS__;
  const CELL = __CELL__;   // world units (logical)
  const MARGIN = 6;       // world margin
  // ---------- STATE ----------
  const canvas = document.getElementById('board');
  const ctx = canvas.getContext('2d', { alpha: false });
  // edges stored as "r,c,d" where d in {'h','v'}
  const filled = new Set();

  // transform state (world -> screen): scale, translate
  let scale = 1.0;
  let tx = 0, ty = 0; // screen translation in pixels
  // We'll work in "world" coordinates (same units as CELL), but map to canvas pixels with scale and DPR.
  const dpr = Math.max(1, window.devicePixelRatio || 1);

  // derived sizes
  const viewW = COLS * CELL + MARGIN * 2;
  const viewH = ROWS * CELL + MARGIN * 2;

  // pointer / drag state
  let active = false;
  let mode = null; // 'add'|'remove'
  let anchorEdge = null; // string key
  let anchorClient = null; // {x,y} in client pixels
  let anchorWorld = null; // {x,y} in world coords
  let axis = null; // 'h'|'v' current dominant axis
  let appliedSteps = 0;
  let lastMoveEvent = null;
  let raf = null;
  const MOVE_THRESHOLD = 4; // client pixels

  // pinch state
  let lastPinchDist = null;
  let lastPinchCenter = null;

  // helpers: edge key / parse
  const edgeKey = (r,c,d) => `${r},${c},${d}`;
  function parseKey(k){ const p = k.split(','); return {r: +p[0], c: +p[1], d: p[2]}; }

  // vertex/degree helpers (work on the Set)
  function endpointsOf(key){
    const p = parseKey(key);
    if(p.d === 'h') return [{r:p.r, c:p.c}, {r:p.r, c:p.c+1}];
    return [{r:p.r, c:p.c}, {r:p.r+1, c:p.c}];
  }
  function vertexDegree(v){
    let deg = 0;
    if(v.c-1 >= 0 && filled.has(edgeKey(v.r, v.c-1, 'h'))) deg++;
    if(v.c <= COLS-1 && filled.has(edgeKey(v.r, v.c, 'h'))) deg++;
    if(v.r-1 >= 0 && filled.has(edgeKey(v.r-1, v.c, 'v'))) deg++;
    if(v.r <= ROWS-1 && filled.has(edgeKey(v.r, v.c, 'v'))) deg++;
    return deg;
  }
  function wouldExceedIfAdd(key){
    if(filled.has(key)) return false;
    for(const v of endpointsOf(key)) if(vertexDegree(v) >= 2) return true;
    return false;
  }

  // coordinate transforms: client <-> world
  function clientToCanvas(clientX, clientY){
    const rect = canvas.getBoundingClientRect();
    return { x: (clientX - rect.left) * dpr, y: (clientY - rect.top) * dpr, rect };
  }
  function clientToWorld(clientX, clientY){
    const c = clientToCanvas(clientX, clientY);
    // canvas pixels -> world units
    const sx = (c.x - tx) / (scale * dpr);
    const sy = (c.y - ty) / (scale * dpr);
    return { x: sx, y: sy };
  }
  function worldToCanvasWX(wx, wy){
    const cx = (wx * scale * dpr) + tx;
    const cy = (wy * scale * dpr) + ty;
    return { x: cx, y: cy };
  }

  // nearest edge to a world point (same logic as SVG versions)
  function nearestEdgeToWorld(wx, wy){
    // horizontal candidate
    const r_h = Math.round((wy - MARGIN) / CELL);
    const c_h = Math.floor((wx - MARGIN) / CELL);
    let dist_h = Infinity, key_h = null;
    if(r_h >= 0 && r_h <= ROWS && c_h >= 0 && c_h < COLS){
      const hx = MARGIN + (c_h + 0.5) * CELL;
      const hy = MARGIN + r_h * CELL;
      dist_h = Math.hypot(wx - hx, wy - hy);
      key_h = edgeKey(r_h, c_h, 'h');
    }
    // vertical
    const c_v = Math.round((wx - MARGIN) / CELL);
    const r_v = Math.floor((wy - MARGIN) / CELL);
    let dist_v = Infinity, key_v = null;
    if(c_v >= 0 && c_v <= COLS && r_v >= 0 && r_v < ROWS){
      const vx = MARGIN + c_v * CELL;
      const vy = MARGIN + (r_v + 0.5) * CELL;
      dist_v = Math.hypot(wx - vx, wy - vy);
      key_v = edgeKey(r_v, c_v, 'v');
    }
    return (dist_h <= dist_v) ? key_h : key_v;
  }

  // rendering (draw full board each frame)
  function resizeCanvas(){
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    // keep scale/tx/ty when resizing; no further action needed
    draw();
  }

  function clearCanvas(){
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0,0,canvas.width,canvas.height);
  }

  function draw(){
    clearCanvas();
    ctx.save();
    // world->canvas: scale and translate already in tx/ty
    ctx.translate(tx, ty);
    ctx.scale(scale * dpr, scale * dpr);

    // draw dots
    const dotR = 0.12 * Math.max(1, CELL / 16); // small world radius
    ctx.fillStyle = '#000';
    for(let r=0;r<=ROWS;r++){
      const wy = MARGIN + r*CELL;
      for(let c=0;c<=COLS;c++){
        const wx = MARGIN + c*CELL;
        ctx.beginPath();
        ctx.arc(wx, wy, dotR, 0, Math.PI*2);
        ctx.fill();
      }
    }

    // draw filled edges
    ctx.lineCap = 'round';
    ctx.lineWidth = Math.max(2, 0.18 * CELL);
    ctx.strokeStyle = '#000';
    // iterate filled set; it's efficient even for many edges on canvas
    filled.forEach(k=>{
      const p = parseKey(k);
      if(p.d === 'h'){
        const x1 = MARGIN + p.c * CELL, y = MARGIN + p.r * CELL;
        const x2 = x1 + CELL;
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();
      } else {
        const x = MARGIN + p.c * CELL, y1 = MARGIN + p.r * CELL;
        const y2 = y1 + CELL;
        ctx.beginPath();
        ctx.moveTo(x, y1);
        ctx.lineTo(x, y2);
        ctx.stroke();
      }
    });

    ctx.restore();
  }

  // flash feedback for blocked adds (draw red line quickly on top)
  function flashBlocked(key){
    const p = parseKey(key);
    ctx.save();
    ctx.translate(tx, ty);
    ctx.scale(scale * dpr, scale * dpr);
    ctx.strokeStyle = '#d00';
    ctx.lineWidth = Math.max(2, 0.18 * CELL);
    ctx.lineCap = 'round';
    if(p.d === 'h'){
      const x1 = MARGIN + p.c * CELL, y = MARGIN + p.r * CELL;
      ctx.beginPath(); ctx.moveTo(x1,y); ctx.lineTo(x1 + CELL, y); ctx.stroke();
    } else {
      const x = MARGIN + p.c * CELL, y1 = MARGIN + p.r * CELL;
      ctx.beginPath(); ctx.moveTo(x,y1); ctx.lineTo(x, y1 + CELL); ctx.stroke();
    }
    ctx.restore();
    // redraw after small delay to remove red flash
    setTimeout(draw, 180);
  }

  // PROCESS MOVES (throttled by rAF)
  function scheduleMoveProcessing(ev){
    lastMoveEvent = ev;
    if(!raf) raf = requestAnimationFrame(processMove);
  }

  function processMove(){
    raf = null;
    const ev = lastMoveEvent;
    if(!active || !anchorClient || !anchorWorld) return;
    // compute movement in client pixels relative to anchorClient
    const dxClient = ev.clientX - anchorClient.x;
    const dyClient = ev.clientY - anchorClient.y;
    const distClient = Math.hypot(dxClient, dyClient);
    if(distClient < MOVE_THRESHOLD) return;
    // determine dominant axis based on current move vector
    const currentAxis = Math.abs(dxClient) >= Math.abs(dyClient) ? 'h' : 'v';
    if(axis !== currentAxis){
      // switch axis: re-anchor to current pointer
      anchorClient = {x: ev.clientX, y: ev.clientY};
      anchorWorld = clientToWorld(ev.clientX, ev.clientY);
      anchorEdge = nearestEdgeToWorld(anchorWorld.x, anchorWorld.y);
      axis = currentAxis;
      appliedSteps = 0;
      mode = filled.has(anchorEdge) ? 'remove' : 'add';
      // do not perform step on axis-change frame; wait for movement from new anchor
      return;
    }
    // compute movement along axis in world units
    const rect = canvas.getBoundingClientRect();
    const unitX = viewBoxW / rect.width;
    const unitY = viewBoxH / rect.height;
    let movedUnits = (axis === 'h') ? dxClient * unitX : dyClient * unitY;
    const sign = movedUnits >= 0 ? 1 : -1;
    const stepsNow = Math.floor(Math.abs(movedUnits) / CELL);
    if(stepsNow <= appliedSteps) return;
    const newSteps = stepsNow - appliedSteps;

    const base = parseKey(anchorEdge);
    // choose anchor view (world coords) used when changing orientation mapping
    const anchorV = anchorWorld;

    for(let s=1; s<=newSteps; s++){
      let keyToAct = null;
      const stepIndex = appliedSteps + s;
      if(base.d === axis){
        if(axis === 'h'){
          const nc = base.c + sign * stepIndex;
          if(nc < 0 || nc >= COLS) break;
          keyToAct = edgeKey(base.r, nc, 'h');
        } else {
          const nr = base.r + sign * stepIndex;
          if(nr < 0 || nr >= ROWS) break;
          keyToAct = edgeKey(nr, base.c, 'v');
        }
      } else {
        if(base.d === 'h' && axis === 'v'){
          // choose column base.c or base.c+1 using anchorWorld.x
          const midX = MARGIN + (base.c + 0.5) * CELL;
          const col = (anchorV.x <= midX) ? base.c : base.c + 1;
          const nr = base.r + sign * stepIndex;
          if(nr < 0 || nr >= ROWS || col < 0 || col > COLS) break;
          keyToAct = edgeKey(nr, col, 'v');
        } else if(base.d === 'v' && axis === 'h'){
          const midY = MARGIN + (base.r + 0.5) * CELL;
          const row = (anchorV.y <= midY) ? base.r : base.r + 1;
          const nc = base.c + sign * stepIndex;
          if(nc < 0 || nc >= COLS || row < 0 || row > ROWS) break;
          keyToAct = edgeKey(row, nc, 'h');
        }
      }

      if(!keyToAct) continue;
      if(mode === 'add'){
        if(!filled.has(keyToAct)){
          if(!wouldExceedIfAdd(keyToAct)){
            filled.add(keyToAct);
          } else {
            flashBlocked(keyToAct);
          }
        }
      } else {
        if(filled.has(keyToAct)){
          filled.delete(keyToAct);
        }
      }
    }

    appliedSteps = stepsNow;
    draw();
  }

  // pointer handlers (mouse / touch unified)
  function onPointerDown(ev){
    ev.preventDefault();
    active = true;
    // single-touch pan/zoom handled elsewhere for pinch; for pointerdown, set captures
    try{ ev.target.setPointerCapture(ev.pointerId); } catch(e){}
    anchorClient = { x: ev.clientX, y: ev.clientY };
    anchorWorld = clientToWorld(ev.clientX, ev.clientY);
    anchorEdge = nearestEdgeToWorld(anchorWorld.x, anchorWorld.y);
    mode = filled.has(anchorEdge) ? 'remove' : 'add';
    // immediate attempt
    if(mode === 'add'){
      if(!wouldExceedIfAdd(anchorEdge)){
        filled.add(anchorEdge);
      } else {
        flashBlocked(anchorEdge);
      }
    } else {
      filled.delete(anchorEdge);
    }
    axis = null;
    appliedSteps = 0;
    draw();
  }

  function onPointerUp(ev){
    try{ ev.target.releasePointerCapture(ev.pointerId);} catch(e){}
    active = false;
    anchorClient = null; anchorWorld = null; anchorEdge = null;
    axis = null; appliedSteps = 0;
    if(raf){ cancelAnimationFrame(raf); raf = null; lastMoveEvent = null; }
  }

  function onPointerMove(ev){
    if(!active) return;
    lastMoveEvent = ev;
    if(!raf) raf = requestAnimationFrame(processMove);
  }

  // double-tap zoom and pinch-to-zoom + two-finger pan
  let lastTapTime = 0;
  canvas.addEventListener('touchend', function(e){
    const now = Date.now();
    if(now - lastTapTime < 300 && e.touches.length === 0){
      // double-tap: toggle scale 1 <-> 2 centered on last touch
      const last = e.changedTouches[0];
      const wpos = clientToWorld(last.clientX, last.clientY);
      toggleZoomAt(wpos.x, wpos.y);
    }
    lastTapTime = now;
  }, {passive:true});

  // pinch & two-finger pan handling
  canvas.addEventListener('touchmove', function(e){
    if(e.touches && e.touches.length === 2){
      e.preventDefault();
      const t0 = e.touches[0], t1 = e.touches[1];
      const cx = (t0.clientX + t1.clientX)/2, cy = (t0.clientY + t1.clientY)/2;
      const dist = Math.hypot(t0.clientX - t1.clientX, t0.clientY - t1.clientY);
      if(lastPinchDist == null){
        lastPinchDist = dist;
        lastPinchCenter = { x: cx, y: cy };
        return;
      }
      // pinch scale factor
      const factor = dist / lastPinchDist;
      // zoom about pinch center
      const before = clientToWorld(lastPinchCenter.x, lastPinchCenter.y);
      scale *= factor;
      clampScale();
      // after zoom, need to keep the same world point under the same screen pixel,
      // so adjust tx/ty accordingly
      const after = clientToWorld(lastPinchCenter.x, lastPinchCenter.y);
      tx += (after.x - before.x) * scale * dpr;
      ty += (after.y - before.y) * scale * dpr;
      lastPinchDist = dist;
      lastPinchCenter = { x: cx, y: cy };
      draw();
    }
  }, {passive:false});

  canvas.addEventListener('touchend', function(e){
    if(e.touches && e.touches.length < 2){
      lastPinchDist = null; lastPinchCenter = null;
    }
  }, {passive:true});

  // wheel zoom (desktop)
  canvas.addEventListener('wheel', function(e){
    e.preventDefault();
    const delta = -e.deltaY;
    const zoomFactor = delta > 0 ? 1.08 : 0.925;
    const clientX = e.clientX, clientY = e.clientY;
    const before = clientToWorld(clientX, clientY);
    scale *= zoomFactor;
    clampScale();
    const after = clientToWorld(clientX, clientY);
    tx += (after.x - before.x) * scale * dpr;
    ty += (after.y - before.y) * scale * dpr;
    draw();
  }, {passive:false});

  function clampScale(){
    scale = Math.max(0.25, Math.min(6, scale));
  }

  function toggleZoomAt(wx, wy){
    // toggle between 1 and 2 centered on world coords (wx, wy)
    const canvasRect = canvas.getBoundingClientRect();
    const centerClientX = canvasRect.left + canvasRect.width/2;
    const centerClientY = canvasRect.top + canvasRect.height/2;
    if(Math.abs(scale - 1) < 0.01){
      // zoom to 2x centered at world point
      const before = clientToWorld(centerClientX, centerClientY);
      scale = 2;
      const after = clientToWorld(centerClientX, centerClientY);
      tx += (after.x - before.x) * scale * dpr;
      ty += (after.y - before.y) * scale * dpr;
    } else {
      // reset
      scale = 1;
      tx = 0; ty = 0;
    }
    clampScale();
    draw();
  }

  // initial canvas size and event hookups
  function init(){
    // center board initially: set tx/ty so board world (0,0) maps with margin to top-left quarter
    const rect = canvas.getBoundingClientRect();
    // center world onto canvas center
    tx = (rect.width * dpr - viewBoxW * scale * dpr) / 2;
    ty = (rect.height * dpr - viewBoxH * scale * dpr) / 2;
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    canvas.addEventListener('pointermove', onPointerMove);
    // prevent context menu on right click
    canvas.addEventListener('contextmenu', e => e.preventDefault());
    draw();
  }

  // small blocked flash wrapper
  function flashBlocked(key){
    flashBlockedLocal(key);
  }
  function flashBlockedLocal(key){
    // draw red then restore
    flashBlocked(key);
  }

  // start
  init();

})();
</script>
</body>
</html>
"""

# replace placeholders and render
html_code = HTML.replace("__ROWS__", str(ROWS)).replace("__COLS__", str(COLS)).replace("__CELL__", str(CELL_PX))
html(html_code, height=IFRAME_HEIGHT, scrolling=True)
