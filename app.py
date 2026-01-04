# app.py
import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink Board", layout="wide")

# Fixed board size: 200 x 200 dots (199 x 199 cells)
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
  const ROWS = __ROWS__;
  const COLS = __COLS__;
  const CELL = __CELL__;
  const MARGIN = 6;
  const SVG_NS = "http://www.w3.org/2000/svg";

  const filled = new Set();

  // pointer state
  let pointerActive = false;
  let pointerMode = null;       // 'add' or 'remove'
  let anchorEdge = null;        // key of the anchor edge for stepping
  let activeAxis = null;        // 'h' or 'v' - current dominant axis (can change)
  let anchorClient = null;      // client {x,y} used as anchor for measuring steps
  let lastStep = 0;             // steps already applied since anchorClient
  let viewBoxW = null, viewBoxH = null;

  function edgeKey(r,c,d){ return r + "," + c + "," + d; }
  function parseKey(key){ const p = key.split(','); return {r:parseInt(p[0],10), c:parseInt(p[1],10), d:p[2]}; }

  function endpointsOf(key){
    const {r,c,d} = parseKey(key);
    return d === 'h' ? [{r:r,c:c},{r:r,c:c+1}] : [{r:r,c:c},{r:r+1,c:c}];
  }

  function vertexDegree(v){
    const vr=v.r, vc=v.c;
    let deg=0;
    if(vc-1 >= 0 && filled.has(edgeKey(vr,vc-1,'h'))) deg++;
    if(vc <= COLS-1 && filled.has(edgeKey(vr,vc,'h'))) deg++;
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

    hit.addEventListener("pointerdown", handlePointerDown);
    hit.addEventListener("pointerup", handlePointerUp);

    g.appendChild(vis); g.appendChild(hit);
    return g;
  }

  for(let r=0;r<=ROWS;r++){
    for(let c=0;c<COLS;c++){
      const x1 = MARGIN + c*CELL, y = MARGIN + r*CELL, x2 = x1 + CELL;
      svg.appendChild(createEdgeGroup(x1,y,x2,y, edgeKey(r,c,'h')));
    }
  }
  for(let r=0;r<ROWS;r++){
    for(let c=0;c<=COLS;c++){
      const x = MARGIN + c*CELL, y1 = MARGIN + r*CELL, y2 = y1 + CELL;
      svg.appendChild(createEdgeGroup(x,y1,x,y2, edgeKey(r,c,'v')));
    }
  }

  function updateVisuals(){
    svg.querySelectorAll("[data-edge]").forEach(function(g){
      const k = g.getAttribute("data-edge");
      const vis = g.querySelector(".vis");
      if(filled.has(k)) vis.setAttribute("stroke","#000");
      else vis.setAttribute("stroke","transparent");
    });
  }

  function clientToViewBox(clientX, clientY){
    const rect = svg.getBoundingClientRect();
    const fx = (clientX - rect.left) / rect.width;
    const fy = (clientY - rect.top) / rect.height;
    return { x: fx * viewBoxW, y: fy * viewBoxH };
  }

  function nearestEdgeKeyForClient(clientX, clientY){
    const pt = clientToViewBox(clientX, clientY);
    const sx = pt.x, sy = pt.y;
    const r_h = Math.round((sy - MARGIN) / CELL);
    const c_h = Math.floor((sx - MARGIN) / CELL);
    let dist_h = Infinity, key_h = null;
    if(r_h >= 0 && r_h <= ROWS && c_h >= 0 && c_h < COLS){
      const hx = MARGIN + (c_h + 0.5) * CELL;
      const hy = MARGIN + r_h * CELL;
      dist_h = Math.hypot(sx - hx, sy - hy);
      key_h = edgeKey(r_h, c_h, 'h');
    }
    const c_v = Math.round((sx - MARGIN) / CELL);
    const r_v = Math.floor((sy - MARGIN) / CELL);
    let dist_v = Infinity, key_v = null;
    if(c_v >= 0 && c_v <= COLS && r_v >= 0 && r_v < ROWS){
      const vx = MARGIN + c_v * CELL;
      const vy = MARGIN + (r_v + 0.5) * CELL;
      dist_v = Math.hypot(sx - vx, sy - vy);
      key_v = edgeKey(r_v, c_v, 'v');
    }
    if(dist_h <= dist_v) return key_h;
    return key_v;
  }

  // anchor adjustment when axis switches: choose anchorEdge and anchorClient based on current pointer
  function setAnchorForCurrentPointer(clientX, clientY){
    anchorEdge = nearestEdgeKeyForClient(clientX, clientY);
    anchorClient = { x: clientX, y: clientY };
    lastStep = 0;
  }

  function handlePointerDown(ev){
    ev.preventDefault();
    try{ ev.target.setPointerCapture(ev.pointerId); } catch(e){}
    pointerActive = true;
    // set initial anchor and mode
    setAnchorForCurrentPointer(ev.clientX, ev.clientY);
    const chosen = anchorEdge;
    if(!chosen) return;
    pointerMode = filled.has(chosen) ? 'remove' : 'add';
    // immediate attempt
    if(pointerMode === 'add'){
      if(!wouldExceedDegreeIfAdded(chosen)) filled.add(chosen);
      else flashBlocked(chosen);
    } else {
      filled.delete(chosen);
    }
    updateVisuals();
    activeAxis = null; // will be set by first significant move
  }

  function handlePointerUp(ev){
    try{ ev.target.releasePointerCapture(ev.pointerId); } catch(e){}
    pointerActive = false;
    pointerMode = null;
    anchorEdge = null;
    anchorClient = null;
    activeAxis = null;
    lastStep = 0;
  }

  // choose anchor index when base orientation differs from axis
  function columnForHorizontalBase(base, anchorView){
    const midX = MARGIN + (base.c + 0.5) * CELL;
    return (anchorView.x <= midX) ? base.c : base.c + 1;
  }
  function rowForVerticalBase(base, anchorView){
    const midY = MARGIN + (base.r + 0.5) * CELL;
    return (anchorView.y <= midY) ? base.r : base.r + 1;
  }

  // pointermove: dynamically determine axis; if axis changes, re-anchor at current pointer position
  document.addEventListener("pointermove", function(ev){
    if(!pointerActive || !anchorClient || !anchorEdge) return;
    const dx = ev.clientX - anchorClient.x;
    const dy = ev.clientY - anchorClient.y;

    // choose current dominant axis based on movement from anchorClient
    const movementThreshold = 6; // pixels
    if(Math.hypot(dx,dy) < movementThreshold) return;

    const currentAxis = Math.abs(dx) >= Math.abs(dy) ? 'h' : 'v';
    // if axis changed, re-anchor at current pointer so stepping continues from here
    if(activeAxis !== currentAxis){
      activeAxis = currentAxis;
      setAnchorForCurrentPointer(ev.clientX, ev.clientY);
      // recompute pointerMode relative to new anchor
      pointerMode = filled.has(anchorEdge) ? 'remove' : 'add';
      return; // wait for next move to create steps from the fresh anchor
    }

    // compute how many steps from anchorClient to current pointer along activeAxis (in view units)
    const rect = svg.getBoundingClientRect();
    const unitX = viewBoxW / rect.width;
    const unitY = viewBoxH / rect.height;
    let movedUnits = (activeAxis === 'h') ? (ev.clientX - anchorClient.x) * unitX : (ev.clientY - anchorClient.y) * unitY;
    const sign = movedUnits >= 0 ? 1 : -1;
    const stepsNow = Math.floor(Math.abs(movedUnits) / CELL);
    if(stepsNow <= lastStep) return;
    const newSteps = stepsNow - lastStep;
    lastStep = stepsNow;

    const base = parseKey(anchorEdge);
    const anchorView = clientToViewBox(anchorClient.x, anchorClient.y);

    for(let s=1; s<=newSteps; s++){
      let keyToAct = null;
      const stepIndex = (lastStep - newSteps) + s; // steps from anchor (this recomputes safely)
      if(base.d === activeAxis){
        if(activeAxis === 'h'){
          const newC = base.c + sign * stepIndex;
          const newR = base.r;
          if(newC < 0 || newC >= COLS) break;
          keyToAct = edgeKey(newR, newC, 'h');
        } else {
          const newR = base.r + sign * stepIndex;
          const newC = base.c;
          if(newR < 0 || newR >= ROWS) break;
          keyToAct = edgeKey(newR, newC, 'v');
        }
      } else {
        // different orientation: map intelligently using anchorView
        if(base.d === 'h' && activeAxis === 'v'){
          const col = columnForHorizontalBase(base, anchorView);
          const newR = base.r + sign * stepIndex;
          if(newR < 0 || newR >= ROWS) break;
          if(col < 0 || col > COLS) break;
          keyToAct = edgeKey(newR, col, 'v');
        } else if(base.d === 'v' && activeAxis === 'h'){
          const row = rowForVerticalBase(base, anchorView);
          const newC = base.c + sign * stepIndex;
          if(newC < 0 || newC >= COLS) break;
          if(row < 0 || row > ROWS) break;
          keyToAct = edgeKey(row, newC, 'h');
        }
      }

      if(!keyToAct) continue;

      if(pointerMode === 'add'){
        if(!filled.has(keyToAct)){
          if(!wouldExceedDegreeIfAdded(keyToAct)){
            filled.add(keyToAct);
          } else {
            flashBlocked(keyToAct);
          }
        }
      } else if(pointerMode === 'remove'){
        if(filled.has(keyToAct)){
          filled.delete(keyToAct);
        }
      }
    }

    updateVisuals();
  }, {passive:true});

  function flashBlocked(key){
    const g = svg.querySelector(`[data-edge="${key}"]`);
    if(!g) return;
    const vis = g.querySelector('.vis');
    vis.setAttribute('stroke','#d00');
    setTimeout(()=>{ vis.setAttribute('stroke', filled.has(key) ? '#000' : 'transparent'); }, 200);
  }

  // double-tap zoom and pinch-to-zoom
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

  // initial render
  updateVisuals();
  console.log("Slitherlink board ready (axis-following drag).");
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
