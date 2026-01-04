# app.py
import streamlit as st
from streamlit.components.v1 import html
import json

st.set_page_config(page_title="Slitherlink Board", layout="wide")
st.title("Slitherlink Board")

# UI inputs
rows = st.sidebar.number_input("Rows", min_value=3, max_value=20, value=7, step=1)
cols = st.sidebar.number_input("Columns", min_value=3, max_value=20, value=7, step=1)
cell_px = st.sidebar.number_input("Cell size (px)", min_value=24, max_value=120, value=56, step=1)
iframe_height = 640 if max(rows, cols) <= 10 else 900

# Optional import JSON (paste a dict with key "filled_edges": list of "r,c,d" strings)
import_text = st.sidebar.text_area("Import board JSON (optional)", height=120)
if st.sidebar.button("Load import into iframe"):
    try:
        parsed = json.loads(import_text)
        st.session_state["_import_payload"] = json.dumps(parsed)
        st.sidebar.success("Import payload saved — open the board and use Import state.")
    except Exception as e:
        st.sidebar.error("Invalid JSON: " + str(e))

# HTML template (plain string; no f-string)
HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=4.0, user-scalable=1" />
<style>
  html,body { height:100%; margin:0; padding:0; font-family: Arial, Helvetica, sans-serif; -webkit-user-select: none; -ms-user-select: none; user-select: none; }
  #container { width:100%; height:100%; display:flex; flex-direction:column; gap:8px; box-sizing:border-box; padding:8px; }
  .controls { display:flex; gap:8px; align-items:center; }
  .board-wrap { flex:1 1 auto; display:flex; align-items:center; justify-content:center; overflow:hidden; }
  svg { touch-action: none; display:block; max-width:100%; height:auto; }
  button { padding:8px 12px; font-size:14px; }
  .hint { font-size:13px; color:#444; }
  .coords { font-size:12px; color:#888; }
</style>
</head>
<body>
<div id="container">
  <div class="controls">
    <div>
      <button id="resetBtn">Clear</button>
      <button id="exportBtn">Export to Streamlit</button>
      <button id="importBtn">Import state</button>
      <label style="margin-left:8px;"><input id="dragMode" type="checkbox" checked /> Drag-to-draw</label>
    </div>
    <div style="flex:1"></div>
    <div class="hint">Tap edge to toggle. Double-tap to zoom in/out. Pinch to zoom.</div>
  </div>

  <div class="board-wrap">
    <div id="svgHolder" style="width:100%; max-width:980px;"></div>
  </div>

  <div style="display:flex; gap:8px; align-items:center;">
    <div class="coords" id="coords"></div>
    <div style="flex:1"></div>
    <div style="font-size:12px;color:#666">Rows: __ROWS__ × Cols: __COLS__ · Base cell: __CELL__px</div>
  </div>
</div>

<script>
(function(){
  var ROWS = __ROWS__;
  var COLS = __COLS__;
  var BASE_CELL = __CELL__;
  var IMPORT_PAYLOAD = "__IMPORT__";

  // parse import payload if present
  var filled = new Set();
  if (IMPORT_PAYLOAD && IMPORT_PAYLOAD.length > 0) {
    try {
      var obj = JSON.parse(IMPORT_PAYLOAD);
      if (obj && obj.filled_edges) {
        for (var i=0;i<obj.filled_edges.length;i++) filled.add(obj.filled_edges[i]);
      }
    } catch(e) { console.warn("Invalid import payload", e); }
  }

  var margin = 8;
  var svgHolder = document.getElementById("svgHolder");
  var scale = 1;
  var lastTouchDist = null;
  var lastTouchCenter = null;

  function edgeKey(r,c,d){ return r + "," + c + "," + d; }

  function buildSVG(){
    var width = COLS * BASE_CELL + margin*2;
    var height = ROWS * BASE_CELL + margin*2;
    var xmlns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(xmlns, "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.style.width = "100%";
    svg.style.height = "auto";
    svg.id = "slitherSvg";

    var bg = document.createElementNS(xmlns, "rect");
    bg.setAttribute("x", 0); bg.setAttribute("y", 0);
    bg.setAttribute("width", width); bg.setAttribute("height", height);
    bg.setAttribute("fill", "transparent");
    svg.appendChild(bg);

    for (var r=0;r<=ROWS;r++){
      for (var c=0;c<=COLS;c++){
        var dot = document.createElementNS(xmlns, "circle");
        dot.setAttribute("cx", margin + c*BASE_CELL);
        dot.setAttribute("cy", margin + r*BASE_CELL);
        dot.setAttribute("r", 4);
        dot.setAttribute("fill", "#000");
        svg.appendChild(dot);
      }
    }

    var edgesGroup = document.createElementNS(xmlns, "g");
    for (var r=0;r<=ROWS;r++){
      for (var c=0;c<COLS;c++){
        var x1 = margin + c*BASE_CELL;
        var y = margin + r*BASE_CELL;
        var x2 = x1 + BASE_CELL;
        var key = edgeKey(r,c,"h");
        var grp = document.createElementNS(xmlns, "g");
        grp.setAttribute("data-edge", key);
        var vis = document.createElementNS(xmlns, "line");
        vis.setAttribute("x1", x1); vis.setAttribute("y1", y);
        vis.setAttribute("x2", x2); vis.setAttribute("y2", y);
        vis.setAttribute("stroke-linecap", "round");
        vis.setAttribute("stroke-width", 6);
        vis.setAttribute("class", "visible-line");
        var hit = document.createElementNS(xmlns, "line");
        hit.setAttribute("x1", x1); hit.setAttribute("y1", y);
        hit.setAttribute("x2", x2); hit.setAttribute("y2", y);
        hit.setAttribute("stroke-linecap", "round");
        hit.setAttribute("stroke-width", BASE_CELL * 0.6);
        hit.setAttribute("stroke", "transparent");
        hit.setAttribute("class", "hit-line");
        hit.style.cursor = "pointer";
        grp.appendChild(vis);
        grp.appendChild(hit);
        edgesGroup.appendChild(grp);
      }
    }
    for (var r=0;r<ROWS;r++){
      for (var c=0;c<=COLS;c++){
        var x = margin + c*BASE_CELL;
        var y1 = margin + r*BASE_CELL;
        var y2 = y1 + BASE_CELL;
        var keyv = edgeKey(r,c,"v");
        var grpv = document.createElementNS(xmlns, "g");
        grpv.setAttribute("data-edge", keyv);
        var visv = document.createElementNS(xmlns, "line");
        visv.setAttribute("x1", x); visv.setAttribute("y1", y1);
        visv.setAttribute("x2", x); visv.setAttribute("y2", y2);
        visv.setAttribute("stroke-linecap", "round"); visv.setAttribute("stroke-width", 6);
        visv.setAttribute("class", "visible-line");
        var hitv = document.createElementNS(xmlns, "line");
        hitv.setAttribute("x1", x); hitv.setAttribute("y1", y1);
        hitv.setAttribute("x2", x); hitv.setAttribute("y2", y2);
        hitv.setAttribute("stroke-linecap", "round"); hitv.setAttribute("stroke-width", BASE_CELL * 0.6);
        hitv.setAttribute("stroke", "transparent");
        hitv.setAttribute("class", "hit-line");
        hitv.style.cursor = "pointer";
        grpv.appendChild(visv);
        grpv.appendChild(hitv);
        edgesGroup.appendChild(grpv);
      }
    }
    svg.appendChild(edgesGroup);
    return svg;
  }

  function renderSVG(){
    svgHolder.innerHTML = "";
    var svg = buildSVG();
    svgHolder.appendChild(svg);
    updateVisuals();
    attachHandlers(svg);
  }

  function updateVisuals(){
    var svg = document.getElementById("slitherSvg");
    if (!svg) return;
    var groups = svg.querySelectorAll('[data-edge]');
    groups.forEach(function(g){
      var key = g.getAttribute('data-edge');
      var vis = g.querySelector('.visible-line');
      if (filled.has(key)){
        vis.setAttribute('stroke', '#111');
        vis.setAttribute('opacity', '1');
      } else {
        vis.setAttribute('stroke', 'transparent');
        vis.setAttribute('opacity', '0');
      }
    });
  }

  function clientToSvgPoint(svg, clientX, clientY){
    var pt = svg.createSVGPoint();
    pt.x = clientX; pt.y = clientY;
    var ctm = svg.getScreenCTM();
    if (!ctm) return null;
    return pt.matrixTransform(ctm.inverse());
  }

  function attachHandlers(svg){
    var pointerDown = false;
    var pointerMode = null;
    var lastEdge = null;

    svg.addEventListener('pointerdown', function(ev){
      ev.preventDefault();
      try{ svg.setPointerCapture(ev.pointerId); }catch(e){}
      var hit = document.elementFromPoint(ev.clientX, ev.clientY);
      var grp = hit && hit.closest && hit.closest('[data-edge]');
      if (grp){
        var key = grp.getAttribute('data-edge');
        toggleEdgeByKey(key);
        pointerMode = filled.has(key) ? 'remove' : 'add';
        lastEdge = key;
      }
      pointerDown = true;
    });

    svg.addEventListener('pointermove', function(ev){
      if (!pointerDown) return;
      if (!document.getElementById('dragMode').checked) return;
      var hit = document.elementFromPoint(ev.clientX, ev.clientY);
      var grp = hit && hit.closest && hit.closest('[data-edge]');
      if (grp){
        var key = grp.getAttribute('data-edge');
        if (key !== lastEdge){
          if (pointerMode === 'add'){
            if (!filled.has(key)) filled.add(key);
            updateVisuals();
          } else if (pointerMode === 'remove'){
            if (filled.has(key)) filled.delete(key);
            updateVisuals();
          }
          lastEdge = key;
        }
      }
    });

    svg.addEventListener('pointerup', function(ev){
      try{ svg.releasePointerCapture(ev.pointerId); }catch(e){}
      pointerDown = false;
      pointerMode = null;
      lastEdge = null;
    });

    svg.addEventListener('dblclick', function(ev){
      ev.preventDefault();
      if (Math.abs(scale - 1) < 0.01) {
        scale = 2;
      } else {
        scale = 1;
      }
      applyTransform();
    });

    svg.addEventListener('touchstart', function(ev){
      if (ev.touches && ev.touches.length === 2){
        lastTouchDist = Math.hypot(
          ev.touches[0].clientX - ev.touches[1].clientX,
          ev.touches[0].clientY - ev.touches[1].clientY
        );
      }
    }, {passive:false});

    svg.addEventListener('touchmove', function(ev){
      if (ev.touches && ev.touches.length === 2){
        ev.preventDefault();
        var d = Math.hypot(
          ev.touches[0].clientX - ev.touches[1].clientX,
          ev.touches[0].clientY - ev.touches[1].clientY
        );
        if (lastTouchDist){
          var factor = d / lastTouchDist;
          var newScale = Math.max(0.5, Math.min(4, scale * factor));
          scale = newScale;
          applyTransform();
        }
        lastTouchDist = d;
      }
    }, {passive:false});

    svg.addEventListener('touchend', function(ev){
      lastTouchDist = null;
    });

  }

  function applyTransform(){
    var svg = document.getElementById("slitherSvg");
    if (!svg) return;
    svg.style.transformOrigin = "0 0";
    svg.style.transform = "translate(0px, 0px) scale(" + scale + ")";
  }

  function toggleEdgeByKey(key){
    if (filled.has(key)) filled.delete(key);
    else filled.add(key);
    updateVisuals();
  }

  // Button handlers in parent document
  document.addEventListener('click', function(ev){
    var target = ev.target;
    if (!target) return;
    if (target.id === 'resetBtn'){
      filled.clear();
      updateVisuals();
    } else if (target.id === 'exportBtn'){
      var payload = { rows: ROWS, cols: COLS, filled_edges: Array.from(filled) };
      try {
        window.parent.postMessage({isStreamlitMessage: true, type: 'component_value', value: payload}, '*');
      } catch(e){}
      target.innerText = "Exported ✓";
      setTimeout(function(){ target.innerText = "Export to Streamlit"; }, 900);
    } else if (target.id === 'importBtn'){
      if (window._IMPORT_PAYLOAD){
        try {
          var obj = JSON.parse(window._IMPORT_PAYLOAD);
          if (obj && obj.filled_edges){
            filled.clear();
            for (var i=0;i<obj.filled_edges.length;i++) filled.add(obj.filled_edges[i]);
            updateVisuals();
          }
        } catch(e){}
      } else {
        target.innerText = "No import data";
        setTimeout(function(){ target.innerText = "Import state"; }, 900);
      }
    }
  });

  if (IMPORT_PAYLOAD && IMPORT_PAYLOAD.length>0){
    try { window._IMPORT_PAYLOAD = IMPORT_PAYLOAD; } catch(e){}
  }

  renderSVG();

  setInterval(function(){
    var coords = document.getElementById('coords');
    if (!coords) return;
    coords.textContent = "Scale: " + scale.toFixed(2) + " · Edges: " + filled.size;
  }, 600);

})(); 
</script>
</body>
</html>
"""

# Prepare safe replacements
import_payload = st.session_state.get("_import_payload", "")
html_code = HTML_TEMPLATE.replace("__ROWS__", str(rows)).replace("__COLS__", str(cols)).replace("__CELL__", str(cell_px)).replace("__IMPORT__", json.dumps(import_payload))

# Render the iframe; posted will contain the last exported payload when user clicks Export inside iframe
posted = html(html_code, height=iframe_height, scrolling=True)

st.write("---")
st.subheader("Exported state from iframe (click Export to get updated value)")
if posted:
    st.success("Received payload from iframe")
    st.json(posted)
    if st.button("Load this exported state into iframe"):
        st.session_state["_import_payload"] = json.dumps(posted)
        st.experimental_rerun()
else:
    st.info("No payload received yet. Click 'Export to Streamlit' inside the board to send the state here.")
