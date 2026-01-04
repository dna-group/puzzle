# app.py
import streamlit as st
from streamlit.components.v1 import html
import json

st.set_page_config(page_title="Slitherlink — Tap edges", layout="wide")
st.title("Slitherlink — Tap edges (tap the gap between dots)")

# Grid controls
cols = st.sidebar.number_input("Columns (X)", min_value=2, max_value=40, value=7, step=1)
rows = st.sidebar.number_input("Rows (Y)", min_value=2, max_value=40, value=7, step=1)
cell_px = st.sidebar.slider("Cell size (px)", min_value=24, max_value=120, value=56)
iframe_height = 640 if max(rows, cols) <= 10 else 900

# Optional import JSON area
import_text = st.sidebar.text_area("Import JSON (optional)", height=120)
if st.sidebar.button("Load import into iframe"):
    try:
        parsed = json.loads(import_text)
        st.session_state["_import_payload"] = json.dumps(parsed)
        st.sidebar.success("Import payload saved — open the board and use Import state.")
    except Exception as e:
        st.sidebar.error("Invalid JSON: " + str(e))

HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=4.0" />
<style>
  html,body { height:100%; margin:0; padding:0; font-family: Arial, Helvetica, sans-serif; -webkit-user-select:none; user-select:none; }
  #container { width:100%; height:100%; display:flex; flex-direction:column; gap:8px; box-sizing:border-box; padding:8px; }
  .controls { display:flex; gap:8px; align-items:center; }
  .board-wrap { flex:1 1 auto; display:flex; align-items:center; justify-content:center; overflow:hidden; }
  svg { touch-action: none; display:block; max-width:100%; height:auto; }
  button { padding:8px 12px; font-size:14px; }
  .hint { font-size:13px; color:#444; }
</style>
</head>
<body>
<div id="container">
  <div class="controls">
    <div>
      <button id="clearBtn">Clear</button>
      <label style="margin-left:12px;"><input id="dragMode" type="checkbox" checked /> Drag-to-draw</label>
      <button id="exportBtn" style="margin-left:12px;">Export JSON</button>
      <button id="importBtn">Import state</button>
    </div>
    <div style="flex:1"></div>
    <div class="hint">Tap the gap between two dots to toggle that edge. Drag to draw when enabled.</div>
  </div>

  <div class="board-wrap">
    <div id="svgHolder" style="width:100%; max-width:980px;"></div>
  </div>
</div>

<script>
(function(){
  try {
    console.log("slither iframe initializing");
    var ROWS = __ROWS__;
    var COLS = __COLS__;
    var CELL = __CELL__;
    var IMPORT_PAYLOAD = "__IMPORT__";
    var margin = 8;
    var xmlns = "http://www.w3.org/2000/svg";
    var svgHolder = document.getElementById('svgHolder');

    // set of "r,c,d" strings where d = 'h' or 'v'
    var filled = new Set();

    if (IMPORT_PAYLOAD && IMPORT_PAYLOAD.length>0) {
      try {
        var obj = JSON.parse(IMPORT_PAYLOAD);
        if (obj && obj.filled_edges) {
          for (var i=0;i<obj.filled_edges.length;i++) filled.add(obj.filled_edges[i]);
        }
      } catch(e){ console.warn("bad import", e); }
    }

    function edgeKey(r,c,d){ return r + "," + c + "," + d; }

    function buildSVG(){
      var width = COLS*CELL + margin*2;
      var height = ROWS*CELL + margin*2;
      var svg = document.createElementNS(xmlns, "svg");
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
      svg.style.width = "100%";
      svg.style.height = "auto";
      svg.id = "slitherSvg";

      // background
      var bg = document.createElementNS(xmlns, "rect");
      bg.setAttribute("x",0); bg.setAttribute("y",0);
      bg.setAttribute("width", width); bg.setAttribute("height", height);
      bg.setAttribute("fill", "transparent");
      svg.appendChild(bg);

      // dots
      var dotR = Math.max(3, Math.round(CELL*0.08));
      for (var r=0;r<=ROWS;r++){
        for (var c=0;c<=COLS;c++){
          var dot = document.createElementNS(xmlns, "circle");
          dot.setAttribute("cx", margin + c*CELL);
          dot.setAttribute("cy", margin + r*CELL);
          dot.setAttribute("r", dotR);
          dot.setAttribute("fill", "#111");
          svg.appendChild(dot);
        }
      }

      // horizontal hit-lines (invisible thick areas that respond to taps)
      for (var r=0;r<=ROWS;r++){
        for (var c=0;c<COLS;c++){
          var x1 = margin + c*CELL, y = margin + r*CELL, x2 = x1 + CELL;
          var g = document.createElementNS(xmlns, "g");
          var key = edgeKey(r,c,'h');
          g.setAttribute("data-edge", key);
          // visible stroke (drawn when filled)
          var vis = document.createElementNS(xmlns, "line");
          vis.setAttribute("x1", x1); vis.setAttribute("y1", y);
          vis.setAttribute("x2", x2); vis.setAttribute("y2", y);
          vis.setAttribute("stroke-linecap", "round");
          vis.setAttribute("stroke-width", 6);
          vis.setAttribute("class", "vis");
          // hit area
          var hit = document.createElementNS(xmlns, "line");
          hit.setAttribute("x1", x1); hit.setAttribute("y1", y);
          hit.setAttribute("x2", x2); hit.setAttribute("y2", y);
          hit.setAttribute("stroke-linecap", "round");
          hit.setAttribute("stroke-width", CELL*0.6);
          hit.setAttribute("stroke", "transparent");
          hit.style.cursor = "pointer";
          hit.addEventListener('pointerdown', onHitPointerDown);
          hit.addEventListener('pointerup', onHitPointerUp);
          g.appendChild(vis);
          g.appendChild(hit);
          svg.appendChild(g);
        }
      }

      // vertical hit-lines
      for (var r=0;r<ROWS;r++){
        for (var c=0;c<=COLS;c++){
          var x = margin + c*CELL, y1 = margin + r*CELL, y2 = y1 + CELL;
          var g = document.createElementNS(xmlns, "g");
          var key = edgeKey(r,c,'v');
          g.setAttribute("data-edge", key);
          var vis = document.createElementNS(xmlns, "line");
          vis.setAttribute("x1", x); vis.setAttribute("y1", y1);
          vis.setAttribute("x2", x); vis.setAttribute("y2", y2);
          vis.setAttribute("stroke-linecap", "round");
          vis.setAttribute("stroke-width", 6);
          vis.setAttribute("class", "vis");
          var hit = document.createElementNS(xmlns, "line");
          hit.setAttribute("x1", x); hit.setAttribute("y1", y1);
          hit.setAttribute("x2", x); hit.setAttribute("y2", y2);
          hit.setAttribute("stroke-linecap", "round");
          hit.setAttribute("stroke-width", CELL*0.6);
          hit.setAttribute("stroke", "transparent");
          hit.style.cursor = "pointer";
          hit.addEventListener('pointerdown', onHitPointerDown);
          hit.addEventListener('pointerup', onHitPointerUp);
          g.appendChild(vis);
          g.appendChild(hit);
          svg.appendChild(g);
        }
      }

      updateVisuals(svg);
      return svg;
    }

    var pointerActive = false;
    var pointerMode = null; // 'add' or 'remove'

    function onHitPointerDown(ev){
      ev.preventDefault();
      try{ ev.target.setPointerCapture(ev.pointerId); } catch(e){}
      pointerActive = true;
      var g = ev.target.closest('[data-edge]');
      if (!g) return;
      var key = g.getAttribute('data-edge');
      // determine mode: if currently filled remove on drag, else add on drag
      pointerMode = filled.has(key) ? 'remove' : 'add';
      // immediate toggle on tap-down for responsiveness
      toggleEdgeImmediate(key);
    }

    function onHitPointerUp(ev){
      try{ ev.target.releasePointerCapture(ev.pointerId); } catch(e){}
      pointerActive = false;
      pointerMode = null;
    }

    // Drag support: when pointer moves over other hit areas while pressed
    document.addEventListener('pointermove', function(ev){
      if (!pointerActive) return;
      if (!document.getElementById('dragMode').checked) return;
      var el = document.elementFromPoint(ev.clientX, ev.clientY);
      if (!el) return;
      var g = el.closest && el.closest('[data-edge]');
      if (!g) return;
      var key = g.getAttribute('data-edge');
      if (pointerMode === 'add'){
        if (!filled.has(key)){ filled.add(key); updateVisuals(document.getElementById('slitherSvg')); }
      } else if (pointerMode === 'remove'){
        if (filled.has(key)){ filled.delete(key); updateVisuals(document.getElementById('slitherSvg')); }
      }
    }, {passive:true});

    function toggleEdgeImmediate(key){
      if (filled.has(key)) filled.delete(key);
      else filled.add(key);
      updateVisuals(document.getElementById('slitherSvg'));
    }

    function updateVisuals(svg){
      if (!svg) return;
      var groups = svg.querySelectorAll('[data-edge]');
      groups.forEach(function(g){
        var k = g.getAttribute('data-edge');
        var vis = g.querySelector('.vis');
        if (filled.has(k)){
          vis.setAttribute('stroke', '#111');
          vis.setAttribute('opacity', '1');
        } else {
          vis.setAttribute('stroke', 'transparent');
          vis.setAttribute('opacity', '0');
        }
      });
    }

    // Buttons
    document.addEventListener('click', function(ev){
      var t = ev.target;
      if (!t) return;
      if (t.id === 'clearBtn'){
        filled.clear();
        updateVisuals(document.getElementById('slitherSvg'));
      } else if (t.id === 'exportBtn'){
        var payload = { rows: ROWS, cols: COLS, filled_edges: Array.from(filled) };
        try { window.parent.postMessage({isStreamlitMessage:true, type:'component_value', value: payload}, '*'); }
        catch(e){ console.warn(e); }
        t.innerText = "Exported ✓";
        setTimeout(function(){ t.innerText = "Export JSON"; }, 900);
      } else if (t.id === 'importBtn'){
        if (window._IMPORT_PAYLOAD){
          try {
            var obj = JSON.parse(window._IMPORT_PAYLOAD);
            if (obj && obj.filled_edges){ filled.clear(); for (var i=0;i<obj.filled_edges.length;i++) filled.add(obj.filled_edges[i]); updateVisuals(document.getElementById('slitherSvg')); }
          } catch(e){ console.warn(e); }
        } else {
          t.innerText = "No import data";
          setTimeout(function(){ t.innerText = "Import state"; }, 900);
        }
      }
    });

    if (IMPORT_PAYLOAD && IMPORT_PAYLOAD.length>0){ try{ window._IMPORT_PAYLOAD = IMPORT_PAYLOAD; } catch(e){} }

    // initial render
    svgHolder.innerHTML = "";
    svgHolder.appendChild(buildSVG());

    // expose state getter for debugging / future use
    window.getBoardState = function(){ return { rows: ROWS, cols: COLS, filled_edges: Array.from(filled) }; };

    console.log("slither iframe ready");
  } catch (err) {
    console.error("slither iframe init error", err);
    var holder = document.getElementById('svgHolder');
    if (holder) { holder.innerHTML = "<div style='color:red;padding:12px'>Error initializing board — open console for details</div>"; }
  }
})();
</script>
</body>
</html>
"""

# prepare replacements (safe)
import_payload = st.session_state.get("_import_payload", "")
html_code = (
    HTML_TEMPLATE
    .replace("__ROWS__", str(rows))
    .replace("__COLS__", str(cols))
    .replace("__CELL__", str(cell_px))
    .replace("__IMPORT__", json.dumps(import_payload))
)

posted = html(html_code, height=iframe_height, scrolling=True)

st.write("---")
st.subheader("Exported state from iframe (click Export JSON in iframe)")
if posted:
    st.success("Received payload from iframe")
    st.json(posted)
    if st.button("Load this exported state into iframe"):
        st.session_state["_import_payload"] = json.dumps(posted)
        st.experimental_rerun()
else:
    st.info("No payload received yet. Click 'Export JSON' inside the board to send the state here.")
