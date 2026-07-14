import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourcePath = path.join(root, 'src', 'renderer', 'components', 'RoomLayoutEditor.tsx');
const generatedPath = path.join(root, 'src', 'renderer', 'components', 'RoomLayoutEditor.v154.tsx');
let source = await readFile(sourcePath, 'utf8');

function replaceOne(pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`1.5.4 room-editor patch could not find: ${label}`);
  source = source.replace(pattern, replacement);
}

replaceOne(
  /import \{ Maximize2, Move, Plus, Trash2, ZoomIn, ZoomOut \} from 'lucide-react';/,
  "import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Hand, LocateFixed, Maximize2, Move, Plus, Trash2, ZoomIn, ZoomOut } from 'lucide-react';",
  'room editor icon import',
);

replaceOne(
  /type EditMode = 'move' \| 'vertices' \| 'add-point' \| 'remove-point';/,
  "type EditMode = 'pan' | 'move' | 'vertices' | 'add-point' | 'remove-point';",
  'pan edit mode',
);

replaceOne(
  /type DragState = \{[\s\S]*?\n\};\n\ninterface Props/,
  (match) => match.replace('\n\ninterface Props', `\n\ntype PanDragState = {\n  pointerId: number;\n  startClient: Point;\n  startPan: Point;\n};\n\ninterface Props`),
  'pan drag state',
);

replaceOne(
  /const svgRef = useRef<SVGSVGElement \| null>\(null\);\n  const dragRef = useRef<DragState \| null>\(null\);/,
  `const svgRef = useRef<SVGSVGElement | null>(null);\n  const dragRef = useRef<DragState | null>(null);\n  const panDragRef = useRef<PanDragState | null>(null);`,
  'pan ref',
);

replaceOne(
  /const \[zoom, setZoom\] = useState\(DEFAULT_ZOOM\);/,
  `const [zoom, setZoom] = useState(DEFAULT_ZOOM);\n  const [viewPan, setViewPan] = useState<Point>([0, 0]);`,
  'pan state',
);

