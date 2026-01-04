# app.py
import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink Board", layout="wide")

# Fixed board size: 200 x 200 dots (199 x 199 cells)
ROWS = 199   # cells vertically
COLS = 199   # cells horizontally
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
  const ROWS = __ROWS__;
  const COLS = __COLS__;
  const CELL = __CELL__;
  const MARGIN = 6;
  const SVG_NS = "http://www.w3.org/2000/svg";

  const filled = new Set();

  // pointer state
  let pointerActive = false;
  let pointerMode = null;       // 'add' or 'remove'
  let initialEdge = null;       // key of the first selected edge
  let dragAxis = null;          // 'h' or 'v' decided by first significant move
  let lastAddedEdge = null;     // last edge added/removed (for stepping)
  let startClient = null;       // {x,y} of initial pointerdown client coords
  let viewBoxW = null, viewBoxH = null; // for coordinate mapping

  function edgeKey(r,c,d){ return r + "," + c + "," + d; }
  function parseKey(key){ const p = key.split(','); return {r:parseInt(p[0],10), c:parseInt(p[1],10), d:p[2]}; }

  function endpointsOf(key){
    const {r,c,d} = parseKey(key);
    return d === 'h' ? [{r:r,c:c},{r:r,c:c+1}] : [{r:r,c:c},{r:r+1,c:c}];
  }

  function vertexDegree(v){
    const vr=v.r, vc=v.c;
    let deg=0;
    // horizontals
    if(vc-1 >= 0 && filled.has(edgeKey(vr,vc-1,'h'))) deg++;
    if(vc <= COLS-1 && filled.has(edgeKey(vr,vc,'h'))) deg++;
    // verticals
    if(vr-1 >= 0 && filled.has(edgeKey(vr-1,vc,'v'))) deg++;
    if(vr <= ROWS-1 && filled.has(edgeKey(vr,vc,'v'))) deg++;
    return deg;
  }

  function wouldExceedDegreeIfAdded(key){
    if(filled.has(key)) return false;
    const eps = endpointsOf(key);
    for(const v of eps){
      if(vertexDegree(v) >= 2) return true;
    }
    return false;
  }

  // build SVG
  const width  = COLS * CELL + MARGIN * 2;
  const height = ROWS * CELL + MARGIN * 2;
  viewBoxW = width; viewBoxH = height;

  const svg = document.createElementNS(SVG_NS,"svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.style.width = "100%";
  svg.style.height = "auto";
  document.getElementById("root").appendChild(svg);

  const bg = document.createElementNS(SVG_NS,"rect");
  bg.setAttribute("x",0); bg.setAttribute("y",0);
  bg.setAttribute("width", width); bg.setAttribute("height", height);
  bg.setAttribute("fill", "transparent");
  svg.appendChild(bg);

  // draw dots
  const dotR = 2;
  for(let r=0;r<=ROWS;r++){
    for(let c=0;c<=COLS;c++){
      const dot = document.createElementNS(SVG_NS,"circle");
      dot.setAttribute("cx", MARGIN + c*CELL);
      dot.setAttribute("cy", MARGIN + r*CELL);
      dot.setAttribute("r", dotR);
      dot.setAttribute("fill", "#000");
      svg.appendChild(dot);
    }
  }

  // create edge groups (vis + hit) but keep hit handlers lightweight;
  // we'll still support pointerdown even if user clicks slightly off by computing nearest edge
  function createEdgeGroup(x1,y1,x2,y2,key){
    const g = document.createElementNS(SVG_NS,"g");
    g.setAttribute("data-edge", key);
    const vis = document.createElementNS(SVG_NS,"line");
    vis.setAttribute("x1", x1); vis.setAttribute("y1", y1);
    vis.setAttribute("x2", x2); vis.setAttribute("y2", y2);
    vis.setAttribute("stroke-width", 3);
    vis.setAttribute("stroke-linecap", "round");
    vis.setAttribute("class", "vis");
    vis.setAttribute("stroke", "transparent");

    const hit = document.createElementNS(SVG_NS,"line");
    hit.setAttribute("x1", x1); hit.setAttribute("y1", y1);
    hit.setAttribute("x2", x2); hit.setAttribute("y2", y2);
    hit.setAttribute("stroke-width", CELL * 0.6);
    hit.setAttribute("stroke", "transparent");
    hit.style.cursor = "pointer";

    // lightweight handlers here: but the primary selection logic will compute nearest edge if needed
    hit.addEventListener("pointerdown", function(ev){
      handlePointerDown(ev);
    });
    hit.addEventListener("pointerup", function(ev){
      handlePointerUp(ev);
    });

    g.appendChild(vis); g.appendChild(hit);
    svg.appendChild(g);
  }

  for(let r=0;r<=ROWS;r++){
    for(let c=0;c<COLS;c++){
      const x1 = MARGIN + c*CELL, y = MARGIN + r*CELL, x2 = x1 + CELL;
      createEdgeGroup(x1,y,x2,y, edgeKey(r,c,'h'));
    }
  }
  for(let r=0;r<ROWS;r++){
    for(let c=0;c<=COLS;c++){
      const x = MARGIN + c*CELL, y1 = MARGIN + r*CELL, y2 = y1 + CELL;
      createEdgeGroup(x,y1,x,y2, edgeKey(r,c,'v'));
    }
  }

  // update visuals
  function updateVisuals(){
    svg.querySelectorAll("[data-edge]").forEach(function(g){
      const k = g.getAttribute("data-edge");
      const vis = g.querySelector(".vis");
      if(filled.has(k)){
        vis.setAttribute("stroke","#000");
      } else {
        vis.setAttribute("stroke","transparent");
      }
    });
  }

  // map client coords to viewBox coords (approximate, accounts for CSS scaling)
  function clientToViewBox(clientX, clientY){
    const rect = svg.getBoundingClientRect();
    // fraction within rect
    const fx = (clientX - rect.left) / rect.width;
    const fy = (clientY - rect.top) / rect.height;
    // map to viewBox (0..viewBoxW / viewBoxH)
    return { x: fx * viewBoxW, y: fy * viewBoxH };
  }

  // compute nearest candidate edge to given client coords
  function nearestEdgeKeyForClient(clientX, clientY){
    const pt = clientToViewBox(clientX, clientY);
    const sx = pt.x, sy = pt.y;
    // compute nearest horizontal candidate:
    const r_h = Math.round((sy - MARGIN) / CELL);
    const c_h = Math.floor((sx - MARGIN) / CELL);
    let dist_h = Infinity, key_h = null;
    if(r_h >= 0 && r_h <= ROWS && c_h >= 0 && c_h < COLS){
      const hx = MARGIN + (c_h + 0.5) * CELL;
      const hy = MARGIN + r_h * CELL;
      dist_h = Math.hypot(sx - hx, sy - hy);
      key_h = edgeKey(r_h, c_h, 'h');
    }
    // compute vertical candidate:
    const c_v = Math.round((sx - MARGIN) / CELL);
    const r_v = Math.floor((sy - MARGIN) / CELL);
    let dist_v = Infinity, key_v = null;
    if(c_v >= 0 && c_v <= COLS && r_v >= 0 && r_v < ROWS){
      const vx = MARGIN + c_v * CELL;
      const vy = MARGIN + (r_v + 0.5) * CELL;
      dist_v = Math.hypot(sx - vx, sy - vy);
      key_v = edgeKey(r_v, c_v, 'v');
    }
    // choose smaller distance
    if(dist_h <= dist_v) return key_h;
    return key_v;
  }

  // core: handle pointerdown (choose nearest edge if needed)
  function handlePointerDown(ev){
    ev.preventDefault();
    try{ ev.target.setPointerCapture(ev.pointerId); } catch(e){}
    pointerActive = true;
    startClient = { x: ev.clientX, y: ev.clientY };
    // pick nearest edge (even if the event was on background)
    const chosen = nearestEdgeKeyForClient(ev.clientX, ev.clientY);
    if(!chosen) return;
    initialEdge = chosen;
    lastAddedEdge = chosen;
    // decide add/remove based on current presence
    pointerMode = filled.has(chosen) ? 'remove' : 'add';
    // do the immediate attempt (respecting degree rules)
    if(pointerMode === 'add'){
      if(!wouldExceedDegreeIfAdded(chosen)){
        filled.add(chosen);
      } else {
        flash(chosen);
      }
    } else {
      // remove
      filled.delete(chosen);
    }
    updateVisuals();
    // dragAxis unknown until movement; set to null now
    dragAxis = null;
  }

  function handlePointerUp(ev){
    try{ ev.target.releasePointerCapture(ev.pointerId); } catch(e){}
    pointerActive = false;
    pointerMode = null;
    initialEdge = null;
    lastAddedEdge = null;
    startClient = null;
    dragAxis = null;
  }

  function flash(key){
    const g = svg.querySelector(`[data-edge="${key}"]`);
    if(!g) return;
    const vis = g.querySelector('.vis');
    vis.setAttribute('stroke','#d00');
    setTimeout(()=>{ vis.setAttribute('stroke', filled.has(key) ? '#000' : 'transparent'); }, 180);
  }

  // pointermove: determine axis on first significant move; step along axis
  document.addEventListener("pointermove", function(ev){
    if(!pointerActive) return;
    if(!startClient) return;
    const dx = ev.clientX - startClient.x;
    const dy = ev.clientY - startClient.y;
    // determine axis if not set and movement significant
    if(!dragAxis){
      if(Math.hypot(dx,dy) < 6) return; // ignore tiny tremble
      dragAxis = Math.abs(dx) >= Math.abs(dy) ? 'h' : 'v';
      // record initial direction sign
      // we will step based on sign of projection along axis relative to initial pointer
    }
    // compute how far along axis we've moved relative to cell size in client space
    // map movement in client pixels to viewBox units and then to cell steps
    const rect = svg.getBoundingClientRect();
    const unitPerClientX = viewBoxW / rect.width;
    const unitPerClientY = viewBoxH / rect.height;
    let step = 0;
    let sign = 0;
    if(dragAxis === 'h'){
      const moved_units = dx * unitPerClientX;
      step = Math.floor(Math.abs(moved_units) / CELL);
      sign = moved_units >= 0 ? 1 : -1;
    } else {
      const moved_units = dy * unitPerClientY;
      step = Math.floor(Math.abs(moved_units) / CELL);
      sign = moved_units >= 0 ? 1 : -1;
    }
    if(step <= 0) return;
    // starting from initialEdge, step `step` times, adding/removing edges along axis in direction `sign`
    let base = parseKey(initialEdge);
    // base r,c,d correspond to the initial edge; we must step from that index
    for(let s=1; s<=step; s++){
      let keyToAct = null;
      if(base.d === 'h' && dragAxis === 'h'){
        const newC = base.c + sign * s;
        const newR = base.r;
        if(newC < 0 || newC >= COLS) break;
        keyToAct = edgeKey(newR, newC, 'h');
      } else if(base.d === 'v' && dragAxis === 'v'){
        const newR = base.r + sign * s;
        const newC = base.c;
        if(newR < 0 || newR >= ROWS) break;
        keyToAct = edgeKey(newR, newC, 'v');
      } else if(base.d === 'h' && dragAxis === 'v'){
        // user started on horizontal but dragged vertically; convert stepping along column
        // choose vertical edges adjacent to the midpoint column
        // map to vertical at column = base.c or base.c+1 depending on horizontal position
        const colCandidate = (sign >= 0) ? base.c + 0 : base.c; // keep conservative mapping
        const newR = base.r + sign * s;
        const newC = base.c; // conservative
        if(newR < 0 || newR >= ROWS) break;
        keyToAct = edgeKey(newR, newC, 'v');
      } else if(base.d === 'v' && dragAxis === 'h'){
        // started vertical but dragging horizontal: choose horizontal edges adjacent
        const newC = base.c + sign * s;
        const newR = base.r;
        if(newC < 0 || newC >= COLS) break;
        keyToAct = edgeKey(newR, newC, 'h');
      }
      if(!keyToAct) continue;
      // avoid repeating the same edge multiple times if lastAddedEdge already at or beyond it
      // For simplicity, allow idempotent ops: adding when already present does nothing
      if(pointerMode === 'add'){
        if(!filled.has(keyToAct)){
          if(!wouldExceedDegreeIfAdded(keyToAct)){
            filled.add(keyToAct);
            lastAddedEdge = keyToAct;
          } else {
            flash(keyToAct);
          }
        }
      } else if(pointerMode === 'remove'){
        if(filled.has(keyToAct)){
          filled.delete(keyToAct);
          lastAddedEdge = keyToAct;
        }
      }
    }
    updateVisuals();
  }, {passive:true});

  // helper: decide if adding this would exceed degree > 2
  function wouldExceedDegreeIfAdded(key){
    if(filled.has(key)) return false;
    const eps = endpointsOf(key);
    for(const v of eps){
      if(vertexDegree(v) >= 2) return true;
    }
    return false;
  }

  // vertexDegree uses current filled set
  function vertexDegree(v){
    const vr=v.r, vc=v.c;
    let deg=0;
    if(vc-1 >= 0 && filled.has(edgeKey(vr,vc-1,'h'))) deg++;
    if(vc <= COLS-1 && filled.has(edgeKey(vr,vc,'h'))) deg++;
    if(vr-1 >= 0 && filled.has(edgeKey(vr-1,vc,'v'))) deg++;
    if(vr <= ROWS-1 && filled.has(edgeKey(vr,vc,'v'))) deg++;
    return deg;
  }

  // simple flash helper for blocked adds
  function flash(key){
    const g = svg.querySelector(`[data-edge="${key}"]`);
    if(!g) return;
    const vis = g.querySelector('.vis');
    vis.setAttribute('stroke','#d00');
    setTimeout(()=>{ vis.setAttribute('stroke', filled.has(key) ? '#000' : 'transparent'); }, 180);
  }

  // double-tap zoom and pinch-to-zoom (unchanged)
  let lastTap = 0;
  document.addEventListener("touchend", function(){
    const now = Date.now();
    if(now - lastTap < 300){
      const cur = svg.style.transform ? parseFloat(svg.style.transform.replace("scale(","")) : 1;
      svg.style.transformOrigin = "0 0";
      svg.style.transform = `scale(${cur===1?2:1})`;
    }
    lastTap = now;
  }, {passive:true});

  let lastDist = null;
  document.addEventListener("touchmove", function(e){
    if(e.touches && e.touches.length === 2){
      e.preventDefault();
      const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      if(lastDist){
        const cur = svg.style.transform ? parseFloat(svg.style.transform.replace("scale(","")) : 1;
        const next = Math.max(0.5, Math.min(4, cur * (d / lastDist)));
        svg.style.transformOrigin = "0 0";
        svg.style.transform = `scale(${next})`;
      }
      lastDist = d;
    }
  }, {passive:false});
  document.addEventListener("touchend", function(){ lastDist = null; }, {passive:true});

  // initial visual update
  updateVisuals();

  console.log("Slitherlink board ready (directional drag with degree constraint).");

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
