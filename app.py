  // --- double-tap suppression helpers ---
  let isDragging = false;
  let lastPointer = null;
  let dragStart = null;
  let pointerMovedSinceDown = false;

  // Double-tap detection / suppression
  let lastTapTime = 0;
  let lastTapPos = null;
  const DOUBLE_TAP_DELAY = 300;
  let suppressNextTap = false;      // when true, upcoming tap will be treated as double-tap (no edge toggle)
  let doubleTapWorld = null;       // world coord where double-tap should center

  canvas.addEventListener('pointerdown', (ev) => {
    ev.preventDefault();
    canvas.setPointerCapture(ev.pointerId);
    lastPointer = { id: ev.pointerId, x: ev.clientX, y: ev.clientY };
    dragStart = { x: ev.clientX, y: ev.clientY, vx: viewport.x, vy: viewport.y };
    pointerMovedSinceDown = false;
    isDragging = true;

    // Check if this pointerdown looks like the second tap of a double-tap.
    const timeNow = performance.now();
    const isDoubleCandidate = (timeNow - lastTapTime) <= DOUBLE_TAP_DELAY &&
                              lastTapPos &&
                              Math.hypot(ev.clientX - lastTapPos.x, ev.clientY - lastTapPos.y) < 40;
    if (isDoubleCandidate) {
      // mark to suppress the single-tap action and perform zoom on pointerup
      suppressNextTap = true;
      doubleTapWorld = clientToWorld(ev.clientX, ev.clientY);
      // clear lastTap so we don't treat further taps as chained doubles
      lastTapTime = 0;
      lastTapPos = null;
    }
  });

  canvas.addEventListener('pointermove', (ev) => {
    if (!isDragging || ev.pointerId !== lastPointer.id) return;
    const dx = ev.clientX - dragStart.x;
    const dy = ev.clientY - dragStart.y;
    if (Math.hypot(dx, dy) > 4) {
      pointerMovedSinceDown = true;
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

    const upX = ev.clientX;
    const upY = ev.clientY;
    const timeNow = performance.now();

    if (!pointerMovedSinceDown) {
      // If a double-tap was detected on pointerdown, perform zoom and do NOT toggle an edge.
      if (suppressNextTap) {
        toggleZoom(doubleTapWorld);
        suppressNextTap = false;
        doubleTapWorld = null;
        // don't set lastTapTime/lastTapPos since this was handled as double-tap
        return;
      }

      // Single tap: toggle edge
      const world = clientToWorld(upX, upY);
      const edge = findClosestEdge(world.x, world.y);
      if (edge) toggleEdge(edge);

      // record this tap for future double-tap detection
      lastTapTime = timeNow;
      lastTapPos = { x: upX, y: upY };
    } else {
      // ended a pan; clear any pending suppression
      suppressNextTap = false;
      doubleTapWorld = null;
    }
  });

  canvas.addEventListener('pointercancel', (ev) => {
    if (lastPointer && ev.pointerId === lastPointer.id) {
      isDragging = false;
      lastPointer = null;
      suppressNextTap = false;
      doubleTapWorld = null;
    }
  });
