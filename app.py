import streamlit as st

st.set_page_config(page_title="Slitherlink (128×178) — Minimap", layout="wide")
st.markdown(
    """
Single large Slitherlink puzzle (128 × 178).  
Controls:
- Single tap/click: toggle an edge (add if none, remove if present).  
- Drag (touch or mouse): pan/scroll the large puzzle.  
- Minimap (bottom-right) shows the entire puzzle with a rectangle for the currently visible segment. Tap/click the minimap to recenter the main view.
"""
)

html = r"""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
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
<div class="info">128 × 178 dots. Tap between dots to toggle an edge. Drag to pan. Use the minimap to orient or jump.</div>

<script>
(() => {
  // Grid
  const COLS = 128;
  const ROWS = 178;

  // Edge storage
  const horizontalEdges = new Uint8Array(ROWS * Math.max(0, COLS - 1));
  const verticalEdges = new Uint8Array(Math.max(0, ROWS - 1) * COLS);

  // Canvas
  const canvas = document.getElementById('c');
  const ctx = canvas.getContext('2d', {alpha:false});

  // Visual params (no zoom; fixed scale)
  const DOT_SPACING = 28;    // pixels between dots in main view
  const DOT_RADIUS = 2.0;
  const EDGE_WIDTH = 4.0;
  const MAX_EDGE_COUNT = 2;

  // Viewport (world pixels)
  let viewport = { x: 0, y: 0, width: 0, height: 0 };

  // Device pixel ratio
  const DPR = Math.max(1, window.devicePixelRatio || 1);

  function gridPixelSize(spacing) {
    return { width: (COLS - 1) * spacing, height: (ROWS - 1) * spacing };
  }

  function fitCanvas() {
    const rect = document.getElementById('container').getBoundingClientRect();
    const cw = Math.max(320, rect.width - 24);
    const ch = Math.max(320, rect.height - 24);
    canvas.style.width = cw + 'px';
    canvas.style.height = ch + 'px';
    canvas.width = Math.round(cw * DPR);
    canvas.height = Math.round(ch * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    viewport.width = canvas.clientWidth;
    viewport.height = canvas.clientHeight;
  }

  window.addEventListener('resize', () => { fitCanvas(); requestRender(); });

  // Render scheduling
  let pendingRender = false;
  function requestRender() {
    if (!pendingRender) {
      pendingRender = true;
      window.requestAnimationFrame(() => { pendingRender = false; render(); });
    }
  }

  // Minimap parameters
  const MINIMAP_MAX_W = 220; // px
  const MINIMAP_MAX_H = 220; // px
  const MINIMAP_PADDING = 12; // px from canvas edges
  const MINIMAP_BG = 'rgba(12,12,12,0.9)';
  const MINIMAP_EDGE_COLOR = 'rgba(0,208,255,0.75)';
  const MINIMAP_VIEWPORT_COLOR = 'rgba(255,255,255,0.9)';
  const MINIMAP_BORDER = 'rgba(255,255,255,0.08)';

  function render() {
    // clear background
    ctx.fillStyle = '#0b0b0b';
    ctx.fillRect(0,0,canvas.clientWidth, canvas.clientHeight);

    const spacing = DOT_SPACING;
    const grid = gridPixelSize(spacing);

    // clamp viewport to grid
    viewport.x = Math.max(0, Math.min(viewport.x, Math.max(0, grid.width - viewport.width)));
    viewport.y = Math.max(0, Math.min(viewport.y, Math.max(0, grid.height - viewport.height)));

    // visible bounds (world)
    const x0 = viewport.x;
    const y0 = viewport.y;
    const x1 = viewport.x + viewport.width;
    const y1 = viewport.y + viewport.height;

    // draw edges (only visible region)
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

    // draw dots (visible)
    ctx.fillStyle = '#e6e6e6';
    const rStart = Math.max(0, Math.floor((y0 - DOT_RADIUS) / spacing));
    const rEnd = Math.min(ROWS - 1, Math.ceil((y1 + DOT_RADIUS) / spacing));
    const cStart = Math.max(0, Math.floor((x0 - DOT_RADIUS) / spacing));
    const cEnd = Math.min(COLS - 1, Math.ceil((x1 + DOT_RADIUS) / spacing));
    for (let r=rStart; r<=rEnd; r++) {
      const ry = r * spacing - viewport.y;
      for (let c=cStart; c<=cEnd; c++) {
        const rx = c * spacing - viewport.x;
        ctx.beginPath();
        ctx.arc(rx, ry, DOT_RADIUS, 0, Math.PI*2);
        ctx.fill();
      }
    }

    // ---------- draw minimap ----------
    // compute minimap size keeping aspect ratio
    const maxW = MINIMAP_MAX_W;
    const maxH = MINIMAP_MAX_H;
    const scaleX = maxW / grid.width;
    const scaleY = maxH / grid.height;
    const miniScale = Math.min(scaleX, scaleY, 1.0);
    const miniW = Math.round(grid.width * miniScale);
    const miniH = Math.round(grid.height * miniScale);

    const miniX = canvas.clientWidth - MINIMAP_PADDING - miniW;
    const miniY = canvas.clientHeight - MINIMAP_PADDING - miniH;

    // background
    ctx.fillStyle = MINIMAP_BG;
    ctx.fillRect(miniX - 2, miniY - 2, miniW + 4, miniH + 4);

    // draw simplified edges on minimap (sampled to keep it fast)
    ctx.save();
    ctx.beginPath();
    ctx.rect(miniX, miniY, miniW, miniH);
    ctx.clip();

    // scale and translate to minimap origin
    ctx.translate(miniX, miniY);
    ctx.scale(miniScale, miniScale);

    // draw edges (use thin lines)
    ctx.lineWidth = Math.max(1 / miniScale, 0.8);
    ctx.strokeStyle = MINIMAP_EDGE_COLOR;

    // horizontal
    for (let r=0; r<ROWS; r++) {
      const hC = COLS - 1;
      const ry = r * spacing;
      for (let c=0; c<hC; c++) {
        const idx = r * hC + c;
        const val = horizontalEdges[idx];
        if (!val) continue;
        ctx.beginPath();
        ctx.moveTo(c * spacing, ry);
        ctx.lineTo((c+1) * spacing, ry);
        ctx.stroke();
      }
    }
    // vertical
    for (let r=0; r<ROWS-1; r++) {
      const baseY = r * spacing;
      for (let c=0; c<COLS; c++) {
        const idx = r * COLS + c;
        const val = verticalEdges[idx];
        if (!val) continue;
        ctx.beginPath();
        ctx.moveTo(c * spacing, baseY);
        ctx.lineTo(c * spacing, baseY + spacing);
        ctx.stroke();
      }
    }

    // restore transform
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);

    // draw border for minimap
    ctx.strokeStyle = MINIMAP_BORDER;
    ctx.lineWidth = 1;
    ctx.strokeRect(miniX - 1, miniY - 1, miniW + 2, miniH + 2);

    // draw viewport rectangle on minimap (in screen coordinates)
    const viewRectX = miniX + Math.round((viewport.x / grid.width) * miniW);
    const viewRectY = miniY + Math.round((viewport.y / grid.height) * miniH);
    const viewRectW = Math.max(4, Math.round((viewport.width / grid.width) * miniW));
    const viewRectH = Math.max(4, Math.round((viewport.height / grid.height) * miniH));

    ctx.strokeStyle = MINIMAP_VIEWPORT_COLOR;
    ctx.lineWidth = 2;
    ctx.strokeRect(viewRectX + 0.5, viewRectY + 0.5, viewRectW, viewRectH);

    // draw a subtle fill for the viewport rect
    ctx.fillStyle = 'rgba(255,255,255,0.06)';
    ctx.fillRect(viewRectX + 1, viewRectY + 1, viewRectW - 2, viewRectH - 2);

    // store minimap metrics for hit testing
    minimapState.x = miniX;
    minimapState.y = miniY;
    minimapState.w = miniW;
    minimapState.h = miniH;
    minimapState.scale = miniScale;
    minimapState.gridW = grid.width;
    minimapState.gridH = grid.height;

  } // end render

  // minimap state for hit testing
  const minimapState = { x:0, y:0, w:0, h:0, scale:1, gridW:0, gridH:0 };

  // Input handling: panning + tapping for edges; minimap click to recenter
  let isDragging = false;
  let lastPointer = null;
  let dragStart = null;
  let pointerMovedSinceDown = false;
  const MOVE_THRESHOLD = 6; // px

  canvas.addEventListener('pointerdown', (ev) => {
    ev.preventDefault();
    canvas.setPointerCapture(ev.pointerId);
    lastPointer = { id: ev.pointerId, x: ev.clientX, y: ev.clientY };
    dragStart = { x: ev.clientX, y: ev.clientY, vx: viewport.x, vy: viewport.y };
    pointerMovedSinceDown = false;
    isDragging = true;
  });

  canvas.addEventListener('pointermove', (ev) => {
    if (!isDragging || ev.pointerId !== lastPointer.id) return;
    const dx = ev.clientX - dragStart.x;
    const dy = ev.clientY - dragStart.y;
    if (Math.hypot(dx, dy) > MOVE_THRESHOLD) {
      pointerMovedSinceDown = true;
      viewport.x = Math.max(0, dragStart.vx - dx);
      viewport.y = Math.max(0, dragStart.vy - dy);
      // clamp
      const grid = gridPixelSize(DOT_SPACING);
      viewport.x = Math.min(viewport.x, Math.max(0, grid.width - viewport.width));
      viewport.y = Math.min(viewport.y, Math.max(0, grid.height - viewport.height));
      requestRender();
    }
    lastPointer.x = ev.clientX;
    lastPointer.y = ev.clientY;
  });

  canvas.addEventListener('pointerup', (ev) => {
    if (!lastPointer || ev.pointerId !== lastPointer.id) return;
    canvas.releasePointerCapture(ev.pointerId);
    isDragging = false;

    const upX = ev.clientX;
    const upY = ev.clientY;

    // if click/tap inside minimap, recentre main view
    if (pointInMinimap(upX, upY)) {
      const wx = minimapToWorldX(upX);
      const wy = minimapToWorldY(upY);
      // center viewport on this world point
      const grid = gridPixelSize(DOT_SPACING);
      viewport.x = Math.min(Math.max(0, wx - viewport.width / 2), Math.max(0, grid.width - viewport.width));
      viewport.y = Math.min(Math.max(0, wy - viewport.height / 2), Math.max(0, grid.height - viewport.height));
      requestRender();
      return;
    }

    if (!pointerMovedSinceDown) {
      // treat as tap on main canvas: toggle edge
      const world = clientToWorld(upX, upY);
      const edge = findClosestEdge(world.x, world.y);
      if (edge) toggleEdge(edge);
      requestRender();
    } else {
      // ended a pan; already rendered while moving
    }
  });

  canvas.addEventListener('pointercancel', (ev) => {
    if (lastPointer && ev.pointerId === lastPointer.id) {
      isDragging = false;
      lastPointer = null;
    }
  });

  canvas.addEventListener('contextmenu', (ev) => ev.preventDefault());

  // coordinate transforms
  function clientToWorld(cx, cy) {
    const rect = canvas.getBoundingClientRect();
    const localX = (cx - rect.left);
    const localY = (cy - rect.top);
    return { x: localX + viewport.x, y: localY + viewport.y };
  }

  function pointInMinimap(cx, cy) {
    return cx >= minimapState.x && cx <= (minimapState.x + minimapState.w) &&
           cy >= minimapState.y && cy <= (minimapState.y + minimapState.h);
  }

  function minimapToWorldX(cx) {
    const rx = cx - minimapState.x;
    const ratio = rx / minimapState.w;
    return ratio * minimapState.gridW;
  }
  function minimapToWorldY(cy) {
    const ry = cy - minimapState.y;
    const ratio = ry / minimapState.h;
    return ratio * minimapState.gridH;
  }

  // Hit detection for edges (nearest horizontal or vertical edge midpoint)
  function findClosestEdge(worldX, worldY) {
    const spacing = DOT_SPACING;
    const gx = worldX / spacing;
    const gy = worldY / spacing;

    let best = { type: null, r:0, c:0, dist: Infinity };

    const rNear = Math.round(gy);
    const cFloor = Math.floor(gx);
    for (let dc = -1; dc <= 1; dc++) {
      const c = cFloor + dc;
      const r = rNear;
      if (r < 0 || r >= ROWS) continue;
      if (c < 0 || c >= COLS - 1) continue;
      const mx = (c + 0.5) * spacing;
      const my = r * spacing;
      const d = Math.hypot(worldX - mx, worldY - my);
      if (d < best.dist) best = { type:'h', r:r, c:c, dist:d };
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
      const d = Math.hypot(worldX - mx, worldY - my);
      if (d < best.dist) best = { type:'v', r:r, c:c, dist:d };
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
      if (val >= 1) horizontalEdges[idx] = 0;
      else if (val < MAX_EDGE_COUNT) horizontalEdges[idx] = val + 1;
    } else if (edge.type === 'v') {
      const idx = edge.r * COLS + edge.c;
      const val = verticalEdges[idx];
      if (val >= 1) verticalEdges[idx] = 0;
      else if (val < MAX_EDGE_COUNT) verticalEdges[idx] = val + 1;
    }
  }

  // initialize viewport centered
  function initViewport() {
    fitCanvas();
    const grid = gridPixelSize(DOT_SPACING);
    viewport.x = Math.max(0, (grid.width - viewport.width) / 2);
    viewport.y = Math.max(0, (grid.height - viewport.height) / 2);
    requestRender();
  }

  initViewport();

  // Expose some debug helpers
  window.slitherlink = {
    stateSummary: () => {
      let h=0,v=0;
      for (let i=0;i<horizontalEdges.length;i++) if (horizontalEdges[i]) h++;
      for (let i=0;i<verticalEdges.length;i++) if (verticalEdges[i]) v++;
      return { horiz:h, vert:v, total:h+v };
    },
    panTo: (x,y) => { viewport.x = x; viewport.y = y; requestRender(); }
  };

})();
</script>
</body>
</html>
"""

st.components.v1.html(html, height=800, scrolling=False)
