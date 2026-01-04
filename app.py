# app.py
import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink Canvas (tap-to-toggle, drag-to-pan)", layout="wide")

# Board parameters — kept from last request
DOTS_X = 128
DOTS_Y = 178
ROWS = DOTS_Y - 1
COLS = DOTS_X - 1
CELL_PX = 16
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
  let tx = 0, ty = 0; // translation in canvas pixels
  const viewW = COLS * CELL + MARGIN * 2;
  const viewH = ROWS * CELL + MARGIN * 2;

  // interaction state
  let pointerActive = false;
  let activePointerId = null;
  let pointerStart = null;     // {x,y} client coords at down
  let pointerLast = null;      // last client coords during move
  let isPanning = false;
  const MOVE_THRESHOLD = 6;    // pixels to decide pan vs tap

  // multitouch pinch state
  let lastPinchDist = null;
  let lastPinchCenter = null;

  // detection circle radius for tap toggle: radius = d/3 (d == CELL)
  const DETECT_RADIUS_WORLD = CELL / 3.5;

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

  // coordinate conversions (pixel-aligned drawing)
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

  // pointer helpers: handle tap (toggle) and pan
  function handleTapToggle(clientX, clientY){
    const w = clientToWorld(clientX, clientY);
    const nearest = nearestEdgeToWorldWithDist(w.x, w.y);
    if(!nearest || !nearest.key) return;
    if(nearest.dist <= DETECT_RADIUS_WORLD){
      // toggle with degree constraint on add
      if(filled.has(nearest.key)){
        filled.delete(nearest.key);
        draw();
      } else {
        if(!wouldExceedIfAdd(nearest.key)){
          filled.add(nearest.key);
          draw();
        } else {
          flashBlocked(nearest.key);
        }
      }
    }
  }

  // pointer events: single-pointer pan; tap toggles edges (no drag-to-draw)
  canvas.addEventListener('pointerdown', function(ev){
    // ignore non-primary pointers
    if(ev.isPrimary === false) return;
    ev.preventDefault();
    try{ ev.target.setPointerCapture(ev.pointerId); } catch(e){}
    pointerActive = true;
    activePointerId = ev.pointerId;
    pointerStart = { x: ev.clientX, y: ev.clientY };
    pointerLast = { x: ev.clientX, y: ev.clientY };
    isPanning = false;
  }, {passive:false});

  canvas.addEventListener('pointermove', function(ev){
    if(!pointerActive || ev.pointerId !== activePointerId) return;
    // if two-finger pinch is active (handled separately via touch events), skip here
    const dx = ev.clientX - pointerLast.x;
    const dy = ev.clientY - pointerLast.y;
    pointerLast = { x: ev.clientX, y: ev.clientY };

    const totalDx = ev.clientX - pointerStart.x;
    const totalDy = ev.clientY - pointerStart.y;
    if(!isPanning && Math.hypot(totalDx, totalDy) >= MOVE_THRESHOLD){
      isPanning = true; // start panning
    }
    if(isPanning){
      // apply pan in canvas pixels, respecting dpr & scale already baked into tx/ty logic
      // We moved in client pixels; convert to canvas pixels by *dpr*
      tx += dx * dpr;
      ty += dy * dpr;
      draw();
    }
  }, {passive:true});

  canvas.addEventListener('pointerup', function(ev){
    if(ev.pointerId !== activePointerId) return;
    try{ ev.target.releasePointerCapture(ev.pointerId); } catch(e){}
    // if it was not a pan (i.e., small movement), treat as tap
    const totalDx = ev.clientX - pointerStart.x;
    const totalDy = ev.clientY - pointerStart.y;
    if(Math.hypot(totalDx, totalDy) < MOVE_THRESHOLD){
      handleTapToggle(ev.clientX, ev.clientY);
    }
    pointerActive = false;
    activePointerId = null;
    pointerStart = null;
    pointerLast = null;
    isPanning = false;
  }, {passive:false});

  canvas.addEventListener('pointercancel', function(ev){
    if(ev.pointerId !== activePointerId) return;
    try{ ev.target.releasePointerCapture(ev.pointerId); } catch(e){}
    pointerActive = false; activePointerId = null; pointerStart = null; pointerLast = null; isPanning = false;
  }, {passive:false});

  // touch pinch zoom and two-finger pan: handle via touch events
  canvas.addEventListener('touchstart', function(e){
    if(e.touches && e.touches.length === 2){
      lastPinchDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      lastPinchCenter = {
        x: (e.touches[0].clientX + e.touches[1].clientX) / 2,
        y: (e.touches[0].clientY + e.touches[1].clientY) / 2
      };
    }
  }, {passive:true});

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
      const factor = dist / lastPinchDist;
      // zoom about pinch center
      const before = clientToWorld(lastPinchCenter.x, lastPinchCenter.y);
      scale *= factor; scale = Math.max(0.25, Math.min(6, scale));
      const after = clientToWorld(lastPinchCenter.x, lastPinchCenter.y);
      // adjust tx/ty so the same world point stays under the same screen pixel
      tx += (after.x - before.x) * scale * dpr;
      ty += (after.y - before.y) * scale * dpr;
      // two-finger pan (if pinch center moved)
      const moveX = cx - lastPinchCenter.x;
      const moveY = cy - lastPinchCenter.y;
      tx += moveX * dpr;
      ty += moveY * dpr;
      lastPinchDist = dist;
      lastPinchCenter = { x: cx, y: cy };
      draw();
    }
  }, {passive:false});

  canvas.addEventListener('touchend', function(e){
    if(e.touches && e.touches.length < 2){
      lastPinchDist = null;
      lastPinchCenter = null;
    }
  }, {passive:true});

  // wheel zoom (desktop)
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

  // double-tap to toggle zoom centered on touch
  let lastTap = 0;
  canvas.addEventListener('touchend', function(e){
    const now = Date.now();
    if(now - lastTap < 300 && e.changedTouches.length){
      if(Math.abs(scale - 1) < 0.01){
        scale = 2;
      } else {
        scale = 1; tx = 0; ty = 0;
      }
      draw();
    }
    lastTap = now;
  }, {passive:true});

  // prevent context menu
  canvas.addEventListener('contextmenu', e => e.preventDefault());

  // initial fit-to-screen & setup
  function init(){
    // compute initial scale to fit board to canvas rect
    const rect = canvas.getBoundingClientRect();
    // handle case rect width/height might be 0 initially; use setTimeout fallback
    const computeAndSetup = () => {
      const r = canvas.getBoundingClientRect();
      const fitScale = Math.min(r.width / viewW, r.height / viewH) * 0.96;
      scale = Math.max(0.25, Math.min(6, fitScale));
      tx = (r.width * dpr - viewW * scale * dpr) / 2;
      ty = (r.height * dpr - viewH * scale * dpr) / 2;
      resizeCanvas();
      window.addEventListener('resize', resizeCanvas);
      draw();
    };
    // sometimes getBoundingClientRect returns 0 if not yet laid out; guard
    const r = canvas.getBoundingClientRect();
    if(r.width <= 0 || r.height <= 0){
      // try again shortly
      setTimeout(computeAndSetup, 50);
    } else {
      computeAndSetup();
    }
  }

  init();

})();
</script>
</body>
</html>
"""

html_code = HTML.replace("__ROWS__", str(ROWS)).replace("__COLS__", str(COLS)).replace("__CELL__", str(CELL_PX))
html(html_code, height=IFRAME_HEIGHT, scrolling=True)
