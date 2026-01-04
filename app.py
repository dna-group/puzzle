# app.py
import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink Board", layout="wide")

ROWS = 199
COLS = 199
CELL_PX = 16
IFRAME_HEIGHT = 1200

HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=4.0"/>
<style>
  html,body{margin:0;padding:0;height:100%;overflow:hidden;background:#fff}
  #root{width:100%;height:100%}
  svg{touch-action:none;display:block}
</style>
</head>
<body>
<div id="root"></div>

<script>
(function(){
  const ROWS = __ROWS__, COLS = __COLS__, CELL = __CELL__, MARGIN = 6;
  const SVG_NS = "http://www.w3.org/2000/svg";

  // data
  const filled = new Set();

  // cached layout
  let viewBoxW = null, viewBoxH = null;
  let rect = null, unitX = 1, unitY = 1;

  // pointer/drag state
  let active = false;
  let mode = null;         // 'add' or 'remove'
  let anchorEdge = null;   // key string
  let anchorClient = null; // {x,y}
  let anchorView = null;   // {x,y} in view coords
  let axis = null;         // 'h' or 'v'
  let appliedSteps = 0;    // steps already applied from anchor
  let rafReq = null;
  let lastMoveEvent = null;
  const MOVE_THRESHOLD = 4; // pixels

  // helpers
  const edgeKey = (r,c,d) => `${r},${c},${d}`;
  function parseKey(k){ const p=k.split(','); return {r:+p[0],c:+p[1],d:p[2]}; }
  function endpointsOf(k){ const {r,c,d}=parseKey(k); return d==='h'? [{r,c},{r,c:c+1}] : [{r,c},{r:r+1,c}]; }
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
    for(const v of endpointsOf(k)) if(vertexDegree(v)>=2) return true;
    return false;
  }

  // build svg
  const width = COLS*CELL + MARGIN*2, height = ROWS*CELL + MARGIN*2;
  viewBoxW = width; viewBoxH = height;

  const svg = document.createElementNS(SVG_NS,'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('preserveAspectRatio','xMidYMid meet');
  svg.style.width='100%'; svg.style.height='auto';
  document.getElementById('root').appendChild(svg);

  // background + dots
  const bg = document.createElementNS(SVG_NS,'rect');
  bg.setAttribute('x',0); bg.setAttribute('y',0); bg.setAttribute('width',width); bg.setAttribute('height',height);
  bg.setAttribute('fill','transparent'); svg.appendChild(bg);
  const dotR = 2;
  for(let r=0;r<=ROWS;r++){ for(let c=0;c<=COLS;c++){
    const dot = document.createElementNS(SVG_NS,'circle');
    dot.setAttribute('cx', MARGIN + c*CELL); dot.setAttribute('cy', MARGIN + r*CELL);
    dot.setAttribute('r', dotR); dot.setAttribute('fill','#000'); svg.appendChild(dot);
  }}

  // create edges groups (vis + hit) — lightweight
  function createEdge(x1,y1,x2,y2,key){
    const g = document.createElementNS(SVG_NS,'g'); g.dataset.edge = key;
    const vis = document.createElementNS(SVG_NS,'line'); vis.setAttribute('x1',x1); vis.setAttribute('y1',y1);
    vis.setAttribute('x2',x2); vis.setAttribute('y2',y2); vis.setAttribute('stroke-width',3);
    vis.setAttribute('stroke-linecap','round'); vis.classList.add('vis'); vis.setAttribute('stroke','transparent');
    const hit = document.createElementNS(SVG_NS,'line'); hit.setAttribute('x1',x1); hit.setAttribute('y1',y1);
    hit.setAttribute('x2',x2); hit.setAttribute('y2',y2); hit.setAttribute('stroke-width', CELL*0.6);
    hit.setAttribute('stroke','transparent'); hit.style.cursor='pointer';
    hit.addEventListener('pointerdown', onPointerDown);
    hit.addEventListener('pointerup', onPointerUp);
    g.appendChild(vis); g.appendChild(hit); svg.appendChild(g);
  }

  for(let r=0;r<=ROWS;r++){ for(let c=0;c<COLS;c++){
    const x1 = MARGIN + c*CELL, y = MARGIN + r*CELL; createEdge(x1,y,x1+CELL,y, edgeKey(r,c,'h'));
  }}
  for(let r=0;r<ROWS;r++){ for(let c=0;c<=COLS;c++){
    const x = MARGIN + c*CELL, y1 = MARGIN + r*CELL; createEdge(x,y1,x,y1+CELL, edgeKey(r,c,'v'));
  }}

  function updateVisuals(){
    svg.querySelectorAll('[data-edge]').forEach(g=>{
      const k = g.dataset.edge; const vis = g.querySelector('.vis');
      vis.setAttribute('stroke', filled.has(k) ? '#000' : 'transparent');
    });
  }

  // layout cache
  function refreshLayoutCache(){
    rect = svg.getBoundingClientRect();
    unitX = viewBoxW / rect.width; unitY = viewBoxH / rect.height;
  }
  window.addEventListener('resize', ()=>{ if(svg) refreshLayoutCache(); });

  // map client->view coords (fast)
  function clientToView(cx,cy){
    return { x: (cx - rect.left) * unitX, y: (cy - rect.top) * unitY };
  }

  // nearest edge pick (cheap arithmetic)
  function nearestEdgeForClient(cx,cy){
    const v = clientToView(cx,cy);
    const sx = v.x, sy = v.y;
    const r_h = Math.round((sy - MARGIN) / CELL);
    const c_h = Math.floor((sx - MARGIN) / CELL);
    let dh = Infinity, kh = null;
    if(r_h>=0 && r_h<=ROWS && c_h>=0 && c_h<COLS){
      const hx = MARGIN + (c_h + 0.5)*CELL, hy = MARGIN + r_h*CELL;
      dh = Math.hypot(sx-hx, sy-hy); kh = edgeKey(r_h,c_h,'h');
    }
    const c_v = Math.round((sx - MARGIN) / CELL);
    const r_v = Math.floor((sy - MARGIN) / CELL);
    let dv = Infinity, kv = null;
    if(c_v>=0 && c_v<=COLS && r_v>=0 && r_v<ROWS){
      const vx = MARGIN + c_v*CELL, vy = MARGIN + (r_v + 0.5)*CELL;
      dv = Math.hypot(sx-vx, sy-vy); kv = edgeKey(r_v,c_v,'v');
    }
    return dh <= dv ? kh : kv;
  }

  // pointer handlers — minimal work on pointerdown
  function onPointerDown(ev){
    ev.preventDefault();
    try{ ev.target.setPointerCapture(ev.pointerId); }catch(e){}
    refreshLayoutCache();
    active = true; lastMoveEvent = null;
    anchorClient = {x: ev.clientX, y: ev.clientY};
    anchorEdge = nearestEdgeForClient(ev.clientX, ev.clientY);
    anchorView = clientToView(anchorClient.x, anchorClient.y);
    appliedSteps = 0; axis = null;
    mode = filled.has(anchorEdge) ? 'remove' : 'add';
    // immediate action
    if(mode === 'add'){
      if(!wouldExceed(anchorEdge)){ filled.add(anchorEdge); } else flash(anchorEdge);
    } else { filled.delete(anchorEdge); }
    updateVisuals();
  }

  function onPointerUp(ev){
    try{ ev.target.releasePointerCapture(ev.pointerId); }catch(e){}
    active = false; mode = null; anchorEdge = null; anchorClient = null; axis = null; appliedSteps = 0;
    if(rafReq){ cancelAnimationFrame(rafReq); rafReq = null; }
  }

  // degree check uses same helpers
  function endpointsOfKey(k){ const p=k.split(','); const r=+p[0], c=+p[1], d=p[2]; return d==='h'? [{r,c},{r,c:c+1}]: [{r,c},{r:r+1,c}]; }
  function vertexDeg(v){
    let d=0; if(v.c-1>=0 && filled.has(edgeKey(v.r,v.c-1,'h'))) d++; if(v.c<=COLS-1 && filled.has(edgeKey(v.r,v.c,'h'))) d++;
    if(v.r-1>=0 && filled.has(edgeKey(v.r-1,v.c,'v'))) d++; if(v.r<=ROWS-1 && filled.has(edgeKey(v.r,v.c,'v'))) d++; return d;
  }
  function wouldExceed(k){ if(filled.has(k)) return false; for(const v of endpointsOfKey(k)) if(vertexDeg(v)>=2) return true; return false; }
  function flash(k){ const g = svg.querySelector(`[data-edge="${k}"]`); if(!g) return; const vis=g.querySelector('.vis'); vis.setAttribute('stroke','#d00'); setTimeout(()=>vis.setAttribute('stroke', filled.has(k)?'#000':'transparent'),160); }

  // throttled move handler via rAF
  svg.addEventListener('pointermove', function(ev){
    if(!active) return;
    lastMoveEvent = ev;
    if(!rafReq) rafReq = requestAnimationFrame(processMove);
  }, {passive:true});

  function processMove(){
    rafReq = null;
    const ev = lastMoveEvent;
    if(!ev || !active || !anchorClient) return;
    const dx = ev.clientX - anchorClient.x, dy = ev.clientY - anchorClient.y;
    const dist = Math.hypot(dx,dy);
    if(dist < MOVE_THRESHOLD) return;

    // determine dominant axis dynamically
    const newAxis = Math.abs(dx) >= Math.abs(dy) ? 'h' : 'v';
    if(axis !== newAxis){
      // re-anchor on axis switch: set anchor to current pointer
      anchorClient = {x: ev.clientX, y: ev.clientY};
      anchorView = clientToView(anchorClient.x, anchorClient.y);
      axis = newAxis; appliedSteps = 0;
      // update anchorEdge based on nearest edge at the new anchor
      anchorEdge = nearestEdgeForClient(anchorClient.x, anchorClient.y);
      mode = filled.has(anchorEdge) ? 'remove' : 'add';
      return;
    }

    // compute moved units along axis in view coordinates
    const movedUnits = axis === 'h' ? (ev.clientX - anchorClient.x) * unitX : (ev.clientY - anchorClient.y) * unitY;
    const sign = movedUnits >= 0 ? 1 : -1;
    const stepsNow = Math.floor(Math.abs(movedUnits) / CELL);
    if(stepsNow <= appliedSteps) return;
    const newSteps = stepsNow - appliedSteps;

    const base = parseKey(anchorEdge);
    // for mapping when base.d != axis, pick anchor index based on anchorView (as earlier)
    const anchorV = anchorView;

    for(let s=1; s<=newSteps; s++){
      let keyToAct = null;
      const stepIndex = appliedSteps + s;
      if(base.d === axis){
        if(axis === 'h'){
          const nc = base.c + sign*stepIndex; if(nc<0||nc>=COLS) break; keyToAct = edgeKey(base.r,nc,'h');
        } else {
          const nr = base.r + sign*stepIndex; if(nr<0||nr>=ROWS) break; keyToAct = edgeKey(nr,base.c,'v');
        }
      } else {
        if(base.d === 'h' && axis === 'v'){
          const col = anchorV.x <= (MARGIN + (base.c+0.5)*CELL) ? base.c : base.c+1;
          const nr = base.r + sign*stepIndex; if(nr<0||nr>=ROWS||col<0||col>COLS) break; keyToAct = edgeKey(nr,col,'v');
        } else if(base.d === 'v' && axis === 'h'){
          const row = anchorV.y <= (MARGIN + (base.r+0.5)*CELL) ? base.r : base.r+1;
          const nc = base.c + sign*stepIndex; if(nc<0||nc>=COLS||row<0||row>ROWS) break; keyToAct = edgeKey(row,nc,'h');
        }
      }

      if(!keyToAct) continue;
      if(mode === 'add'){
        if(!filled.has(keyToAct)){
          if(!wouldExceed(keyToAct)) filled.add(keyToAct); else flash(keyToAct);
        }
      } else {
        if(filled.has(keyToAct)) filled.delete(keyToAct);
      }
    }

    appliedSteps = stepsNow;
    updateVisuals();
  }

  // double-tap / pinch unchanged
  let lastTap=0, lastDist=null;
  document.addEventListener('touchend', function(){
    const now=Date.now(); if(now-lastTap<300){ const cur = svg.style.transform?parseFloat(svg.style.transform.replace('scale(','')):1; svg.style.transformOrigin='0 0'; svg.style.transform=`scale(${cur===1?2:1})`; } lastTap=now;
  }, {passive:true});
  document.addEventListener('touchmove', function(e){ if(e.touches && e.touches.length===2){ e.preventDefault(); const d=Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY); if(lastDist){ const cur=svg.style.transform?parseFloat(svg.style.transform.replace('scale(','')):1; const next=Math.max(0.5, Math.min(4, cur*(d/lastDist))); svg.style.transformOrigin='0 0'; svg.style.transform=`scale(${next})`; } lastDist=d;} }, {passive:false});
  document.addEventListener('touchend', function(){ lastDist=null; }, {passive:true});

  // initial cache
  refreshLayoutCache();
  updateVisuals();
  console.log('Responsive slither ready');
})();
</script>
</body>
</html>
"""

html(
    HTML
    .replace("__ROWS__", str(ROWS))
    .replace("__COLS__", str(COLS))
    .replace("__CELL__", str(CELL_PX)),
    height=IFRAME_HEIGHT,
    scrolling=True
)
