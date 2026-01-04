# app.py
import streamlit as st
from streamlit.components.v1 import html
import json

st.set_page_config(page_title="Slitherlink — Playable (iframe)", layout="wide")
st.title("Slitherlink — Playable (client-only)")

# Controls
cols = st.sidebar.number_input("Columns", min_value=2, max_value=20, value=7, step=1)
rows = st.sidebar.number_input("Rows", min_value=2, max_value=20, value=7, step=1)
cell_px = st.sidebar.slider("Cell size (px)", min_value=24, max_value=120, value=56)
iframe_h = 720 if max(rows, cols) <= 10 else 980

# NOTE: this version keeps everything client-side to avoid streamlit JSON/render issues.
HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=4.0" />
<style>
  html,body{height:100%;margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;-webkit-user-select:none;user-select:none}
  #wrap{box-sizing:border-box;padding:12px;height:100%;display:flex;flex-direction:column;gap:8px}
  .controls{display:flex;gap:8px;align-items:center}
  .board{flex:1 1 auto;display:flex;align-items:center;justify-content:center;overflow:hidden}
  svg{touch-action:none;display:block;max-width:100%;height:auto}
  button{padding:8px 12px;font-size:14px}
  .hint{font-size:13px;color:#444}
  .status{font-size:12px;color:#666}
  textarea{width:360px;height:120px}
</style>
</head>
<body>
<div id="wrap">
  <div class="controls">
    <div>
      <button id="clear">Clear</button>
      <label style="margin-left:10px"><input id="drag" type="checkbox" checked/> Drag-to-draw</label>
      <button id="download" style="margin-left:10px">Download JSON</button>
      <button id="showImport">Import JSON</button>
    </div>
    <div style="flex:1"></div>
    <div class="hint">Tap a gap to toggle an edge. Drag to draw. Double-tap zoom. Pinch to zoom.</div>
  </div>

  <div class="board"><div id="svgHolder" style="width:100%;max-width:980px"></div></div>

  <div class="status" id="status">Ready</div>

  <div id="importArea" style="display:none;padding-top:8px">
    <div>Paste JSON ({"rows","cols","filled_edges": [...]}) then click Apply:</div>
    <textarea id="importText"></textarea>
    <div style="margin-top:6px"><button id="applyImport">Apply</button> <button id="closeImport">Close</button></div>
  </div>
</div>

<script>
(function(){
  // placeholders replaced by Python
  var ROWS = __ROWS__;
  var COLS = __COLS__;
  var CELL = __CELL__;
  var margin = 8;
  var xmlns = "http://www.w3.org/2000/svg";
  var holder = document.getElementById('svgHolder');
  var status = document.getElementById('status');

  // internal set
  var filled = new Set();

  // load saved from localStorage (key includes dims)
  var storageKey = "slither_state_" + ROWS + "x" + COLS + "_cell" + CELL;
  (function loadSaved(){
    try{
      var raw = localStorage.getItem(storageKey);
      if(raw){
        var obj = JSON.parse(raw);
        if(obj && Array.isArray(obj.filled_edges)){
          obj.filled_edges.forEach(function(e){ filled.add(e); });
        }
      }
    }catch(e){ console.warn("loadSaved error", e); }
  })();

  function edgeKey(r,c,d){ return r + "," + c + "," + d; }

  function build(){
    var width = COLS*CELL + margin*2;
    var height = ROWS*CELL + margin*2;
    var svg = document.createElementNS(xmlns,"svg");
    svg.setAttribute("viewBox","0 0 " + width + " " + height);
    svg.setAttribute("preserveAspectRatio","xMidYMid meet");
    svg.style.width = "100%";
    svg.style.height = "auto";
    svg.id = "slitherSvg";

    var bg = document.createElementNS(xmlns,"rect");
    bg.setAttribute("x",0); bg.setAttribute("y",0);
    bg.setAttribute("width", width); bg.setAttribute("height", height);
    bg.setAttribute("fill","transparent");
    svg.appendChild(bg);

    // dots
    var dotR = Math.max(3, Math.round(CELL*0.08));
    for(var r=0;r<=ROWS;r++){
      for(var c=0;c<=COLS;c++){
        var dot = document.createElementNS(xmlns,"circle");
        dot.setAttribute("cx", margin + c*CELL);
        dot.setAttribute("cy", margin + r*CELL);
        dot.setAttribute("r", dotR);
        dot.setAttribute("fill", "#111");
        svg.appendChild(dot);
      }
    }

    // create hit lines and visible lines grouped
    for(var r=0;r<=ROWS;r++){
      for(var c=0;c<COLS;c++){
        var x1 = margin + c*CELL, y = margin + r*CELL, x2 = x1 + CELL;
        var g = document.createElementNS(xmlns,"g");
        g.setAttribute("data-edge", edgeKey(r,c,'h'));
        var vis = document.createElementNS(xmlns,"line");
        vis.setAttribute("x1", x1); vis.setAttribute("y1", y); vis.setAttribute("x2", x2); vis.setAttribute("y2", y);
        vis.setAttribute("stroke-linecap","round"); vis.setAttribute("stroke-width",6); vis.setAttribute("class","vis");
        var hit = document.createElementNS(xmlns,"line");
        hit.setAttribute("x1", x1); hit.setAttribute("y1", y); hit.setAttribute("x2", x2); hit.setAttribute("y2", y);
        hit.setAttribute("stroke-linecap","round"); hit.setAttribute("stroke-width", CELL*0.6);
        hit.setAttribute("stroke","transparent"); hit.style.cursor="pointer";
        hit.addEventListener("pointerdown", onDown);
        hit.addEventListener("pointerup", onUp);
        g.appendChild(vis); g.appendChild(hit); svg.appendChild(g);
      }
    }
    for(var r=0;r<ROWS;r++){
      for(var c=0;c<=COLS;c++){
        var x = margin + c*CELL, y1 = margin + r*CELL, y2 = y1 + CELL;
        var g = document.createElementNS(xmlns,"g");
        g.setAttribute("data-edge", edgeKey(r,c,'v'));
        var vis = document.createElementNS(xmlns,"line");
        vis.setAttribute("x1", x); vis.setAttribute("y1", y1); vis.setAttribute("x2", x); vis.setAttribute("y2", y2);
        vis.setAttribute("stroke-linecap","round"); vis.setAttribute("stroke-width",6); vis.setAttribute("class","vis");
        var hit = document.createElementNS(xmlns,"line");
        hit.setAttribute("x1", x); hit.setAttribute("y1", y1); hit.setAttribute("x2", x); hit.setAttribute("y2", y2);
        hit.setAttribute("stroke-linecap","round"); hit.setAttribute("stroke-width", CELL*0.6);
        hit.setAttribute("stroke","transparent"); hit.style.cursor="pointer";
        hit.addEventListener("pointerdown", onDown);
        hit.addEventListener("pointerup", onUp);
        g.appendChild(vis); g.appendChild(hit); svg.appendChild(g);
      }
    }

    update(svg);
    return svg;
  }

  var pointerActive=false, pointerMode=null, lastEdge=null;

  function onDown(ev){
    ev.preventDefault();
    try{ ev.target.setPointerCapture(ev.pointerId); }catch(e){}
    pointerActive = true;
    var g = ev.target.closest && ev.target.closest("[data-edge]");
    if(!g) return;
    var key = g.getAttribute("data-edge");
    pointerMode = filled.has(key) ? "remove" : "add";
    toggle(key);
    lastEdge = key;
  }
  function onUp(ev){
    try{ ev.target.releasePointerCapture(ev.pointerId); }catch(e){}
    pointerActive=false; pointerMode=null; lastEdge=null;
  }

  document.addEventListener("pointermove", function(ev){
    if(!pointerActive) return;
    if(!document.getElementById("drag").checked) return;
    var el = document.elementFromPoint(ev.clientX, ev.clientY);
    if(!el) return;
    var g = el.closest && el.closest("[data-edge]");
    if(!g) return;
    var key = g.getAttribute("data-edge");
    if(key === lastEdge) return;
    lastEdge = key;
    if(pointerMode === "add"){
      if(!filled.has(key)){ filled.add(key); update(document.getElementById("slitherSvg")); }
    } else if(pointerMode === "remove"){
      if(filled.has(key)){ filled.delete(key); update(document.getElementById("slitherSvg")); }
    }
  }, {passive:true});

  function toggle(key){
    if(filled.has(key)) filled.delete(key); else filled.add(key);
    update(document.getElementById("slitherSvg"));
  }

  function update(svg){
    if(!svg) return;
    var groups = svg.querySelectorAll("[data-edge]");
    groups.forEach(function(g){
      var k = g.getAttribute("data-edge");
      var vis = g.querySelector(".vis");
      if(filled.has(k)){ vis.setAttribute("stroke","#111"); vis.setAttribute("opacity","1"); }
      else { vis.setAttribute("stroke","transparent"); vis.setAttribute("opacity","0"); }
    });
    status.textContent = "Edges: " + filled.size;
    // persist
    try{
      var serial = { rows: ROWS, cols: COLS, filled_edges: Array.from(filled) };
      localStorage.setItem(storageKey, JSON.stringify(serial));
    }catch(e){ console.warn("save err", e); }
  }

  // Download/export
  document.getElementById("download").addEventListener("click", function(){
    var payload = { rows: ROWS, cols: COLS, filled_edges: Array.from(filled) };
    var blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = "slither_state.json"; document.body.appendChild(a); a.click();
    setTimeout(function(){ URL.revokeObjectURL(url); a.remove(); }, 1500);
  });

  // Import UI
  document.getElementById("showImport").addEventListener("click", function(){
    document.getElementById("importArea").style.display = "block";
  });
  document.getElementById("closeImport").addEventListener("click", function(){
    document.getElementById("importArea").style.display = "none";
  });
  document.getElementById("applyImport").addEventListener("click", function(){
    var txt = document.getElementById("importText").value;
    try{
      var obj = JSON.parse(txt);
      if(obj && Array.isArray(obj.filled_edges)){
        filled.clear(); obj.filled_edges.forEach(function(e){ filled.add(e); });
        update(document.getElementById("slitherSvg"));
        document.getElementById("importArea").style.display = "none";
      } else {
        alert("JSON must include filled_edges array");
      }
    }catch(e){ alert("Invalid JSON: " + e); }
  });

  // Clear
  document.getElementById("clear").addEventListener("click", function(){
    if(confirm("Clear all drawn lines?")){ filled.clear(); update(document.getElementById("slitherSvg")); }
  });

  // basic gestures: double-tap to toggle zoom, pinch-to-scale (centerless, simple)
  var lastTap = 0; document.addEventListener("touchend", function(){
    var now = Date.now();
    if(now - lastTap < 300){
      var svg = document.getElementById("slitherSvg");
      if(svg){
        var cur = svg.style.transform ? parseFloat(svg.style.transform.replace("scale(","").replace(")","")) : 1;
        var next = Math.abs(cur - 1) < 0.01 ? 2 : 1;
        svg.style.transformOrigin = "0 0"; svg.style.transform = "scale(" + next + ")";
      }
    }
    lastTap = now;
  }, {passive:true});

  var lastDist = null;
  document.addEventListener("touchmove", function(e){
    if(e.touches && e.touches.length === 2){
      e.preventDefault();
      var d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      if(lastDist){
        var svg = document.getElementById("slitherSvg");
        if(svg){
          var cur = svg.style.transform ? parseFloat(svg.style.transform.replace("scale(","").replace(")","")) : 1;
          var next = Math.max(0.5, Math.min(4, cur * (d / lastDist)));
          svg.style.transformOrigin = "0 0"; svg.style.transform = "scale(" + next + ")";
        }
      }
      lastDist = d;
    }
  }, {passive:false});
  document.addEventListener("touchend", function(){ lastDist = null; }, {passive:true});

  // initial render
  holder.innerHTML = ""; holder.appendChild(build());

})(); // end
</script>
</body>
</html>
"""

# Fill placeholders safely
html_code = (
    HTML
    .replace("__ROWS__", str(rows))
    .replace("__COLS__", str(cols))
    .replace("__CELL__", str(cell_px))
)

# Render iframe (no messages back)
html(html_code, height=iframe_h, scrolling=True)

st.markdown("---")
st.info("This board is client-side. Use the Download button inside the board to export JSON, or Import to paste a state. No server round-trips are performed for each tap.")