replaceOne(
  /const beginMove = \(event: React\.PointerEvent<SVGPolygonElement>, room: RoomShape\) => \{\n    event\.preventDefault\(\);\n    event\.stopPropagation\(\);\n    setSelectedId\(room\.id\);\n    if \(busy \|\| editMode !== 'move'\) return;/,
  `const beginMove = (event: React.PointerEvent<SVGPolygonElement>, room: RoomShape) => {\n    setSelectedId(room.id);\n    if (editMode === 'pan' || event.button === 1 || event.shiftKey) return;\n    event.preventDefault();\n    event.stopPropagation();\n    if (busy || editMode !== 'move') return;`,
  'room pointer routing',
);

replaceOne(
  /const movePointer = \(event: React\.PointerEvent<SVGSVGElement>\) => \{\n    const drag = dragRef\.current;/,
  `const movePointer = (event: React.PointerEvent<SVGSVGElement>) => {\n    const panDrag = panDragRef.current;\n    if (panDrag) {\n      const svg = svgRef.current;\n      if (!svg) return;\n      const dx = event.clientX - panDrag.startClient[0];\n      const dy = event.clientY - panDrag.startClient[1];\n      const maxPanX = Math.max(scene.width_m, viewport.width) * 0.7;\n      const maxPanZ = Math.max(scene.depth_m, viewport.height) * 0.7;\n      setViewPan([\n        clamp(panDrag.startPan[0] - dx * viewport.width / Math.max(svg.clientWidth, 1), -maxPanX, maxPanX),\n        clamp(panDrag.startPan[1] - dy * viewport.height / Math.max(svg.clientHeight, 1), -maxPanZ, maxPanZ),\n      ]);\n      return;\n    }\n    const drag = dragRef.current;`,
  'mouse pan movement',
);

replaceOne(
  /const finishPointer = \(event: React\.PointerEvent<SVGSVGElement>\) => \{\n    const drag = dragRef\.current;/,
  `const finishPointer = (event: React.PointerEvent<SVGSVGElement>) => {\n    if (panDragRef.current) {\n      panDragRef.current = null;\n      if (svgRef.current?.hasPointerCapture(event.pointerId)) svgRef.current.releasePointerCapture(event.pointerId);\n      return;\n    }\n    const drag = dragRef.current;`,
  'finish pan movement',
);

replaceOne(
  /const setClampedZoom = \(value: number\) => setZoom\(clamp\(value, MIN_ZOOM, MAX_ZOOM\)\);[\s\S]*?const viewport = useMemo\(\(\) => \{\n    const width = scene\.width_m \/ zoom;\n    const height = scene\.depth_m \/ zoom;\n    return \{\n      x: \(scene\.width_m - width\) \/ 2,\n      y: \(scene\.depth_m - height\) \/ 2,\n      width,\n      height,\n      value: `\$\{\(scene\.width_m - width\) \/ 2\} \$\{\(scene\.depth_m - height\) \/ 2\} \$\{width\} \$\{height\}`,\n    \};\n  \}, \[scene\.width_m, scene\.depth_m, zoom\]\);/,
  `const setClampedZoom = (value: number) => setZoom(clamp(value, MIN_ZOOM, MAX_ZOOM));\n  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {\n    event.preventDefault();\n    const multiplier = event.deltaY < 0 ? 1.1 : 1 / 1.1;\n    setZoom((current) => clamp(current * multiplier, MIN_ZOOM, MAX_ZOOM));\n  };\n\n  const viewport = useMemo(() => {\n    const width = scene.width_m / zoom;\n    const height = scene.depth_m / zoom;\n    const x = (scene.width_m - width) / 2 + viewPan[0];\n    const y = (scene.depth_m - height) / 2 + viewPan[1];\n    return { x, y, width, height, value: \`${'${x} ${y} ${width} ${height}'}\` };\n  }, [scene.width_m, scene.depth_m, zoom, viewPan]);\n\n  const beginPan = (event: React.PointerEvent<SVGSVGElement>) => {\n    const shouldPan = editMode === 'pan' || event.button === 1 || (event.button === 0 && event.shiftKey);\n    if (!shouldPan) return;\n    event.preventDefault();\n    panDragRef.current = { pointerId: event.pointerId, startClient: [event.clientX, event.clientY], startPan: viewPan };\n    svgRef.current?.setPointerCapture(event.pointerId);\n  };\n  const panBy = (dx: number, dz: number) => {\n    const step = Math.max(viewport.width, viewport.height) * 0.12;\n    setViewPan(([x, z]) => [x + dx * step, z + dz * step]);\n  };\n  const resetView = () => { setZoom(DEFAULT_ZOOM); setViewPan([0, 0]); };`,
  'zoomable pannable viewport',
);

replaceOne(
  /<div className="room-editor-modebar">\n        <button className=\{editMode === 'move'/,
  `<div className="room-editor-modebar">\n        <button className={editMode === 'pan' ? 'active' : ''} onClick={() => setEditMode('pan')}><Hand size={15} /> Pan view</button>\n        <button className={editMode === 'move'`,
  'pan mode button',
);

replaceOne(
  /<button type="button" title="Fit complete plan" onClick=\{\(\) => setZoom\(DEFAULT_ZOOM\)\}>/,
  '<button type="button" title="Fit complete plan" onClick={resetView}>',
  'fit plan resets pan',
);

replaceOne(
  /<\/div>\n      <\/div>\n\n      <div className="room-editor-stage"/,
  `</div>\n        <div className="room-pan-controls" aria-label="Room editor pan controls">\n          <button className="pan-up" title="Pan up" onClick={() => panBy(0, -1)}><ArrowUp size={15} /></button>\n          <button className="pan-left" title="Pan left" onClick={() => panBy(-1, 0)}><ArrowLeft size={15} /></button>\n          <button className="pan-reset" title="Centre plan" onClick={() => setViewPan([0, 0])}><LocateFixed size={15} /></button>\n          <button className="pan-right" title="Pan right" onClick={() => panBy(1, 0)}><ArrowRight size={15} /></button>\n          <button className="pan-down" title="Pan down" onClick={() => panBy(0, 1)}><ArrowDown size={15} /></button>\n        </div>\n      </div>\n\n      <div className={\`room-editor-stage ${'${editMode === \'pan\' ? \'is-panning\' : \'\'}'}\`}`,
  'room pan buttons',
);

replaceOne(
  /preserveAspectRatio="xMidYMid meet"\n          onPointerMove=/,
  `preserveAspectRatio="xMidYMid meet"\n          onPointerDown={beginPan}\n          onPointerMove=`,
  'SVG pan pointer start',
);

replaceOne(
  /\{editMode === 'move' && <><Move size=\{15\} \/> Drag room; use corner handles to scale\.<\/\>\}/,
  `{editMode === 'pan' && <><Hand size={15} /> Drag anywhere, middle-drag or Shift-drag to pan the plan.</>}\n          {editMode === 'move' && <><Move size={15} /> Drag room; use corner handles to scale.</>}`,
  'pan help copy',
);

source = `// Generated by scripts/generate-v154-room-editor.mjs. Do not edit directly.\n${source}`;
await writeFile(generatedPath, source, 'utf8');
console.log(`Generated ${path.relative(root, generatedPath)} with mouse and button panning.`);
