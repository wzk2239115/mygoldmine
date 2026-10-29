import { useCallback, useEffect, useRef, useState } from 'react';

const STORAGE_KEY = 'vulboard.drawer-width';
const MIN_WIDTH = 420;
const MAX_MARGIN = 80;

function readStoredWidth() {
  const saved = Number(window.localStorage.getItem(STORAGE_KEY));
  return Number.isFinite(saved) && saved >= MIN_WIDTH ? saved : null;
}

/** Persistent width shared by the detail and live-run drawers; null = CSS default. */
export function useDrawerWidth() {
  const [width, setWidth] = useState(readStoredWidth);

  useEffect(() => {
    if (width === null) window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, String(width));
  }, [width]);

  const reset = useCallback(() => setWidth(null), []);
  return [width, setWidth, reset];
}

export default function DrawerResizer({ width, onResize, onReset }) {
  const dragStart = useRef(null);

  const clamp = useCallback(
    (value) => Math.min(Math.max(value, MIN_WIDTH), window.innerWidth - MAX_MARGIN),
    []
  );

  const handlePointerDown = useCallback(
    (event) => {
      event.preventDefault();
      dragStart.current = { x: event.clientX, width: width || event.currentTarget.parentElement.offsetWidth };
      event.currentTarget.setPointerCapture(event.pointerId);
      document.body.classList.add('drawer-resizing');
    },
    [width]
  );

  const handlePointerMove = useCallback(
    (event) => {
      const start = dragStart.current;
      if (!start) return;
      onResize(clamp(Math.round(start.width + (start.x - event.clientX))));
    },
    [clamp, onResize]
  );

  const endDrag = useCallback(
    (event) => {
      if (!dragStart.current) return;
      dragStart.current = null;
      event.currentTarget.releasePointerCapture(event.pointerId);
      document.body.classList.remove('drawer-resizing');
    },
    []
  );

  return (
    <div
      className="drawer-resizer"
      title="拖动调整宽度 · 双击恢复默认"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onDoubleClick={onReset}
    />
  );
}
