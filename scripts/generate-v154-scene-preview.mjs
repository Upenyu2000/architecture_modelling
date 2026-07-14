import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourcePath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.v153.tsx');
const generatedPath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.v154.tsx');
let source = await readFile(sourcePath, 'utf8');

function replaceOne(pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`1.5.4 scene patch could not find: ${label}`);
  source = source.replace(pattern, replacement);
}

replaceOne(
  /Grid, OrbitControls, OrthographicCamera, PerspectiveCamera, PointerLockControls, useTexture,/,
  'ContactShadows, Environment, Grid, Lightformer, OrbitControls, OrthographicCamera, PerspectiveCamera, PointerLockControls, useGLTF, useTexture,',
  'drei imports',
);

replaceOne(
  /import \* as THREE from 'three';/,
  "import * as THREE from 'three';\nimport { clone as cloneSkeleton } from 'three/examples/jsm/utils/SkeletonUtils.js';",
  'skeleton-aware clone import',
);

replaceOne(
  /import \{ RoomLayoutEditor \} from '\.\/RoomLayoutEditor';/,
  "import { RoomLayoutEditor } from './RoomLayoutEditor.v154';",
  'generated room editor import',
);

replaceOne(
  /import \{ InteriorDesignEditor \} from '\.\/InteriorDesignEditor';/,
  "import { InteriorDesignEditor } from './InteriorDesignEditor.v157';",
  'full-plan interior editor import',
);

