import streamlit as st
from streamlit.components.v1 import html
import json

st.set_page_config(page_title="Slitherlink Board", layout="wide")
st.title("Slitherlink Board")

rows = st.sidebar.number_input("Rows", 3, 20, 7)
cols = st.sidebar.number_input("Columns", 3, 20, 7)
cell_px = st.sidebar.number_input("Cell size (px)", 30, 120, 56)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=4.0">
<style>
html,body { margin:0; padding:0; }
svg { touch-action: none; user-select:none; }
</style>
</head>
<body>
<div id="root"></div>

<script>
const ROWS = __ROWS__;
const COLS = __COLS__;
const CELL = __CELL__;

const margin = 10;
let scale = 1;
let lastTap = 0;
let filled = new Set();

function edgeKey(r,c,d){ return r+","+c+","+d; }

const svgNS = "http://www.w3.org/2000/svg";
const width = COLS*CELL + margin*2;
const height = ROWS*CELL + margin*2;

const svg = document.createElementNS(svgNS,"svg");
svg.setAttribute("viewBox",`0 0 ${width} ${height}`);
svg.style.width="100%";

document.getElementById("root").appendChild(svg);

function draw(){
  svg.innerHTML = "";
  for(let r=0;r<=ROWS;r++){
    for(let c=0;c<=COLS;c++){
      const dot=document.createElementNS(svgNS,"circle");
      dot.setAttribute("cx",margin+c*CELL);
      dot.setAttribute("cy",margin+r*CELL);
      dot.setAttribute("r",4);
      svg.appendChild(dot);
    }
  }

  for(let r=0;r<=ROWS;r++){
    for(let c=0;c<COLS;c++){
      const key=edgeKey(r,c,"h");
      drawEdge(key,
        margin+c*CELL,margin+r*CELL,
        margin+(c+1)*CELL,margin+r*CELL);
    }
  }

  for(let r=0;r<ROWS;r++){
    for(let c=0;c<=COLS;c++){
      const key=edgeKey(r,c,"v");
      drawEdge(key,
        margin+c*CELL,margin+r*CELL,
        margin+c*CELL,margin+(r+1)*CELL);
    }
  }
}

function drawEdge(key,x1,y1,x2,y2){
  const hit=document.createElementNS(svgNS,"line");
  hit.setAttribute("x1",x1);
  hit.setAttribute("y1",y1);
  hit.setAttribute("x2",x2);
  hit.setAttribute("y2",y2);
  hit.setAttribute("stroke","transparent");
  hit.setAttribute("stroke-width",CELL*0.6);
  hit.onclick=()=>toggle(key);
  svg.appendChild(hit);

  if(filled.has(key)){
    const vis=document.createElementNS(svgNS,"line");
    vis.setAttribute("x1",x1);
    vis.setAttribute("y1",y1);
    vis.setAttribute("x2",x2);
    vis.setAttribute("y2",y2);
    vis.setAttribute("stroke","black");
    vis.setAttribute("stroke-width",6);
    vis.setAttribute("stroke-linecap","round");
    svg.appendChild(vis);
  }
}

function toggle(key){
  if(filled.has(key)) filled.delete(key);
  else filled.add(key);
  draw();
}

svg.addEventListener("dblclick",(e)=>{
  scale = scale===1 ? 2 : 1;
  svg.style.transform = `scale(${scale})`;
});

let pinchStart=null;
svg.addEventListener("touchstart",(e)=>{
  if(e.touches.length===2){
    pinchStart=Math.hypot(
      e.touches[0].clientX-e.touches[1].clientX,
      e.touches[0].clientY-e.touches[1].clientY
    );
  }
},{passive:false});

svg.addEventListener("touchmove",(e)=>{
  if(e.touches.length===2 && pinchStart){
    e.preventDefault();
    const d=Math.hypot(
      e.touches[0].clientX-e.touches[1].clientX,
      e.touches[0].clientY-e.touches[1].clientY
    );
    scale=Math.min(4,Math.max(0.5,scale*(d/pinchStart)));
    svg.style.transform=`scale(${scale})`;
    pinchStart=d;
  }
},{passive:false});

draw();
</script>
</body>
</html>
"""

html_code = (
    HTML_TEMPLATE
    .replace("__ROWS__", str(rows))
    .replace("__COLS__", str(cols))
    .replace("__CELL__", str(cell_px))
)

html(html_code, height=700, scrolling=True)
