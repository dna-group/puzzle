# app.py
import streamlit as st
import json
from streamlit.components.v1 import html

st.set_page_config(page_title="Slitherlink Board", layout="wide")

st.title("Slitherlink Board — Tap / Pinch / Double-tap")

# Controls in Streamlit sidebar
cols = st.sidebar.number_input("Columns", min_value=3, max_value=20, value=7, step=1)
rows = st.sidebar.number_input("Rows", min_value=3, max_value=20, value=7, step=1)
cell_px = st.sidebar.number_input("Base cell px (UI scale)", min_value=24, max_value=120, value=56, step=1)
show_coords = st.sidebar.checkbox("Show debug coordinates (in iframe)", value=False)

# Optional: load previously exported JSON (user can paste)
import_text = st.sidebar.text_area("Import board JSON (paste here then click Load)", height=120)
if st.sidebar.button("Load JSON into iframe"):
    try:
        imported = json.loads(import_text)
        st.session_state["_import_payload"] = json.dumps(imported)
        st.sidebar.success("Loaded payload — open the board and press 'Import state' inside it.")
    except Exception as e:
        st.sidebar.error(f"Invalid JSON: {e}")

# Build HTML/JS for the interactive board. It will post state back to Streamlit when the
# user clicks "Export to Streamlit" button inside the iframe. The posted value will be
# returned by components.html(...) as `posted` (or None if nothing posted).
escaped_import = st.session_state.get("_import_payload", "")

iframe_height = 720 if rows > 10 or cols > 10 else 560

