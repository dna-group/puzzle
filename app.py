# app.py
import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink Board", layout="wide")

# Fixed board size: 200 x 200 dots
ROWS = 199   # cells
COLS = 199   # cells
CELL_PX = 16 # small to fit large board; increase carefully
IFRAME_HEIGHT = 1200

HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=4.0"/>
<style>
  html,body{margin:0;padding:0;height:100%;overflow:hidden}
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
  let pointerActive = false;
  let pointerMode = null;
  let lastEdge = null;

  function edgeKey(r,c,d){ return r + "," + c + "," + d; }

  const width  = COLS * CELL + MARGIN * 2;
  const height = ROWS * CELL + MARGIN * 2;

  const svg = document.createElementNS(SVG_NS,"svg");
  svg.setAttribute("viewBox",`0 0 ${width} ${height}`);
  svg.style.width = "100%";
  svg.style.height = "auto";
  document.getElementById("root").appendChild(svg);

  // background
  const bg = document.createElementNS(SVG_NS,"rect");
  bg.setAttribute("x",0); bg.setAttribute("y",0);
  bg.setAttribute("width",width); bg.setAttribute("height",height);
  bg.setAttribute("fill","transparent");
  svg.appendChild(bg);

  // dots
  const dotR = 2;
  for(let r=0;r<=ROWS;r++){
    for(let c=0;c<=COLS;c++){
      const dot = document.createElementNS(SVG_NS,"circle");
      dot.setAttribute("cx", MARGIN + c*CELL);
      dot.setAttribute("cy", MARGIN + r*CELL);
      dot.setAttribute("r", dotR);
      dot.setAttribute("fill","#000");
      svg.appendChild(dot);
    }
  }

  function addEdge(x1,y1,x2,y2,key){
    const g = document.createElementNS(SVG_NS,"g");
    g.dataset.edge = key;

    const vis = document.createElementNS(SVG_NS,"line");
    vis.setAttribute("x1",x1); vis.setAttribute("y1",y1);
    vis.setAttribute("x2",x2); vis.setAttribute("y2",y2);
    vis.setAttribute("stroke-width",3);
    vis.setAttribute("stroke-linecap","round");
    vis.classList.add("vis");

    const hit = document.createElementNS(SVG_NS,"line");
    hit.setAttribute("x1",x1); hit.setAttribute("y1",y1);
    hit.setAttribute("x2",x2); hit.setAttribute("y2",y2);
    hit.setAttribute("stroke-width",CELL*0.6);
    hit.setAttribute("stroke","transparent");
    hit.style.cursor = "pointer";

    hit.addEventListener("pointerdown", e=>{
      e.preventDefault();
      hit.setPointerCapture(e.pointerId);
      pointerActive = true;
      pointerMode = filled.has(key) ? "remove" : "add";
      toggle(key);
      lastEdge = key;
    });

    hit.addEventListener("pointerup", e=>{
      hit.releasePointerCapture(e.pointerId);
      pointerActive = false;
      pointerMode = null;
      lastEdge = null;
    });

    g.appendChild(vis);
    g.appendChild(hit);
    svg.appendChild(g);
  }

  // horizontal edges
  for(let r=0;r<=ROWS;r++){
    for(let c=0;c<COLS;c++){
      const x1 = MARGIN + c*CELL;
      const y  = MARGIN + r*CELL;
      addEdge(x1,y,x1+CELL,y,edgeKey(r,c,"h"));
    }
  }

  // vertical edges
  for(let r=0;r<ROWS;r++){
    for(let c=0;c<=COLS;c++){
      const x  = MARGIN + c*CELL;
      const y1 = MARGIN + r*CELL;
      addEdge(x,y1,x,y1+CELL,edgeKey(r,c,"v"));
    }
  }

  document.addEventListener("pointermove", e=>{
    if(!pointerActive) return;
    const el = document.elementFromPoint(e.clientX,e.clientY);
    if(!el) return;
    const g = el.closest && el.closest("[data-edge]");
    if(!g) return;
    const key = g.dataset.edge;
    if(key === lastEdge) return;
    lastEdge = key;
    if(pointerMode === "add" && !filled.has(key)){ filled.add(key); update(); }
    if(pointerMode === "remove" && filled.has(key)){ filled.delete(key); update(); }
  }, {passive:true});

  function toggle(key){
    if(filled.has(key)) filled.delete(key);
    else filled.add(key);
    update();
  }

  function update(){
    svg.querySelectorAll("[data-edge]").forEach(g=>{
      const vis = g.querySelector(".vis");
      if(filled.has(g.dataset.edge)){
        vis.setAttribute("stroke","#000");
      } else {
        vis.setAttribute("stroke","transparent");
      }
    });
  }

  // double-tap zoom
  let lastTap = 0;
  document.addEventListener("touchend", ()=>{
    const now = Date.now();
    if(now-lastTap < 300){
      const cur = svg.style.transform ? parseFloat(svg.style.transform.replace("scale(","")) : 1;
      svg.style.transformOrigin = "0 0";
      svg.style.transform = `scale(${cur===1?2:1})`;
    }
    lastTap = now;
  }, {passive:true});

  // pinch zoom
  let lastDist = null;
  document.addEventListener("touchmove", e=>{
    if(e.touches.length===2){
      e.preventDefault();
      const d = Math.hypot(
        e.touches[0].clientX-e.touches[1].clientX,
        e.touches[0].clientY-e.touches[1].clientY
      );
      if(lastDist){
        const cur = svg.style.transform ? parseFloat(svg.style.transform.replace("scale(","")) : 1;
        const next = Math.max(0.5,Math.min(4,cur*(d/lastDist)));
        svg.style.transformOrigin = "0 0";
        svg.style.transform = `scale(${next})`;
      }
      lastDist = d;
    }
  }, {passive:false});
  document.addEventListener("touchend", ()=>lastDist=null, {passive:true});

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