replaceOne(
  /function FirstPersonRig\(/,
  `function FirstPersonInputGuard({ active }: { active: boolean }) {
  const { gl } = useThree();
  useEffect(() => {
    if (!active) return undefined;
    const canvas = gl.domElement;
    canvas.tabIndex = 0;
    const prevent = (event: Event) => event.preventDefault();
    const focus = () => canvas.focus({ preventScroll: true });
    const preventKeys = (event: KeyboardEvent) => {
      if (document.pointerLockElement !== canvas) return;
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(event.code)) event.preventDefault();
    };
    const pointerLockChanged = () => {
      const locked = document.pointerLockElement === canvas;
      document.documentElement.classList.toggle('walkthrough-pointer-locked', locked);
      document.body.classList.toggle('walkthrough-pointer-locked', locked);
    };
    canvas.addEventListener('wheel', prevent, { passive: false });
    canvas.addEventListener('contextmenu', prevent);
    canvas.addEventListener('pointerdown', focus);
    window.addEventListener('keydown', preventKeys, { passive: false });
    document.addEventListener('pointerlockchange', pointerLockChanged);
    return () => {
      canvas.removeEventListener('wheel', prevent);
      canvas.removeEventListener('contextmenu', prevent);
      canvas.removeEventListener('pointerdown', focus);
      window.removeEventListener('keydown', preventKeys);
      document.removeEventListener('pointerlockchange', pointerLockChanged);
      document.documentElement.classList.remove('walkthrough-pointer-locked');
      document.body.classList.remove('walkthrough-pointer-locked');
    };
  }, [active, gl]);
  return null;
}

function ImportedCharacter({ url, position, visible }: { url: string; position: [number, number, number]; visible: boolean }) {
  const gltf = useGLTF(url);
  const model = useMemo(() => cloneSkeleton(gltf.scene), [gltf.scene]);
  const normalisation = useMemo(() => {
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const scale = size.y > 0.001 ? 1.75 / size.y : 1;
    return { scale, floorOffset: -box.min.y * scale };
  }, [model]);
  useEffect(() => {
    model.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      child.castShadow = true;
      child.receiveShadow = true;
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.forEach((material) => {
        if (material instanceof THREE.MeshStandardMaterial) {
          material.envMapIntensity = 1.15;
          material.needsUpdate = true;
        }
      });
    });
  }, [model]);
  if (!visible) return null;
  return <primitive object={model} position={[position[0], position[1] + normalisation.floorOffset, position[2]]} scale={normalisation.scale} />;
}

function RealisticEnvironment({ centreX, centreZ, largest, walkthrough }: { centreX: number; centreZ: number; largest: number; walkthrough: boolean }) {
  return (
    <>
      <Environment resolution={128}>
        <Lightformer intensity={3.2} position={[centreX, 8, centreZ + largest]} scale={[largest * 2, largest, 1]} />
        <Lightformer intensity={1.8} position={[centreX - largest, 4, centreZ]} rotation={[0, Math.PI / 2, 0]} scale={[largest, largest, 1]} />
        <Lightformer intensity={1.4} position={[centreX + largest, 3, centreZ]} rotation={[0, -Math.PI / 2, 0]} scale={[largest, largest, 1]} />
      </Environment>
      <ContactShadows position={[centreX, 0.015, centreZ]} scale={largest * 3} opacity={walkthrough ? 0.34 : 0.46} blur={2.8} far={largest * 2} resolution={1024} />
    </>
  );
}

function FirstPersonRig(`,
  'first-person input and realism components',
);

replaceOne(
  /const occupiedTypes = new Set\(scene\.fixtures_and_furniture\.map\(\(item\) => item\.object_type\)\);/,
  `const occupiedTypes = new Set(scene.fixtures_and_furniture.map((item) => item.object_type));
  const characterAsset = project.assets['characters/walkthrough_avatar'];
  const characterUrl = absoluteUrl(characterAsset?.mesh_url ?? characterAsset?.url);
  const avatarPosition: [number, number, number] = scene.first_person_start
    ? [scene.first_person_start[0], 0, scene.first_person_start[2]]
    : [centreX, 0, centreZ];`,
  'character asset lookup',
);

replaceOne(
  /<directionalLight position=\{\[centreX \+ 8, 16, centreZ \+ 10\]\} intensity=\{2\.1\} castShadow shadow-mapSize-width=\{2048\} shadow-mapSize-height=\{2048\} \/>/,
  `<directionalLight position={[centreX + 8, 16, centreZ + 10]} intensity={2.1} castShadow shadow-mapSize-width={4096} shadow-mapSize-height={4096} shadow-bias={-0.00015} />
      <RealisticEnvironment centreX={centreX} centreZ={centreZ} largest={largest} walkthrough={view === 'walkthrough'} />
      {characterUrl ? <ImportedCharacter url={characterUrl} position={avatarPosition} visible={view !== 'walkthrough'} /> : null}`,
  'realistic lights and character',
);

replaceOne(
  /<WalkthroughCamera fov=\{walkthroughFov\} far=\{largest \* 12\} \/>/,
  `<FirstPersonInputGuard active />
          <WalkthroughCamera fov={walkthroughFov} far={largest * 12} />`,
  'walkthrough input guard',
);

replaceOne(
  /<div className="three-view-wrap">/,
  `<div className={view === 'walkthrough' ? 'three-view-wrap walkthrough-active' : 'three-view-wrap'}>`,
  'walkthrough wrapper class',
);

replaceOne(
  /<Canvas shadows dpr=\{\[1, 2\]\} gl=\{\{ preserveDrawingBuffer: true, antialias: true \}\}>/,
  `<Canvas
                shadows
                dpr={[1, 2]}
                gl={{ preserveDrawingBuffer: true, antialias: true, alpha: false, powerPreference: 'high-performance' }}
                onCreated={({ gl }) => {
                  gl.outputColorSpace = THREE.SRGBColorSpace;
                  gl.toneMapping = THREE.ACESFilmicToneMapping;
                  gl.toneMappingExposure = 1.08;
                  gl.shadowMap.enabled = true;
                  gl.shadowMap.type = THREE.PCFSoftShadowMap;
                }}
              >`,
  'filmic renderer settings',
);

replaceOne(
  /<small>Press Esc before adjusting controls\. Wider FOV changes only the projection matrix and never resets player position\.<\/small>/,
  '<small>Click the scene to lock the mouse to the character camera. While locked, mouse, arrows and wheel cannot scroll or move the application window. Press Esc to release.</small>',
  'pointer-lock help copy',
);

source = `// Generated by scripts/generate-v154-scene-preview.mjs. Do not edit directly.\n${source}`;
await writeFile(generatedPath, source, 'utf8');
console.log(`Generated ${path.relative(root, generatedPath)} with active panning, input lock, filmic PBR, character models and the 1.5.7 interior editor.`);
