import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(layout="wide")

html_code = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Slitherlink</title>
<style>
  html,body {
    height:100%;
    margin:0;
    background:#000;
  }
  #container {
    position:relative;
    height:100vh;
    width:100vw;
    background:#000;
    overflow:hidden;
  }
  canvas {
    display:block;
    background:#000;
    touch-action:none;
  }
</style>
</head>
<body>
<div id="container">
  <canvas id="mainCanvas"></canvas>
</div>

<script>
(() => {
  const COLS = 128;
  const ROWS = 178;
  const DOT_SPACING = 9;
  const DOT_RADIUS = 1.0;
  const EDGE_HIT_RADIUS = 10;
  const INITIAL_ZOOM = 3.2;

  // --- black border margin (prevents clipping) ---
  const BORDER = DOT_SPACING * 2;

  const gridWidth  = (COLS - 1) * DOT_SPACING;
  const gridHeight = (ROWS - 1) * DOT_SPACING;

  const fullWidth  = gridWidth  + BORDER * 2;
  const fullHeight = gridHeight + BORDER * 2;

  const container = document.getElementById("container");
  const canvas = document.getElementById("mainCanvas");
  const ctx = canvas.getContext("2d", { alpha:false });

  let zoom = INITIAL_ZOOM;
  let viewport = { cx: fullWidth/2, cy: fullHeight/2, w: 800/zoom, h: 600/zoom };

  const edges = new Map();
  const degree = new Map();

  const nodeKey = (x,y) => `${x},${y}`;
  const edgeKey = (a,b) =>
    nodeKey(a.x,a.y) < nodeKey(b.x,b.y)
      ? nodeKey(a.x,a.y)+"|"+nodeKey(b.x,b.y)
      : nodeKey(b.x,b.y)+"|"+nodeKey(a.x,a.y);

  function addEdge(a,b){
    const k = edgeKey(a,b);
    if (edges.has(k)) return false;
    if ((degree.get(nodeKey(a.x,a.y))||0) >= 2) return false;
    if ((degree.get(nodeKey(b.x,b.y))||0) >= 2) return false;
    edges.set(k,true);
    degree.set(nodeKey(a.x,a.y),(degree.get(nodeKey(a.x,a.y))||0)+1);
    degree.set(nodeKey(b.x,b.y),(degree.get(nodeKey(b.x,b.y))||0)+1);
    return true;
  }

  function removeEdge(a,b){
    const k = edgeKey(a,b);
    if (!edges.has(k)) return;
    edges.delete(k);
    degree.set(nodeKey(a.x,a.y),degree.get(nodeKey(a.x,a.y))-1);
    degree.set(nodeKey(b.x,b.y),degree.get(nodeKey(b.x,b.y))-1);
  }

  function fullToScreen(x,y){
    const l = viewport.cx - viewport.w/2;
    const t = viewport.cy - viewport.h/2;
    return {
      x:(x-l)/viewport.w*canvas.width,
      y:(y-t)/viewport.h*canvas.height
    };
  }

  function screenToFull(x,y){
    const l = viewport.cx - viewport.w/2;
    const t = viewport.cy - viewport.h/2;
    return {
      x:l + x/canvas.width*viewport.w,
      y:t + y/canvas.height*viewport.h
    };
  }

  function resize(){
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    viewport.w = canvas.width/zoom;
    viewport.h = canvas.height/zoom;
  }

  function draw(){
    ctx.fillStyle="#000";
    ctx.fillRect(0,0,canvas.width,canvas.height);

    ctx.fillStyle="#fff";
    const r = Math.max(0.6,DOT_RADIUS*zoom/2);

    for(let y=0;y<ROWS;y++){
      for(let x=0;x<COLS;x++){
        const fx = BORDER + x*DOT_SPACING;
        const fy = BORDER + y*DOT_SPACING;
        const p = fullToScreen(fx,fy);
        ctx.beginPath();
        ctx.arc(p.x,p.y,r,0,Math.PI*2);
        ctx.fill();
      }
    }

    ctx.strokeStyle="#fff";
    ctx.lineWidth=Math.max(3,zoom*1.1);
    ctx.lineCap="round";
    ctx.beginPath();
    edges.forEach((_,k)=>{
      const [a,b]=k.split("|").map(s=>s.split(",").map(Number));
      const p1=fullToScreen(BORDER+a[0]*DOT_SPACING,BORDER+a[1]*DOT_SPACING);
      const p2=fullToScreen(BORDER+b[0]*DOT_SPACING,BORDER+b[1]*DOT_SPACING);
      ctx.moveTo(p1.x,p1.y);
      ctx.lineTo(p2.x,p2.y);
    });
    ctx.stroke();
  }

  function nearestEdge(fx,fy){
    const gx=(fx-BORDER)/DOT_SPACING;
    const gy=(fy-BORDER)/DOT_SPACING;
    const ix=Math.round(gx), iy=Math.round(gy);
    let best={d:1e9};
    for(let dx=-1;dx<=1;dx++){
      for(let dy=-1;dy<=1;dy++){
        const x=ix+dx,y=iy+dy;
        if(x>=0&&x+1<COLS&&y>=0&&y<ROWS){
          const mx=BORDER+(x+0.5)*DOT_SPACING,my=BORDER+y*DOT_SPACING;
          const d=(mx-fx)**2+(my-fy)**2;
          if(d<best.d) best={d,a:{x,y},b:{x:x+1,y}};
        }
        if(x>=0&&x<COLS&&y>=0&&y+1<ROWS){
          const mx=BORDER+x*DOT_SPACING,my=BORDER+(y+0.5)*DOT_SPACING;
          const d=(mx-fx)**2+(my-fy)**2;
          if(d<best.d) best={d,a:{x,y},b:{x,y:y+1}};
        }
      }
    }
    return best;
  }

  let down=false,start=null,drag=false;
  canvas.onpointerdown=e=>{
    down=true;drag=false;
    start={x:e.clientX,y:e.clientY,cx:viewport.cx,cy:viewport.cy};
  };
  window.onpointermove=e=>{
    if(!down)return;
    const dx=e.clientX-start.x,dy=e.clientY-start.y;
    if(Math.hypot(dx,dy)>6)drag=true;
    if(drag){
      viewport.cx=start.cx-dx*(viewport.w/canvas.width);
      viewport.cy=start.cy-dy*(viewport.h/canvas.height);
      draw();
    }
  };
  canvas.onpointerup=e=>{
    down=false;
    if(!drag){
      const r=canvas.getBoundingClientRect();
      const f=screenToFull(e.clientX-r.left,e.clientY-r.top);
      const n=nearestEdge(f.x,f.y);
      if(Math.sqrt(n.d)*zoom<EDGE_HIT_RADIUS){
        const k=edgeKey(n.a,n.b);
        edges.has(k)?removeEdge(n.a,n.b):addEdge(n.a,n.b);
        draw();
      }
    }
  };

  window.onresize=()=>{resize();draw();};
  resize();
  draw();
})();
</script>
</body>
</html>
"""

html(html_code, height=900)
