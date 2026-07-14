import { readFileSync } from 'node:fs';

const scene = readFileSync(new URL('../src/renderer/components/ScenePreview.tsx', import.meta.url), 'utf8');
const editor = readFileSync(new URL('../src/renderer/components/RoomLayoutEditor.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/renderer/stability-1.5.2.css', import.meta.url), 'utf8');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(!/<PerspectiveCamera[^>]*\bposition=/.test(scene), 'Walkthrough camera must not receive a spawn position prop.');
assert(scene.includes('playerPositionRef'), 'Walkthrough must persist the live player position.');
assert(scene.includes('WalkthroughCamera'), 'Dynamic FOV camera component is missing.');
assert(scene.includes('updateProjectionMatrix()'), 'FOV changes must update the projection matrix.');
assert(scene.includes('DEFAULT_FOV = 88'), 'The wider 88-degree default FOV is missing.');
assert(scene.includes('DEFAULT_PLAYER_RADIUS = 0.16'), 'The reduced default collision radius is missing.');
assert(scene.includes('MAX_MOVEMENT_STEP'), 'Sub-stepped collision movement is missing.');
assert(scene.includes('pointIsBlocked'), 'Exterior and wall collision boundary logic is missing.');
assert(editor.includes('onWheel={handleWheel}'), 'Mouse-wheel plan zoom is missing.');
assert(editor.includes('viewBox={viewport.value}'), 'Centred zoomable SVG viewport is missing.');
assert(editor.includes('DEFAULT_ZOOM = 0.8'), 'Zoomed-out default floor-plan scale is missing.');
assert(styles.includes('grid-template-columns: minmax(360px, 420px) minmax(720px, 1fr)'), 'The fixed left/right workspace layout is missing.');
assert(styles.includes('.right-column'), 'The synchronized viewport right-column guard is missing.');

console.log('UI stability smoke test passed: persistent walkthrough, FOV/radius controls, plan zoom and right-hand viewport');
