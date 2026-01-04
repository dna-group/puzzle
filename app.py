import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Slitherlink (128×178)", layout="wide")
st.markdown(
    """
This page embeds a mobile-optimized Slitherlink canvas (128 × 178 dots).
Controls:
- Single tap: toggle an edge (add if none, remove if present). An edge is only added if there are currently < 2 lines on that edge.
- Drag (touch or mouse): pan/scroll the large puzzle.
- Double-tap (or double-click): toggle zoomed-out / zoomed-in. When zooming in from the overview, the zoom centers on the tapped region.
"""
)

html = r"""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"/>
<style>
  html,body { height:100%; margin:0; background:#111; color:#ddd; -webkit-touch-callout:none; -webkit-user-select:none; user-select:none; -ms-touch-action: none; touch-action: none; }
  #container { height:88vh; display:flex; align-items:center; justify-content:center; }
  canvas { background: #0b0b0b; touch-action: none; border-radius:8px; box-shadow: 0 6px 18px rgba(0,0,0,0.6); }
  .info { font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; font-size:12px; color:#bbb; padding:8px 12px; }
</style>
</head>
<body>
<div id="container">
  <canvas id="c"></canvas>
</div>
<div class="info">128 × 178 dots. Tap between dots to toggle an edge. Drag to pan. Double-tap to toggle zoom.</div>

<script>
(() => {
  // Grid dimensions
  const COLS = 128;
  const ROWS = 178;

  // Edge storage:
  const horizontalEdges = new Uint8Array(ROWS * Math.max(0, COLS - 1));
  const verticalEdges = new Uint8Array(Math.max(0, ROWS - 1) * COLS);

  // Canvas and rendering parameters
  const canvas = document.getElementById('c');
  const ctx = canvas.getContext('2d', {alpha:false});
  const DOT_SPACING = 28;
  const DOT_RADIUS = 2.0;
  const EDGE_WIDTH = 4.0;
  const MAX_EDGE_COUNT = 2;

  // View state
  let scale = 1.0;
  let zoomedOut = false;
  let viewport = { x: 0, y: 0, width: 0, height: 0 };

  function gridPixelSize(spacing) {
    return { width: (COLS - 1) * spacing, height: (ROWS - 1) * spacing };
  }

  const DPR = Math.max(1, window.devicePixelRatio || 1);

  function fitCanvas() {
    const rect = document.getElementById('container').getBoundingClientRect();
    const cw = Math.max(300, rect.width - 24);
    const ch = Math.max(300, rect.height - 24);
    canvas.style.width = cw + 'px';
    canvas.style.height = ch + 'px';
    canvas.width = Math.round(cw * DPR);
    canvas.height = Math.round(ch * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    viewport.width = canvas.clientWidth;
    viewport.height = canvas.clientHeight;
  }

  window.addEventListener('resize', () => { fitCanvas(); requestRender(); });

  let pendingRender = false;
  function requestRender() {
    if (!pendingRender) {
      pendingRender = true;
      window.requestAnimationFrame(() => { pendingRender = false; render(); });
    }
  }

  function render() {
    ctx.fillStyle = '#0b0b0b';
    ctx.fillRect(0,0,canvas.clientWidth, canvas.clientHeight);

    const spacing = DOT_SPACING * scale;
    const gridW = (COLS - 1) * spacing;
    const gridH = (ROWS - 1) * spacing;

    const x0 = viewport.x;
    const y0 = viewport.y;
    const x1 = viewport.x + viewport.width;
    const y1 = viewport.y + viewport.height;

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    // Horizontal edges
    const hCols = COLS - 1;
    for (let r=0; r<ROWS; r++) {
      const ry = r * spacing;
      if (ry + DOT_RADIUS < y0 - spacing || ry - DOT_RADIUS > y1 + spacing) continue;
      for (let c=0; c<hCols; c++) {
        const idx = r * hCols + c;
        const val = horizontalEdges[idx];
        if (val === 0) continue;
        const xstart = c * spacing;
        const xend = (c+1) * spacing;
        if (xend < x0 - spacing || xstart > x1 + spacing) continue;
        ctx.strokeStyle = '#00d0ff';
        ctx.lineWidth = EDGE_WIDTH;
        ctx.beginPath();
        ctx.moveTo(xstart - viewport.x, ry - viewport.y);
        ctx.lineTo(xend - viewport.x, ry - viewport.y);
        ctx.stroke();

        if (val === 2) {
          ctx.strokeStyle = '#0090a0';
          ctx.lineWidth = EDGE_WIDTH - 1.6;
          ctx.beginPath();
          ctx.moveTo(xstart - viewport.x, ry - viewport.y - 3);
          ctx.lineTo(xend - viewport.x, ry - viewport.y - 3);
          ctx.stroke();
        }
      }
    }

    // Vertical edges
    const vRows = ROWS - 1;
    for (let r=0; r<vRows; r++) {
      const baseY = r * spacing;
      if (baseY + spacing + DOT_RADIUS < y0 - spacing || baseY - DOT_RADIUS > y1 + spacing) continue;
      for (let c=0; c<COLS; c++) {
        const idx = r * COLS + c;
