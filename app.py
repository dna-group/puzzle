# app.py
import streamlit as st
from streamlit.components.v1 import html
import json

st.set_page_config(page_title="Slitherlink — Playable", layout="wide")
st.title("Slitherlink — Playable")

# --- UI inputs
cols = st.sidebar.number_input("Columns", min_value=2, max_value=20, value=7, step=1)
rows = st.sidebar.number_input("Rows", min_value=2, max_value=20, value=7, step=1)
cell_px = st.sidebar.slider("Cell size (px)", min_value=24, max_value=120, value=56)
iframe_height = 700 if max(rows, cols) <= 10 else 980

st.sidebar.markdown("**Board state Import** (paste JSON with key `filled_edges`)")
import_text = st.sidebar.text_area("", height=120)
if st.sidebar.button("Save import payload to session"):
    try:
        parsed = json.loads(import_text)
        st.session_state["_import_payload"] = json.dumps(parsed)
        st.sidebar.success("Import payload saved (use Import in board).")
    except Exception as e:
        st.sidebar.error("Invalid JSON: " + str(e))

# --- HTML template (plain string; placeholders replaced safely)
HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=4.0" />
<style>
  html,body{height:100%;margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;-webkit-user-select:none;user-select:none}
  #container{box-sizing:border-box;padding:12px;height:100%;display:flex;flex-direction:column;gap:8px}
  .controls{display:flex;gap:8px;align-items:center}
  .board-wrap{flex:1 1 auto;display:flex;align-items:center;justify-content:center;overflow:hidden}
  svg{touch-action:none;display:block;max-width:100%;height:auto}
  button{padding:8px 12px;font-size:14px}
  .hint{font-size:13px;color:#444}
  .status{font-size:12px;color:#666}
</style>
</head>
<body>
<div id="container">
  <div class="controls">
    <div>
      <button id="clearBtn">Clear</button>
      <label style="margin-left:10px"><input id="dragMode" type="checkbox" checked /> Drag-to-draw</label>
      <button id="exportBtn" style="margin-left:12px">Export JSON</button>
      <button id="importBtn" style="margin-left:6px">Import state</button>
    </div>
    <div style="flex:1"></div>
    <div class="hint">Tap gap to toggle edge. Drag to draw. Double-tap to zoom. Pinch to zoom.</div>
  </div>

  <div class="board-wrap"><div id="svgHolder" style="width:100%;max-width:980px"></div></div>
  <div class="status" id="status">Ready</div>
</div>

<script>
(function(){
  try {
    var ROWS = __ROWS__;
    var COLS = __COLS__;
    var CELL = __CELL__;
    var IMPORT_PAYLOAD = "__IMPORT__";
    var margin = 8;
    var xmlns = "http://www.w3.org/2000/svg";
    var svgHolder = document.getElementById("svgHolder");
    var statusEl = document.getElementById("status");

    // filled edges stored as plain arrays when exported; internal uses Set for speed
    var filled = new Set();
    if (IMPORT_PAYLOAD && IMPORT_PAYLOAD.length>0) {
      try {
        var ip = JSON.parse(IMPORT_PAYLOAD);
        if (ip && Array.isArray(ip.filled_edges)) {
          ip.filled_edges.forEach(function(e){ filled.add(e); });
        }
      } catch(e){ console.warn("import error", e); }
    }

    function edgeKey(r,c,d){ return r + "," + c + "," + d; }

    // build SVG with hit areas between dots
    function buildSVG(){
      var width = COLS*CELL + margin*2;
      var height = ROWS*CELL + margin*2;
      var svg = document.createElementNS(xmlns,"svg");
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
      svg.style.width = "100%"; svg.style.height = "auto";
      svg.id = "slitherSvg";

      var bg = document.createElementNS(xmlns,"rect");
      bg.setAttribute("x",0); bg.setAttribute("y",0);
      bg.setAttribute("width", width); bg.setAttribute("height", height);
      bg.setAttribute("fill", "transparent");
      svg.appendChild(bg);

      // dots
      var dotR = Math.max(3, Math.round(CELL*0.08));
      for (var r=0;r<=ROWS;r++){
        for (var c=0;c<=COLS;c++){
          var dot = document.createElementNS(xmlns,"circle");
          dot.setAttribute("cx", margin + c*CELL);
          dot.setAttribute("cy", margin + r*CELL);
          dot.setAttribute("r", dotR);
          dot.setAttribute("fill", "#111");
          svg.appendChild(dot);
        }
      }

      // create groups for horizontal and vertical hit lines
      for (var r=0;r<=ROWS;r++){
        for (var c=0;c<COLS;c++){
          var x1 = margin + c*CELL, y = margin + r*CELL, x2 = x1 + CELL;
          var g = document.createElementNS(xmlns,"g");
          g.setAttribute("data-edge", edgeKey(r,c,"h"));
          var vis = document.createElementNS(xmlns,"line");
          vis.setAttribute("x1", x1); vis.setAttribute("y1", y);
          vis.setAttribute("x2", x2); vis.setAttribute("y2", y);
          vis.setAttribute("stroke-linecap","round");
          vis.setAttribute("stroke-width",6);
          vis.setAttribute("class","vis");
          var hit = document.createElementNS(xmlns,"line");
          hit.setAttribute("x1", x1); hit.setAttribute("y1", y);
          hit.setAttribute("x2", x2); hit.setAttribute("y2", y);
          hit.setAttribute("stroke-linecap","round");
          hit.setAttribute("stroke-width", CELL*0.6);
          hit.setAttribute("stroke","transparent");
          hit.style.cursor = "pointer";
          hit.addEventListener("pointerdown", onHitDown);
          hit.addEventListener("pointerup", onHitUp);
          g.appendChild(vis); g.appendChild(hit);
          svg.appendChild(g);
        }
      }
      for (var r=0;r<ROWS;r++){
        for (var c=0;c<=COLS;c++){
          var x = margin + c*CELL, y1 = margin + r*CELL, y2 = y1 + CELL;
          var g = document.createElementNS(xmlns,"g");
          g.setAttribute("data-edge", edgeKey(r,c,"v"));
          var vis = document.createElementNS(xmlns,"line");
          vis.setAttribute("x1", x); vis.setAttribute("y1", y1);
          vis.setAttribute("x2", x); vis.setAttribute("y2", y2);
          vis.setAttribute("stroke-linecap","round");
          vis.setAttribute("stroke-width",6);
          vis.setAttribute("class","vis");
          var hit = document.createElementNS(xmlns,"line");
          hit.setAttribute("x1", x); hit.setAttribute("y1", y1);
          hit.setAttribute("x2", x); hit.setAttribute("y2", y2);
          hit.setAttribute("stroke-linecap","round");
          hit.setAttribute("stroke-width", CELL*0.6);
          hit.setAttribute("stroke","transparent");
          hit.style.cursor = "pointer";
          hit.addEventListener("pointerdown", onHitDown);
          hit.addEventListener("pointerup", onHitUp);
          g.appendChild(vis); g.appendChild(hit);
          svg.appendChild(g);
        }
      }

      updateVisuals(svg);
      return svg;
    }

    var pointerActive = false;
    var pointerMode = null; // 'add' or 'remove'
    var lastPointerEdge = null;

    function onHitDown(ev){
      ev.preventDefault();
      try{ ev.target.setPointerCapture(ev.pointerId); }catch(e){}
      pointerActive = true;
      var g = ev.target.closest("[data-edge]");
      if (!g) return;
      var key = g.getAttribute("data-edge");
      pointerMode = filled.has(key) ? "remove" : "add";
      toggleEdgeImmediate(key);
      lastPointerEdge = key;
    }
    function onHitUp(ev){
      try{ ev.target.releasePointerCapture(ev.pointerId); }catch(e){}
      pointerActive = false;
      pointerMode = null;
      lastPointerEdge = null;
    }

    document.addEventListener("pointermove", function(ev){
      if (!pointerActive) return;
      if (!document.getElementById("dragMode").checked) return;
      var el = document.elementFromPoint(ev.clientX, ev.clientY);
      if (!el) return;
      var g = el.closest && el.closest("[data-edge]");
      if (!g) return;
      var key = g.getAttribute("data-edge");
      if (key === lastPointerEdge) return;
      lastPointerEdge = key;
      if (pointerMode === "add"){
        if (!filled.has(key)){ filled.add(key); updateVisuals(document.getElementById("slitherSvg")); }
      } else if (pointerMode === "remove"){
        if (filled.has(key)){ filled.delete(key); updateVisuals(document.getElementById("slitherSvg")); }
      }
    }, {passive:true});

    function toggleEdgeImmediate(key){
      if (filled.has(key)) filled.delete(key); else filled.add(key);
      updateVisuals(document.getElementById("slitherSvg"));
    }

    function updateVisuals(svg){
      if (!svg) return;
      var groups = svg.querySelectorAll("[data-edge]");
      groups.forEach(function(g){
        var k = g.getAttribute("data-edge");
        var vis = g.querySelector(".vis");
        if (filled.has(k)){
          vis.setAttribute("stroke","#111"); vis.setAttribute("opacity","1");
        } else {
          vis.setAttribute("stroke","transparent"); vis.setAttribute("opacity","0");
        }
      });
      statusEl.textContent = "Edges: " + filled.size;
    }

    // export/import handlers via buttons
    document.addEventListener("click", function(ev){
      var t = ev.target; if (!t) return;
      if (t.id === "clearBtn"){
        filled.clear(); updateVisuals(document.getElementById("slitherSvg"));
      } else if (t.id === "exportBtn"){
        var payload = { rows: ROWS, cols: COLS, filled_edges: Array.from(filled) };
        // ensure plain JSON object
        try {
          var plain = JSON.parse(JSON.stringify(payload));
          window.parent.postMessage({isStreamlitMessage:true, type:"component_value", value: plain}, "*");
          t.innerText = "Exported ✓"; setTimeout(function(){ t.innerText = "Export JSON"; }, 900);
        } catch(e){ console.warn("export failed", e); }
      } else if (t.id === "importBtn"){
        if (window._IMPORT_PAYLOAD){
          try {
            var o = JSON.parse(window._IMPORT_PAYLOAD);
            if (o && Array.isArray(o.filled_edges)){
              filled.clear(); o.filled_edges.forEach(function(e){ filled.add(e); }); updateVisuals(document.getElementById("slitherSvg"));
            }
          } catch(e){ console.warn("import parse", e); }
        } else {
          t.innerText = "No import"; setTimeout(function(){ t.innerText = "Import state"; }, 900);
        }
      }
    });

    if (IMPORT_PAYLOAD && IMPORT_PAYLOAD.length>0){ try{ window._IMPORT_PAYLOAD = IMPORT_PAYLOAD; } catch(e){} }

    // Simple double-tap to toggle zoom (no complex pan)
    var lastTap = 0; document.addEventListener("touchend", function(e){
      var now = Date.now();
      if (now - lastTap < 300){
        var svg = document.getElementById("slitherSvg");
        if (svg){
          var cur = svg.style.transform ? parseFloat(svg.style.transform.replace("scale(","").replace(")","")) : 1;
          var next = Math.abs(cur - 1) < 0.01 ? 2 : 1;
          svg.style.transformOrigin = "0 0";
          svg.style.transform = "scale(" + next + ")";
        }
      }
      lastTap = now;
    }, {passive:true});

    // pinch-to-zoom (simple scale)
    var lastDist = null;
    document.addEventListener("touchmove", function(e){
      if (e.touches && e.touches.length === 2){
        e.preventDefault();
        var d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
        if (lastDist){
          var svg = document.getElementById("slitherSvg");
          if (svg){
            var cur = svg.style.transform ? parseFloat(svg.style.transform.replace("scale(","").replace(")","")) : 1;
            var next = Math.max(0.5, Math.min(4, cur * (d / lastDist)));
            svg.style.transformOrigin = "0 0";
            svg.style.transform = "scale(" + next + ")";
          }
        }
        lastDist = d;
      }
    }, {passive:false});
    document.addEventListener("touchend", function(){ lastDist = null; }, {passive:true});

    // initial render
    svgHolder.innerHTML = "";
    svgHolder.appendChild(buildSVG());

    // expose state getter (for manual debug)
    window.getBoardState = function(){ return { rows: ROWS, cols: COLS, filled_edges: Array.from(filled) }; };

    console.log("slither iframe ready");
  } catch (err){
    console.error("iframe init error", err);
    var holder = document.getElementById("svgHolder");
    if (holder) holder.innerHTML = "<div style='color:red;padding:12px'>Board init error — see console</div>";
  }
})();
</script>
</body>
</html>
"""

# --- prepare safe replacements and render
import_payload = st.session_state.get("_import_payload", "")
html_code = (
    HTML
    .replace("__ROWS__", str(rows))
    .replace("__COLS__", str(cols))
    .replace("__CELL__", str(cell_px))
    .replace("__IMPORT__", json.dumps(import_payload))
)

posted = html(html_code, height=iframe_height, scrolling=True)

st.write("---")
st.subheader("Exported state from iframe (click Export JSON in iframe)")
if posted is not None:
    st.success("Received payload from iframe")
    # 1) show the raw posted value and its type for debugging
    st.write("Received (raw):", repr(posted))
    st.write("Type:", type(posted).__name__)

    # 2) try to coerce into a plain JSON-like Python object (dict/list)
    shown = None
    if isinstance(posted, (dict, list)):
        shown = posted
    else:
        # posted might be a JSON string; attempt to parse
        try:
            shown = json.loads(posted)
        except Exception:
            shown = None

    # 3) only call st.json when we actually have dict or list
    if isinstance(shown, (dict, list)):
        st.subheader("Parsed JSON")
        st.json(shown)
    else:
        st.warning("Posted value is not valid JSON object/array — showing raw value instead.")
        st.write(posted)
else:
    st.info("No payload received yet. Click 'Export JSON' inside the board to send the state here.")