board_html = f"""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=4.0, user-scalable=1" />
<style>
  html,body {{ height:100%; margin:0; padding:0; font-family: Arial, Helvetica, sans-serif; -webkit-user-select: none; -ms-user-select: none; user-select: none; }}
  #container {{ width:100%; height:100%; display:flex; flex-direction:column; gap:8px; box-sizing:border-box; padding:8px; }}
  .controls {{ display:flex; gap:8px; align-items:center; }}
  .board-wrap {{ flex:1 1 auto; display:flex; align-items:center; justify-content:center; overflow:hidden; }}
  svg {{ touch-action: none; display:block; max-width:100%; height:auto; }}
  button {{ padding:8px 12px; font-size:14px; }}
  .hint {{ font-size:13px; color:#444; }}
  .coords {{ font-size:12px; color:#888; }}
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
    <!-- SVG will be inserted here -->
    <div id="svgHolder" style="width:100%; max-width:980px;"></div>
  </div>

  <div style="display:flex; gap:8px; align-items:center;">
    <div class="coords" id="coords">{ 'Debug on' if show_coords else '' }</div>
    <div style="flex:1"></div>
    <div style="font-size:12px;color:#666">Rows: {rows} × Cols: {cols} · Base cell: {cell_px}px</div>
  </div>
</div>

<script>
(() => {{
  // Config from Python
  const ROWS = {rows};
  const COLS = {cols};
  const BASE_CELL = {cell_px};
  const IMPORT_PAYLOAD = {json.dumps(escaped_import) if escaped_import else '""'};

  // State: set of filled edges as strings "r,c,d" where d in {"h","v"}
  let filled = new Set();
  if (IMPORT_PAYLOAD) {{
    try {{
      const obj = JSON.parse(IMPORT_PAYLOAD);
      if (obj && obj.filled_edges) {{
        for (const e of obj.filled_edges) filled.add(e);
      }}
    }} catch(e) {{
      console.warn("Invalid import payload", e);
    }}
  }}

  // zoom/pan state
  let scale = 1;
  let translate = {{x:0, y:0}}; // in px
  let lastTouchDist = null;
  let lastTouchCenter = null;
  let lastTap = 0;

  const margin = 8;
  const svgHolder = document.getElementById("svgHolder");

  function edgeKey(r,c,d) {{ return `${{r}},${{c}},${{d}}`; }}

  // Build SVG
  function buildSVG() {{
    const width = COLS * BASE_CELL + margin*2;
    const height = ROWS * BASE_CELL + margin*2;
    const xmlns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(xmlns, "svg");
    svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.style.width = "100%";
    svg.style.height = "auto";
    svg.style.touchAction = "none";
    svg.id = "slitherSvg";

    // background rect for catching events
    const bg = document.createElementNS(xmlns, "rect");
    bg.setAttribute("x", 0); bg.setAttribute("y", 0);
    bg.setAttribute("width", width); bg.setAttribute("height", height);
    bg.setAttribute("fill", "transparent");
    svg.appendChild(bg);

    // grid dots
    for (let r=0; r<=ROWS; r++) {{
      for (let c=0; c<=COLS; c++) {{
        const dot = document.createElementNS(xmlns, "circle");
        dot.setAttribute("cx", margin + c*BASE_CELL);
        dot.setAttribute("cy", margin + r*BASE_CELL);
        dot.setAttribute("r", 4);
        dot.setAttribute("fill", "#000");
        svg.appendChild(dot);
      }}
    }}

    // draw edges (lines). We'll create groups for H and V edges for easy event mapping
    const edgesGroup = document.createElementNS(xmlns, "g");
    edgesGroup.id = "edgesGroup";

    // create invisible interactive hit areas (thicker invisible lines) and visible lines for filled edges
    for (let r=0; r<=ROWS; r++) {{
      for (let c=0; c<COLS; c++) {{
        const x1 = margin + c*BASE_CELL; const y = margin + r*BASE_CELL;
        const x2 = x1 + BASE_CELL;
        const key = edgeKey(r,c,"h");
        const grp = document.createElementNS(xmlns, "g");
        grp.setAttribute("data-edge", key);
        // visible line (if filled)
        const vis = document.createElementNS(xmlns, "line");
        vis.setAttribute("x1", x1); vis.setAttribute("y1", y);
        vis.setAttribute("x2", x2); vis.setAttribute("y2", y);
        vis.setAttribute("stroke-linecap", "round");
        vis.setAttribute("stroke-width", 6);
        vis.setAttribute("class", "visible-line");
        // hit line (thicker, transparent)
        const hit = document.createElementNS(xmlns, "line");
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
      }}
    }}
    for (let r=0; r<ROWS; r++) {{
      for (let c=0; c<=COLS; c++) {{
        const x = margin + c*BASE_CELL; const y1 = margin + r*BASE_CELL;
        const y2 = y1 + BASE_CELL;
        const key = edgeKey(r,c,"v");
        const grp = document.createElementNS(xmlns, "g");
        grp.setAttribute("data-edge", key);
        const vis = document.createElementNS(xmlns, "line");
        vis.setAttribute("x1", x); vis.setAttribute("y1", y1);
        vis.setAttribute("x2", x); vis.setAttribute("y2", y2);
        vis.setAttribute("stroke-linecap", "round"); vis.setAttribute("stroke-width", 6);
        vis.setAttribute("class", "visible-line");
        const hit = document.createElementNS(xmlns, "line");
        hit.setAttribute("x1", x); hit.setAttribute("y1", y1);
        hit.setAttribute("x2", x); hit.setAttribute("y2", y2);
        hit.setAttribute("stroke-linecap", "round"); hit.setAttribute("stroke-width", BASE_CELL * 0.6);
        hit.setAttribute("stroke", "transparent");
        hit.setAttribute("class", "hit-line");
        hit.style.cursor = "pointer";
        grp.appendChild(vis);
        grp.appendChild(hit);
        edgesGroup.appendChild(grp);
      }}
    }}
    svg.appendChild(edgesGroup);

    // overlay group for applying transforms (pan/zoom)
    const containerGroup = document.createElementNS(xmlns, "g");
    // actually we'll transform edgesGroup directly via svg viewBox scaling (we'll use CSS transforms)
    return svg;
  }}

  // render and update visuals
  function renderSVG() {{
    svgHolder.innerHTML = "";
    const svg = buildSVG();
    svgHolder.appendChild(svg);
    updateVisuals();
    attachHandlers(svg);
  }}

  function updateVisuals() {{
    const svg = document.getElementById("slitherSvg");
    if (!svg) return;
    // update visible lines
    const groups = svg.querySelectorAll('[data-edge]');
    groups.forEach(g => {{
      const key = g.getAttribute('data-edge');
      const vis = g.querySelector('.visible-line');
      if (filled.has(key)) {{
        vis.setAttribute('stroke', '#111');
        vis.setAttribute('opacity', '1');
      }} else {{
        vis.setAttribute('stroke', 'transparent');
        vis.setAttribute('opacity', '0');
      }}
    }});
  }}

  // Helpers: get nearest edge from client coords
  function clientToSvgPoint(svg, clientX, clientY) {{
    const pt = svg.createSVGPoint
