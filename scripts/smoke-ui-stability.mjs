import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/renderer/App.tsx', import.meta.url), 'utf8');
const main = readFileSync(new URL('../src/renderer/main.tsx', import.meta.url), 'utf8');
const scene = readFileSync(new URL('../src/renderer/components/ScenePreview.v154.tsx', import.meta.url), 'utf8');
const editor = readFileSync(new URL('../src/renderer/components/RoomLayoutEditor.v154.tsx', import.meta.url), 'utf8');
const scrollGuard = readFileSync(new URL('../src/renderer/components/WorkspaceScrollGuard.tsx', import.meta.url), 'utf8');
const runtimeStyles = readFileSync(new URL('../src/renderer/runtime-1.5.4.css', import.meta.url), 'utf8');
const standaloneStyles = readFileSync(new URL('../src/renderer/standalone-layout-1.5.5.css', import.meta.url), 'utf8');
const fixedWorkspaceStyles = readFileSync(new URL('../src/renderer/fixed-workspace-1.5.6.css', import.meta.url), 'utf8');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(app.includes("./components/ScenePreview.v154"), 'The application must import the generated 1.5.4 viewport at runtime.');
assert(main.includes("./standalone-layout-1.5.5.css"), 'The standalone layout guard must load after earlier viewport styles.');
assert(main.includes("./fixed-workspace-1.5.6.css"), 'The fixed 1.5.6 workspace styles must load last.');
assert(main.includes('WorkspaceScrollGuard'), 'The right-column wheel routing guard is not active.');
assert(!/<PerspectiveCamera[^>]*\bposition=/.test(scene), 'Walkthrough camera must not receive a spawn position prop.');
assert(scene.includes('playerPositionRef'), 'Walkthrough must persist the live player position.');
assert(scene.includes('WalkthroughCamera'), 'Dynamic FOV camera component is missing.');
assert(scene.includes('updateProjectionMatrix()'), 'FOV changes must update the projection matrix.');
assert(scene.includes('DEFAULT_FOV = 100'), 'The wider 100-degree default FOV is missing.');
assert(scene.includes('max="120"'), 'The 120-degree FOV range is missing.');
assert(scene.includes('WALKTHROUGH_HORIZONTAL_SCALE = 2'), 'The two-times horizontal walkthrough scale is missing.');
assert(scene.includes('viewport-pan-controls'), 'Directional synchronized viewport pan buttons are missing.');
assert(scene.includes('FirstPersonInputGuard'), 'First-person mouse/window input isolation is missing.');
assert(scene.includes('ACESFilmicToneMapping'), 'Filmic tone mapping is missing.');
assert(scene.includes('ImportedCharacter'), 'Normalised realistic character model support is missing.');
assert(editor.includes("type EditMode = 'pan'"), 'Edit Rooms pan mode is missing.');
assert(editor.includes('room-pan-controls'), 'Edit Rooms directional pan buttons are missing.');
assert(editor.includes('panDragRef'), 'Edit Rooms mouse panning is missing.');
assert(editor.includes('onWheel={handleWheel}'), 'Mouse-wheel plan zoom is missing.');
assert(editor.includes('viewBox={viewport.value}'), 'Pannable zoomable SVG viewport is missing.');
assert(runtimeStyles.includes('grid-template-columns: clamp(330px, 27vw, 420px) minmax(0, 1fr)'), 'Adaptive base workspace is missing.');
assert(runtimeStyles.includes('.walkthrough-active canvas'), 'First-person canvas input containment styles are missing.');
assert(runtimeStyles.includes('.room-pan-controls'), 'Edit Rooms pan styling is missing.');
assert(standaloneStyles.includes('--workspace-column-gap: clamp(72px, 6vw, 120px)'), 'The widened protected renderer gutter is missing.');
assert(standaloneStyles.includes('.left-column::before'), 'The opaque safety gutter between controls and rendering is missing.');
assert(standaloneStyles.includes('contain: layout paint style'), 'Independent paint containment is missing.');
assert(/background:\s*linear-gradient/.test(standaloneStyles), 'The opaque standalone control-rail background is missing.');
assert(standaloneStyles.includes('@media (max-width: 1280px)'), 'The early non-overlap stacking breakpoint is missing.');
assert(standaloneStyles.includes('.three-view-wrap canvas'), 'WebGL canvas width containment is missing.');
assert(fixedWorkspaceStyles.includes('height: 100dvh'), 'The desktop shell must be constrained to the viewport height.');
assert(fixedWorkspaceStyles.includes('overflow-y: auto !important'), 'The left rail must own vertical scrolling.');
assert(fixedWorkspaceStyles.includes('position: sticky !important'), 'The synchronized right workspace must remain pinned.');
assert(fixedWorkspaceStyles.includes('grid-template-rows: minmax(0, 1fr) auto auto'), 'The fixed right column must reserve flexible canvas space and fixed output rows.');
assert(fixedWorkspaceStyles.includes('.right-column canvas'), 'Canvas sizing must be contained inside the fixed viewport.');
assert(scrollGuard.includes("document.querySelector<HTMLElement>('.left-column')"), 'The scroll guard cannot find the left rail.');
assert(scrollGuard.includes("document.querySelector<HTMLElement>('.right-column')"), 'The scroll guard cannot find the right workspace.');
assert(scrollGuard.includes('target.closest(CANVAS_INTERACTION_SELECTOR)'), 'Canvas interaction must bypass normal scroll redirection.');
assert(scrollGuard.includes('leftColumn.scrollBy'), 'Non-canvas right-column wheel input must scroll the left rail.');

console.log('UI stability smoke test passed: fixed right workspace, independently scrolling left rail, canvas gesture isolation, protected gutter, room panning, input lock, PBR and character assets');
