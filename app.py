# app.py
import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink Board", layout="wide")

# Fixed board size: 200 x 200 dots (199 x 199 cells)
ROWS = 199   # number of rows of cells
COLS = 199   # number of columns of cells
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

  // using a Set of "r,c,d" strings for edges
  const filled = new Set();

  // pointer/drag state
  let pointerActive = false;
  let pointerMode = null;    // 'add' or 'remove'
  let lastEdge = null;       // last processed edge key
  let dragDirection = null;  // 'h' or 'v' locked on initial pointerdown

  function edgeKey(r,c,d){ return r + "," + c + "," + d; }

  // parse an edge key into {r,c,d}
  function parseKey(key){
    const parts = key.split(',');
    return { r: parseInt(parts[0],10), c: parseInt(parts[1],10), d: parts[2] };
  }

  // given an edge key, return its two endpoint vertices as [v1, v2],
  // where a vertex is an object {r,c}
  function endpointsOf(key){
    const {r,c,d} = parseKey(key);
    if (d === 'h'){
      return [{r: r, c: c}, {r: r, c: c+1}];
    } else {
      return [{r: r, c: c}, {r: r+1, c: c}];
    }
  }

  // return number of incident filled edges at a given vertex {r,c}
  function vertexDegree(vertex){
    const vr = vertex.r, vc = vertex.c;
    let deg = 0;
    // check horizontal edges touching this vertex:
    // top horizontal at (vr, vc-1)? careful: horizontal edges are keyed by (r, c) for segment from (r,c) to (r,c+1)
    // incident horizontals: (vr, vc-1, 'h') and (vr, vc, 'h')
    const h1 = edgeKey(vr, vc-1, 'h');
    const h2 = edgeKey(vr, vc, 'h');
    if (vc-1 >= 0 && filled.has(h1)) deg++;
    if (vc <= COLS-1 && filled.has(h2)) deg++;
    // incident verticals: (vr-1, vc, 'v') and (vr, vc, 'v') where vertical (r,c,'v') goes (r,c)->(r+1,c)
    const v1 = edgeKey(vr-1, vc, 'v');
    const v2 = edgeKey(vr, vc, 'v');
    if (vr-1 >= 0 && filled.has(v1)) deg++;
    if (vr <= ROWS-1 && filled.has(v2)) deg++;
    return deg;
  }

  // return whether adding edge (key) would violate degree > 2 at either endpoint
  function wouldExceedDegreeIfAdded(key){
    // if edge is already present then adding isn't relevant (we won't add)
    if (filled.has(key)) return false;
    const eps = endpointsOf(key);
    for (const v of eps){
      const d = vertexDegree(v);
      if (d >= 2) return true; // adding would make it >2
    }
    return false;
  }

  // toggle but respect degree rule for adds
  function tryToggleEdge(key){
    if (filled.has(key)){
      // always allow removal
      filled.delete(key);
      update();
      return true;
    } else {
      // addition: block if it would exceed degree
      if (wouldExceedDegreeIfAdded(key)){
        // optionally flash or ignore
        flashBlocked(key);
        return false;
      }
      filled.add(key);
      update();
      return true;
    }
  }

  function flashBlocked(key){
    // brief visual feedback: make the hit line briefly red (if present)
    const g = svg.querySelector(`[data-edge="${key}"]`);
    if (!g) return;
    const vis = g.querySelector('.vis');
    const old = vis.getAttribute('stroke');
    vis.setAttribute('stroke','#d00');
    setTimeout(()=>{ // restore
      vis.setAttribute('stroke', filled.has(key) ? '#000' : 'transparent');
    }, 220);
  }

  // build SVG
  const width  = COLS * CELL + MARGIN * 2;
  const height = ROWS * CELL + MARGIN * 2;
  const svg = document.createElementNS(SVG_NS,"svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.style.width = "100%";
  svg.style.height = "auto";
  document.getElementById("root").appendChild(svg);

  // background rect
  const bg = document.createElementNS(SVG_NS,"rect");
  bg.setAttribute("x",0); bg.setAttribute("y",0);
  bg.setAttribute("width", width); bg.setAttribute("height", height);
  bg.setAttribute("fill", "transparent");
  svg.appendChild(bg);

  // draw dots (very lightweight circles)
  const dotR = 2;
  for (let r=0; r<=ROWS; r++){
    for (let c=0; c<=COLS; c++){
      const dot = document.createElementNS(SVG_NS,"circle");
      dot.setAttribute("cx", MARGIN + c*CELL);
      dot.setAttribute("cy", MARGIN + r*CELL);
      dot.setAttribute("r", dotR);
      dot.setAttribute("fill", "#000");
      svg.appendChild(dot);
    }
  }

  // helper to create edge group (visible + hit)
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

    // pointer handlers
    hit.addEventListener("pointerdown", function(ev){
      ev.preventDefault();
      try{ ev.target.setPointerCapture(ev.pointerId); } catch(e){}
      pointerActive = true;
      pointerMode = filled.has(key) ? "remove" : "add";
      // lock drag direction from this initial edge's direction
      const parts = key.split(",");
      dragDirection = parts[2]; // 'h' or 'v'
      lastEdge = key;
      // immediate toggle attempt
      tryToggleEdge(key);
    });

    hit.addEventListener("pointerup", function(ev){
      try{ ev.target.releasePointerCapture(ev.pointerId); } catch(e){}
      pointerActive = false;
      pointerMode = null;
      lastEdge = null;
      dragDirection = null;
    });

    g.appendChild(vis);
    g.appendChild(hit);
    return g;
  }

  // create all horizontal edges
  for (let r=0; r<=ROWS; r++){
    for (let c=0; c<COLS; c++){
      const x1 = MARGIN + c*CELL;
      const y  = MARGIN + r*CELL;
      const x2 = x1 + CELL;
      const key = edgeKey(r,c,'h');
      const g = createEdgeGroup(x1,y,x2,y,key);
      svg.appendChild(g);
    }
  }

  // create all vertical edges
  for (let r=0; r<ROWS; r++){
    for (let c=0; c<=COLS; c++){
      const x  = MARGIN + c*CELL;
      const y1 = MARGIN + r*CELL;
      const y2 = y1 + CELL;
      const key = edgeKey(r,c,'v');
      const g = createEdgeGroup(x,y1,x,y2,key);
      svg.appendChild(g);
    }
  }

  // pointermove: only act on edges that match dragDirection while dragging
  document.addEventListener("pointermove", function(ev){
    if(!pointerActive) return;
    // find element under pointer
    const el = document.elementFromPoint(ev.clientX, ev.clientY);
    if(!el) return;
    const g = el.closest && el.closest("[data-edge]");
    if(!g) return;
    const key = g.getAttribute("data-edge");
    if(key === lastEdge) return; // skip repeats
    // enforce same direction as initial
    const parts = key.split(",");
    const d = parts[2];
    if(d !== dragDirection) return;
    lastEdge = key;
    if(pointerMode === "add"){
      // attempt to add, but will be blocked if degree would exceed 2
      if(!filled.has(key)){
        if(!wouldExceedDegreeIfAdded(key)){
          filled.add(key);
          updateVisuals();
        } else {
          // feedback: briefly flash blocked
          flashBlocked(key);
        }
      }
    } else if(pointerMode === "remove"){
      if(filled.has(key)){
        filled.delete(key);
        updateVisuals();
      }
    }
  }, {passive:true});

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

  // small visual flash for blocked adds
  function flashBlocked(key){
    const g = svg.querySelector(`[data-edge="${key}"]`);
    if(!g) return;
    const vis = g.querySelector(".vis");
    const prev = vis.getAttribute("stroke");
    vis.setAttribute("stroke","#d00");
    setTimeout(()=>{
      vis.setAttribute("stroke", filled.has(key) ? "#000" : "transparent");
    }, 200);
  }

  // simple double-tap zoom and pinch-to-zoom
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

  // done
  console.log("Slitherlink board ready. Edges:", svg.querySelectorAll("[data-edge]").length);
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
