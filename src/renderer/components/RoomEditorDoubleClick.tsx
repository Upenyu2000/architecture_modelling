import { useEffect, type ReactNode } from 'react';
import { api } from '../lib/api';

type Point = [number, number];

function close(a: Point, b: Point, tolerance = 0.006): boolean {
  return Math.hypot(a[0] - b[0], a[1] - b[1]) <= tolerance;
}

function projectedPoint(point: Point, start: Point, end: Point): Point {
  const dx = end[0] - start[0];
  const dz = end[1] - start[1];
  const lengthSquared = dx * dx + dz * dz;
  if (lengthSquared < 1e-9) return start;
  const ratio = Math.max(0, Math.min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dz) / lengthSquared));
  return [
    Math.round((start[0] + dx * ratio) * 1000) / 1000,
    Math.round((start[1] + dz * ratio) * 1000) / 1000,
  ];
}

export function RoomEditorDoubleClick({ children }: { children: ReactNode }) {
  useEffect(() => {
    const handler = async (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof SVGLineElement) || !target.classList.contains('edge-hit-target')) return;
      event.preventDefault();
      event.stopPropagation();
      const svg = target.ownerSVGElement;
      const matrix = svg?.getScreenCTM();
      const projectId = localStorage.getItem('dreamhome.currentProject');
      if (!svg || !matrix || !projectId) return;

      const start: Point = [Number(target.getAttribute('x1')), Number(target.getAttribute('y1'))];
      const end: Point = [Number(target.getAttribute('x2')), Number(target.getAttribute('y2'))];
      if (!start.every(Number.isFinite) || !end.every(Number.isFinite)) return;
      const transformed = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
      const clicked: Point = [transformed.x, transformed.y];

      try {
        const project = await api.getProject(projectId);
        const scene = project.scene;
        if (!scene) return;
        const room = scene.rooms.find((candidate) => candidate.polygon.some((point, index) => {
          const next = candidate.polygon[(index + 1) % candidate.polygon.length];
          return (close(point, start) && close(next, end)) || (close(point, end) && close(next, start));
        }));
        if (!room || room.polygon.length >= 64) return;
        const edgeIndex = room.polygon.findIndex((point, index) => {
          const next = room.polygon[(index + 1) % room.polygon.length];
          return (close(point, start) && close(next, end)) || (close(point, end) && close(next, start));
        });
        if (edgeIndex < 0) return;
        const point = projectedPoint(clicked, room.polygon[edgeIndex], room.polygon[(edgeIndex + 1) % room.polygon.length]);
        const polygon = [...room.polygon];
        polygon.splice(edgeIndex + 1, 0, point);
        await api.updateRoomGeometry(projectId, room.id, polygon);
        window.location.reload();
      } catch (error) {
        console.error('Unable to add room vertex', error);
      }
    };
    document.addEventListener('dblclick', handler, true);
    return () => document.removeEventListener('dblclick', handler, true);
  }, []);

  return children;
}
