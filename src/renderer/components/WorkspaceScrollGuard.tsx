import { useEffect, type ReactNode } from 'react';

const CANVAS_INTERACTION_SELECTOR = [
  'canvas',
  '.canvas-wrap',
  '.three-view-wrap',
  '.room-layout-editor',
  '.room-editor-stage',
  '.room-editor-canvas',
  '.opening-editor-stage',
  '.interior-editor-stage',
  '.detection-view',
].join(',');

interface WorkspaceScrollGuardProps {
  children: ReactNode;
}

/**
 * Keeps the synchronized viewport fixed while normal wheel scrolling is routed
 * to the left control rail. Wheel and trackpad input inside an active canvas or
 * editor remains untouched so zooming, panning and first-person interaction
 * continue to work normally.
 */
export function WorkspaceScrollGuard({ children }: WorkspaceScrollGuardProps) {
  useEffect(() => {
    const handleWheel = (event: WheelEvent) => {
      if (window.matchMedia('(max-width: 1280px)').matches) return;

      const target = event.target instanceof Element ? event.target : null;
      const rightColumn = document.querySelector<HTMLElement>('.right-column');
      const leftColumn = document.querySelector<HTMLElement>('.left-column');

      if (!target || !rightColumn || !leftColumn || !rightColumn.contains(target)) return;

      // Do not intercept canvas/editor gestures. They own wheel/pinch input for
      // zooming, plan navigation and the pointer-locked walkthrough.
      if (target.closest(CANVAS_INTERACTION_SELECTOR)) return;
      if (event.ctrlKey || event.metaKey) return;

      event.preventDefault();
      leftColumn.scrollBy({
        top: event.deltaY,
        left: event.deltaX,
        behavior: 'auto',
      });
    };

    document.addEventListener('wheel', handleWheel, { capture: true, passive: false });
    document.title = 'Dream Home Visualizer 1.5.6';

    return () => {
      document.removeEventListener('wheel', handleWheel, true);
    };
  }, []);

  return children;
}
