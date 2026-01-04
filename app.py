import streamlit as st

st.set_page_config(page_title="Slitherlink (128×178)", layout="wide")
st.markdown(
    """
This page embeds a mobile-optimized Slitherlink canvas (128 × 178 dots).
Controls:
- Single tap: toggle an edge (add if none, remove if present). An edge is only added if there are currently < 2 lines on that edge.
- Drag (touch or mouse): pan/scroll the large puzzle.
- Long press: toggle zoomed-out / zoomed-in. When zooming in from the overview, the zoom centers on the pressed region.
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
<div class="info">128 × 178 dots. Tap between dots to toggle an edge. Drag to pan. Long-press to toggle zoom.</div>

<script>
(() => {
  const COLS = 128;
  const ROWS = 178;

  const horizontalEdges = new Uint8Array(ROWS * Math.max(0, COLS - 1));
  const verticalEdges = new Uint8Array(Math.max(0, ROWS - 1) * COLS);

  const canvas = document.getElementById('c');
  const ctx = canvas.getContext('2d', {alpha:false});
  const DOT_SPACING = 28;
  const DOT_RADIUS = 2.0;
  const EDGE_WIDTH = 4.0;
  const MAX_EDGE_COUNT = 2;

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

    const x0 = viewport.x;
    const y0 = viewport.y;
    const x1 = viewport.x + viewport.width;
    const y1 = viewport.y + viewport.height;

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

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

    const vRows = ROWS - 1;
    for (let r=0; r<vRows; r++) {
      const baseY = r * spacing;
      if (baseY + spacing + DOT_RADIUS < y0 - spacing || baseY - DOT_RADIUS > y1 + spacing) continue;
      for (let c=0; c<COLS; c++) {
        const idx = r * COLS + c;
        const val = verticalEdges[idx];
        if (val === 0) continue;
        const x = c * spacing;
        const ystart = baseY;
        const yend = baseY + spacing;
        if (x + DOT_RADIUS < x0 - spacing || x - DOT_RADIUS > x1 + spacing) continue;
        ctx.strokeStyle = '#00d0ff';
        ctx.lineWidth = EDGE_WIDTH;
        ctx.beginPath();
        ctx.moveTo(x - viewport.x, ystart - viewport.y);
        ctx.lineTo(x - viewport.x, yend - viewport.y);
        ctx.stroke();

        if (val === 2) {
          ctx.strokeStyle = '#0090a0';
          ctx.lineWidth = EDGE_WIDTH - 1.6;
          ctx.beginPath();
          ctx.moveTo(x - viewport.x + 3, ystart - viewport.y);
          ctx.lineTo(x - viewport.x + 3, yend - viewport.y);
          ctx.stroke();
        }
      }
    }

    const dotColor = '#e6e6e6';
    ctx.fillStyle = dotColor;
    const rStart = Math.max(0, Math.floor((y0 - DOT_RADIUS) / spacing));
    const rEnd = Math.min(ROWS - 1, Math.ceil((y1 + DOT_RADIUS) / spacing));
    const cStart = Math.max(0, Math.floor((x0 - DOT_RADIUS) / spacing));
    const cEnd = Math.min(COLS - 1, Math.ceil((x1 + DOT_RADIUS) / spacing));
    for (let r=rStart; r<=rEnd; r++) {
      const ry = r * spacing - viewport.y;
      for (let c=cStart; c<=cEnd; c++) {
        const rx = c * spacing - viewport.x;
        ctx.beginPath();
        ctx.arc(rx, ry, DOT_RADIUS * (scale + 0.1), 0, Math.PI*2);
        ctx.fill();
      }
    }
  }

  function clientToWorld(cx, cy) {
    const rect = canvas.getBoundingClientRect();
    const localX = (cx - rect.left);
    const localY = (cy - rect.top);
    return { x: localX + viewport.x, y: localY + viewport.y };
  }

  function findClosestEdge(worldX, worldY) {
    const spacing = DOT_SPACING * scale;
    const gx = worldX / spacing;
    const gy = worldY / spacing;

    const rNear = Math.round(gy);
    const cFloor = Math.floor(gx);
    let best = { type: null, r:0, c:0, dist: Infinity };

    for (let dc = -1; dc <= 1; dc++) {
      const c = cFloor + dc;
      const r = rNear;
      if (r < 0 || r >= ROWS) continue;
      if (c < 0 || c >= COLS - 1) continue;
      const mx = (c + 0.5) * spacing;
      const my = r * spacing;
      const dx = worldX - mx;
      const dy = worldY - my;
      const d = Math.hypot(dx, dy);
      if (d < best.dist) {
        best = { type: 'h', r: r, c: c, dist: d };
      }
    }

    const rFloor = Math.floor(gy);
    const cNear = Math.round(gx);
    for (let dr=-1; dr<=1; dr++) {
      const r = rFloor + dr;
      const c = cNear;
      if (r < 0 || r >= ROWS - 1) continue;
      if (c < 0 || c >= COLS) continue;
      const mx = c * spacing;
      const my = (r + 0.5) * spacing;
      const dx = worldX - mx;
      const dy = worldY - my;
      const d = Math.hypot(dx, dy);
      if (d < best.dist) {
        best = { type: 'v', r: r, c: c, dist: d };
      }
    }

    const hitRadius = Math.max(10, spacing * 0.4);
    if (best.dist <= hitRadius) return best;
    return null;
  }

  function toggleEdge(edge) {
    if (!edge) return;
    if (edge.type === 'h') {
      const idx = edge.r * (COLS - 1) + edge.c;
      const val = horizontalEdges[idx];
      if (val >= 1) {
        horizontalEdges[idx] = 0;
      } else {
        if (val < MAX_EDGE_COUNT) horizontalEdges[idx] = val + 1;
      }
    } else if (edge.type === 'v') {
      const idx = edge.r * COLS + edge.c;
      const val = verticalEdges[idx];
      if (val >= 1) {
        verticalEdges[idx] = 0;
      } else {
        if (val < MAX_EDGE_COUNT) verticalEdges[idx] = val + 1;
      }
    }
    requestRender();
  }

  function initViewport() {
    fitCanvas();
    scale = 1.0;
    zoomedOut = false;
    const spacing = DOT_SPACING * scale;
    const gsize = gridPixelSize(spacing);
    viewport.x = Math.max(0, (gsize.width - viewport.width) / 2);
    viewport.y = Math.max(0, (gsize.height - viewport.height) / 2);
    requestRender();
  }

  function toggleZoom(worldCenter) {
    const spacingIn = DOT_SPACING;
    if (!zoomedOut) {
      const grid = gridPixelSize(spacingIn);
      const sx = viewport.width / grid.width;
      const sy = viewport.height / grid.height;
      const s = Math.min(sx, sy, 1.0);
      scale = s;
      zoomedOut = true;
      const gW = grid.width * scale;
      const gH = grid.height * scale;
      viewport.x = Math.max(0, (gW - viewport.width) / 2);
      viewport.y = Math.max(0, (gH - viewport.height) / 2);
      requestRender();
    } else {
      scale = 1.0;
      zoomedOut = false;
      const spacing = DOT_SPACING * scale;
      const grid = gridPixelSize(spacing);
      if (worldCenter) {
        const centerX = worldCenter.x;
        const centerY = worldCenter.y;
        viewport.x = Math.min(Math.max(0, centerX - viewport.width / 2), Math.max(0, grid.width - viewport.width));
        viewport.y = Math.min(Math.max(0, centerY - viewport.height / 2), Math.max(0, grid.height - viewport.height));
      } else {
        viewport.x = Math.max(0, (grid.width - viewport.width) / 2);
        viewport.y = Math.max(0, (grid.height - viewport.height) / 2);
      }
      requestRender();
    }
  }

  // --- pointer handling with long-press to toggle zoom ---
  let isDragging = false;
  let lastPointer = null;
  let dragStart = null;
  let pointerMovedSinceDown = false;

  const LONG_PRESS_MS = 450;
  const MOVE_THRESHOLD = 8; // px

  let longPressTimer = null;
  let longPressFired = false;
  let longPressWorld = null;

  canvas.addEventListener('pointerdown', (ev) => {
    ev.preventDefault();
    canvas.setPointerCapture(ev.pointerId);
    lastPointer = { id: ev.pointerId, x: ev.clientX, y: ev.clientY };
    dragStart = { x: ev.clientX, y: ev.clientY, vx: viewport.x, vy: viewport.y };
    pointerMovedSinceDown = false;
    isDragging = true;
    longPressFired = false;
    longPressWorld = clientToWorld(ev.clientX, ev.clientY);

    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }
    longPressTimer = setTimeout(() => {
      // Only fire long press if pointer hasn't moved much and still down
      if (!pointerMovedSinceDown && isDragging) {
        longPressFired = true;
        toggleZoom(longPressWorld);
      }
      longPressTimer = null;
    }, LONG_PRESS_MS);
  });

  canvas.addEventListener('pointermove', (ev) => {
    if (!isDragging || ev.pointerId !== lastPointer.id) return;
    const dx = ev.clientX - dragStart.x;
    const dy = ev.clientY - dragStart.y;
    if (Math.hypot(dx, dy) > MOVE_THRESHOLD) {
      pointerMovedSinceDown = true;
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
      viewport.x = Math.max(0, dragStart.vx - dx);
      viewport.y = Math.max(0, dragStart.vy - dy);
      const spacing = DOT_SPACING * scale;
      const gsize = gridPixelSize(spacing);
      viewport.x = Math.min(viewport.x, Math.max(0, gsize.width - viewport.width));
      viewport.y = Math.min(viewport.y, Math.max(0, gsize.height - viewport.height));
      requestRender();
    }
    lastPointer.x = ev.clientX;
    lastPointer.y = ev.clientY;
  });

  canvas.addEventListener('pointerup', (ev) => {
    if (!lastPointer || ev.pointerId !== lastPointer.id) return;
    canvas.releasePointerCapture(ev.pointerId);
    isDragging = false;

    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }

    const upX = ev.clientX;
    const upY = ev.clientY;

    if (longPressFired) {
      // long-press already handled zoom; do not toggle edge
      longPressFired = false;
      return;
    }

    if (!pointerMovedSinceDown) {
      // treat as tap
      const world = clientToWorld(upX, upY);
      const edge = findClosestEdge(world.x, world.y);
      if (edge) toggleEdge(edge);
    } else {
      // ended a pan
    }
  });

  canvas.addEventListener('pointercancel', (ev) => {
    if (lastPointer && ev.pointerId === lastPointer.id) {
      isDragging = false;
      lastPointer = null;
    }
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }
    longPressFired = false;
    longPressWorld = null;
  });

  canvas.addEventListener('contextmenu', (ev) => ev.preventDefault());

  initViewport();
  requestRender();

  window.slitherlink = {
    toggleZoom: () => toggleZoom(),
    stateSummary: () => {
      let h = 0, v = 0;
      for (let i=0;i<horizontalEdges.length;i++) if (horizontalEdges[i]) h++;
      for (let i=0;i<verticalEdges.length;i++) if (verticalEdges[i]) v++;
      return { horiz: h, vert: v, total: h+v };
    }
  };

})();
</script>
</body>
</html>
"""

st.components.v1.html(html, height=800, scrolling=False)
