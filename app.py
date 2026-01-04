# app.py
import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink Canvas (circle-detect)", layout="wide")

# Board parameters — updated per request
DOTS_X = 128           # number of dots horizontally
DOTS_Y = 178           # number of dots vertically
ROWS = DOTS_Y - 1
COLS = DOTS_X - 1
CELL_PX = 16           # logical world units per cell (you can tweak)
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
  body,canvas { -webkit-user-select: none; -ms-user-select: none; user-select: none; -webkit-touch-callout: none; }
</style>
</head>
<body>
<div id="root"><canvas id="board"></canvas></div>

<script>
(function(){
  // config
  const ROWS = __ROWS__, COLS = __COLS__, CELL = __CELL__, MARGIN = 6;
  const canvas = document.getElementById('board');
  const ctx = canvas.getContext('2d', { alpha: false });
  const dpr = Math.max(1, window.devicePixelRatio || 1);

  // state
  const filled = new Set();
  let scale = 1.0;
  let tx = 0, ty = 0;
  const viewW = COLS * CELL + MARGIN * 2;
  const viewH = ROWS * CELL + MARGIN * 2;

  // pointer state
  let active = false;
  let mode = null;           // 'add' or 'remove' (decided by first edge hit)
  let lastEdge = null;       // last edge acted on (prevents repeats)
  let lastMoveEvent = null;
  let raf = null;
  const MOVE_THRESHOLD = 2;

  // detection radius: diameter = d/2 was previous; now radius = d/3 per request
  const DETECT_RADIUS_WORLD = CELL / 3.0;

  // helpers
  const edgeKey = (r,c,d) => `${r},${c},${d}`;
  function parseKey(k){ const p=k.split(','); return {r:+p[0], c:+p[1], d:p[2]}; }
  function endpointsOf(key){
    const p = parseKey(key);
    return p.d === 'h' ? [{r:p.r,c:p.c},{r:p.r,c:p.c+1}] : [{r:p.r,c:p.c},{r:p.r+1,c:p.c}];
  }
  function vertexDegree(v){
    let deg=0;
    if(v.c-1>=0 && filled.has(edgeKey(v.r,v.c-1,'h'))) deg++;
    if(v.c<=COLS-1 && filled.has(edgeKey(v.r,v.c,'h'))) deg++;
    if(v.r-1>=0 && filled.has(edgeKey(v.r-1,v.c,'v'))) deg++;
    if(v.r<=ROWS-1 && filled.has(edgeKey(v.r,v.c,'v'))) deg++;
    return deg;
  }
  function wouldExceedIfAdd(k){
    if(filled.has(k)) return false;
    for(const v of endpointsOf(k)) if(vertexDegree(v) >= 2) return true;
    return false;
  }

  // coordinate transforms (pixel-aligned drawing)
  function worldToCanvasPx(wx, wy){
    const sx = Math.round(wx * scale * dpr + tx);
    const sy = Math.round(wy * scale * dpr + ty);
    return { x: sx, y: sy };
  }
  function clientToWorld(cx, cy){
    const rect = canvas.getBoundingClientRect();
    const cx_px = (cx - rect.left) * dpr;
    const cy_px = (cy - rect.top) * dpr;
    return { x: (cx_px - tx) / (scale * dpr), y: (cy_px - ty) / (scale * dpr) };
  }

  // nearest edge + distance to its midpoint in world units
  function nearestEdgeToWorldWithDist(wx, wy){
    // horizontal candidate
    const r_h = Math.round((wy - MARGIN) / CELL);
    const c_h = Math.floor((wx - MARGIN) / CELL);
    let dist_h = Infinity, key_h = null;
    if(r_h >= 0 && r_h <= ROWS && c_h >= 0 && c_h < COLS){
      const hx = MARGIN + (c_h + 0.5) * CELL, hy = MARGIN + r_h * CELL;
      dist_h = Math.hypot(wx - hx, wy - hy);
      key_h = edgeKey(r_h, c_h, 'h');
    }
    // vertical candidate
    const c_v = Math.round((wx - MARGIN) / CELL);
    const r_v = Math.floor((wy - MARGIN) / CELL);
    let dist_v = Infinity, key_v = null;
    if(c_v >= 0 && c_v <= COLS && r_v >= 0 && r_v < ROWS){
      const vx = MARGIN + c_v * CELL, vy = MARGIN + (r_v + 0.5) * CELL;
      dist_v = Math.hypot(wx - vx, wy - vy);
      key_v = edgeKey(r_v, c_v, 'v');
    }
    if(dist_h <= dist_v) return { key: key_h, dist: dist_h };
    return { key: key_v, dist: dist_v };
  }

  // drawing
  function resizeCanvas(){
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    draw();
  }

  function clearCanvas(){
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0,0,canvas.width,canvas.height);
  }

  function draw(){
    clearCanvas();
    ctx.lineCap = 'round';
    ctx.lineWidth = Math.max(1, Math.floor(0.18 * CELL * scale * dpr));
    ctx.strokeStyle = '#000';

    // draw filled edges
    filled.forEach(k=>{
      const p = parseKey(k);
      if(p.d === 'h'){
        const x1w = MARGIN + p.c * CELL, y = MARGIN + p.r * CELL;
        const x2w = x1w + CELL;
        const a = worldToCanvasPx(x1w, y), b = worldToCanvasPx(x2w, y);
        ctx.beginPath(); ctx.moveTo(a.x + 0.5, a.y + 0.5); ctx.lineTo(b.x + 0.5, b.y + 0.5); ctx.stroke();
      } else {
        const x = MARGIN + p.c * CELL, y1w = MARGIN + p.r * CELL, y2w = y1w + CELL;
        const a = worldToCanvasPx(x, y1w), b = worldToCanvasPx(x, y2w);
        ctx.beginPath(); ctx.moveTo(a.x + 0.5, a.y + 0.5); ctx.lineTo(b.x + 0.5, b.y + 0.5); ctx.stroke();
      }
    });

    // draw dots on top
    ctx.fillStyle = '#000';
    const dotRadiusPx = Math.max(1, Math.round(0.12 * CELL * scale * dpr));
    for(let r=0;r<=ROWS;r++){
      const wy = MARGIN + r * CELL;
      for(let c=0;c<=COLS;c++){
        const wx = MARGIN + c * CELL;
        const p = worldToCanvasPx(wx, wy);
        ctx.beginPath(); ctx.arc(p.x, p.y, dotRadiusPx, 0, Math.PI*2); ctx.fill();
      }
    }
  }

  function flashBlocked(key){
    const p = parseKey(key);
    ctx.lineCap = 'round';
    ctx.lineWidth = Math.max(1, Math.floor(0.18 * CELL * scale * dpr));
    ctx.strokeStyle = '#d00';
    if(p.d === 'h'){
      const x1w = MARGIN + p.c * CELL, y = MARGIN + p.r * CELL, x2w = x1w + CELL;
      const a = worldToCanvasPx(x1w, y), b = worldToCanvasPx(x2w, y);
      ctx.beginPath(); ctx.moveTo(a.x + 0.5, a.y + 0.5); ctx.lineTo(b.x + 0.5, b.y + 0.5); ctx.stroke();
    } else {
      const x = MARGIN + p.c * CELL, y1w = MARGIN + p.r * CELL, y2w = y1w + CELL;
      const a = worldToCanvasPx(x, y1w), b = worldToCanvasPx(x, y2w);
      ctx.beginPath(); ctx.moveTo(a.x + 0.5, a.y + 0.5); ctx.lineTo(b.x + 0.5, b.y + 0.5); ctx.stroke();
    }
    setTimeout(draw, 160);
  }

  // process move with rAF
  function scheduleMove(ev){
    lastMoveEvent = ev;
    if(!raf) raf = requestAnimationFrame(processMove);
  }

  function processMove(){
    raf = null;
    const ev = lastMoveEvent;
    if(!active || !ev) return;
    // get world coords of pointer
    const w = clientToWorld(ev.clientX, ev.clientY);
    const nearest = nearestEdgeToWorldWithDist(w.x, w.y);
    if(!nearest || !nearest.key) return;
    // detection: circle radius = CELL / 3 (as requested)
    if(nearest.dist <= DETECT_RADIUS_WORLD){
      if(nearest.key !== lastEdge){
        // first time entering this circle or switched to new edge
        if(mode === null){
          mode = filled.has(nearest.key) ? 'remove' : 'add';
        }
        if(mode === 'add'){
          if(!filled.has(nearest.key)){
            if(!wouldExceedIfAdd(nearest.key)){
              filled.add(nearest.key);
            } else {
              flashBlocked(nearest.key);
            }
          }
        } else {
          if(filled.has(nearest.key)) filled.delete(nearest.key);
        }
        lastEdge = nearest.key;
        draw();
      }
    }
  }

  // pointer handlers
  function onPointerDown(ev){
    ev.preventDefault();
    try{ ev.target.setPointerCapture(ev.pointerId); } catch(e){}
    active = true;
    lastEdge = null;
    // decide initial mode if down occurs inside detection circle
    const w = clientToWorld(ev.clientX, ev.clientY);
    const nearest = nearestEdgeToWorldWithDist(w.x, w.y);
    if(nearest && nearest.key && nearest.dist <= DETECT_RADIUS_WORLD){
      mode = filled.has(nearest.key) ? 'remove' : 'add';
      // immediate action on down
      if(mode === 'add'){
        if(!filled.has(nearest.key)){
          if(!wouldExceedIfAdd(nearest.key)) filled.add(nearest.key); else flashBlocked(nearest.key);
        }
      } else {
        if(filled.has(nearest.key)) filled.delete(nearest.key);
      }
      lastEdge = nearest.key;
      draw();
    } else {
      mode = null; // wait until pointer enters a detection circle during drag
    }
  }

  function onPointerUp(ev){
    try{ ev.target.releasePointerCapture(ev.pointerId); } catch(e){}
    active = false;
    mode = null;
    lastEdge = null;
    if(raf){ cancelAnimationFrame(raf); raf = null; lastMoveEvent = null; }
  }

  function onPointerMove(ev){
    if(!active) return;
    lastMoveEvent = ev;
    if(!raf) raf = requestAnimationFrame(processMove);
  }

  // zoom & pan (wheel & pinch)
  let lastPinchDist = null, lastPinchCenter = null;
  canvas.addEventListener('wheel', function(e){
    e.preventDefault();
    const delta = -e.deltaY;
    const factor = delta > 0 ? 1.08 : 0.925;
    const before = clientToWorld(e.clientX, e.clientY);
    scale *= factor; scale = Math.max(0.25, Math.min(6, scale));
    const after = clientToWorld(e.clientX, e.clientY);
    tx += (after.x - before.x) * scale * dpr;
    ty += (after.y - before.y) * scale * dpr;
    draw();
  }, {passive:false});

  canvas.addEventListener('touchmove', function(e){
    if(e.touches && e.touches.length === 2){
      e.preventDefault();
      const t0 = e.touches[0], t1 = e.touches[1];
      const cx = (t0.clientX + t1.clientX)/2, cy = (t0.clientY + t1.clientY)/2;
      const dist = Math.hypot(t0.clientX - t1.clientX, t0.clientY - t1.clientY);
      if(lastPinchDist == null){ lastPinchDist = dist; lastPinchCenter = { x: cx, y: cy }; return; }
      const factor = dist / lastPinchDist;
      const before = clientToWorld(lastPinchCenter.x, lastPinchCenter.y);
      scale *= factor; scale = Math.max(0.25, Math.min(6, scale));
      const after = clientToWorld(lastPinchCenter.x, lastPinchCenter.y);
      tx += (after.x - before.x) * scale * dpr;
      ty += (after.y - before.y) * scale * dpr;
      lastPinchDist = dist; lastPinchCenter = { x: cx, y: cy };
      draw();
    }
  }, {passive:false});
  canvas.addEventListener('touchend', function(e){ if(e.touches && e.touches.length < 2){ lastPinchDist = null; lastPinchCenter = null; } }, {passive:true});

  // double-tap to toggle zoom
  let lastTap = 0;
  canvas.addEventListener('touchend', function(e){
    const now = Date.now();
    if(now - lastTap < 300 && e.changedTouches.length){
      if(Math.abs(scale - 1) < 0.01){ scale = 2; } else { scale = 1; tx = 0; ty = 0; }
      draw();
    }
    lastTap = now;
  }, {passive:true});

  // initial fit-to-screen & setup
  function init(){
    const rect = canvas.getBoundingClientRect();
    const fitScale = Math.min(rect.width / viewW, rect.height / viewH) * 0.96;
    scale = Math.max(0.25, Math.min(6, fitScale));
    tx = (rect.width * dpr - viewW * scale * dpr) / 2;
    ty = (rect.height * dpr - viewH * scale * dpr) / 2;
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('contextmenu', e => e.preventDefault());
    draw();
  }

  // convert client coords to world coords (utility)
  function clientToWorld(cx, cy){
    const rect = canvas.getBoundingClientRect();
    const cx_px = (cx - rect.left) * dpr;
    const cy_px = (cy - rect.top) * dpr;
    return { x: (cx_px - tx) / (scale * dpr), y: (cy_px - ty) / (scale * dpr) };
  }

  init();
})();
</script>
</body>
</html>
"""

html_code = HTML.replace("__ROWS__", str(ROWS)).replace("__COLS__", str(COLS)).replace("__CELL__", str(CELL_PX))
html(html_code, height=IFRAME_HEIGHT, scrolling=True)
