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
  /function FirstPersonRig\(/,
  `function FirstPersonInputGuard({ active }: { active: boolean }) {\n  const { gl } = useThree();\n  useEffect(() => {\n    if (!active) return undefined;\n    const canvas = gl.domElement;\n    canvas.tabIndex = 0;\n    const prevent = (event: Event) => event.preventDefault();\n    const focus = () => canvas.focus({ preventScroll: true });\n    const preventKeys = (event: KeyboardEvent) => {\n      if (document.pointerLockElement !== canvas) return;\n      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(event.code)) event.preventDefault();\n    };\n    const pointerLockChanged = () => {\n      const locked = document.pointerLockElement === canvas;\n      document.documentElement.classList.toggle('walkthrough-pointer-locked', locked);\n      document.body.classList.toggle('walkthrough-pointer-locked', locked);\n    };\n    canvas.addEventListener('wheel', prevent, { passive: false });\n    canvas.addEventListener('contextmenu', prevent);\n    canvas.addEventListener('pointerdown', focus);\n    window.addEventListener('keydown', preventKeys, { passive: false });\n    document.addEventListener('pointerlockchange', pointerLockChanged);\n    return () => {\n      canvas.removeEventListener('wheel', prevent);\n      canvas.removeEventListener('contextmenu', prevent);\n      canvas.removeEventListener('pointerdown', focus);\n      window.removeEventListener('keydown', preventKeys);\n      document.removeEventListener('pointerlockchange', pointerLockChanged);\n      document.documentElement.classList.remove('walkthrough-pointer-locked');\n      document.body.classList.remove('walkthrough-pointer-locked');\n    };\n  }, [active, gl]);\n  return null;\n}\n\nfunction ImportedCharacter({ url, position, visible }: { url: string; position: [number, number, number]; visible: boolean }) {\n  const gltf = useGLTF(url);\n  const model = useMemo(() => cloneSkeleton(gltf.scene), [gltf.scene]);\n  const normalisation = useMemo(() => {\n    const box = new THREE.Box3().setFromObject(model);\n    const size = box.getSize(new THREE.Vector3());\n    const scale = size.y > 0.001 ? 1.75 / size.y : 1;\n    return { scale, floorOffset: -box.min.y * scale };\n  }, [model]);\n  useEffect(() => {\n    model.traverse((child) => {\n      if (!(child instanceof THREE.Mesh)) return;\n      child.castShadow = true;\n      child.receiveShadow = true;\n      const materials = Array.isArray(child.material) ? child.material : [child.material];\n      materials.forEach((material) => {\n        if (material instanceof THREE.MeshStandardMaterial) {\n          material.envMapIntensity = 1.15;\n          material.needsUpdate = true;\n        }\n      });\n    });\n  }, [model]);\n  if (!visible) return null;\n  return <primitive object={model} position={[position[0], position[1] + normalisation.floorOffset, position[2]]} scale={normalisation.scale} />;\n}\n\nfunction RealisticEnvironment({ centreX, centreZ, largest, walkthrough }: { centreX: number; centreZ: number; largest: number; walkthrough: boolean }) {\n  return (\n    <>\n      <Environment resolution={128}>\n        <Lightformer intensity={3.2} position={[centreX, 8, centreZ + largest]} scale={[largest * 2, largest, 1]} />\n        <Lightformer intensity={1.8} position={[centreX - largest, 4, centreZ]} rotation={[0, Math.PI / 2, 0]} scale={[largest, largest, 1]} />\n        <Lightformer intensity={1.4} position={[centreX + largest, 3, centreZ]} rotation={[0, -Math.PI / 2, 0]} scale={[largest, largest, 1]} />\n      </Environment>\n      <ContactShadows position={[centreX, 0.015, centreZ]} scale={largest * 3} opacity={walkthrough ? 0.34 : 0.46} blur={2.8} far={largest * 2} resolution={1024} />\n    </>\n  );\n}\n\nfunction FirstPersonRig(`,
  'first-person input and realism components',
);

replaceOne(
  /const occupiedTypes = new Set\(scene\.fixtures_and_furniture\.map\(\(item\) => item\.object_type\)\);/,
  `const occupiedTypes = new Set(scene.fixtures_and_furniture.map((item) => item.object_type));\n  const characterAsset = project.assets['characters/walkthrough_avatar'];\n  const characterUrl = absoluteUrl(characterAsset?.mesh_url ?? characterAsset?.url);\n  const avatarPosition: [number, number, number] = scene.first_person_start\n    ? [scene.first_person_start[0], 0, scene.first_person_start[2]]\n    : [centreX, 0, centreZ];`,
  'character asset lookup',
);

replaceOne(
  /<directionalLight position=\{\[centreX \+ 8, 16, centreZ \+ 10\]\} intensity=\{2\.1\} castShadow shadow-mapSize-width=\{2048\} shadow-mapSize-height=\{2048\} \/>/,
  `<directionalLight position={[centreX + 8, 16, centreZ + 10]} intensity={2.1} castShadow shadow-mapSize-width={4096} shadow-mapSize-height={4096} shadow-bias={-0.00015} />\n      <RealisticEnvironment centreX={centreX} centreZ={centreZ} largest={largest} walkthrough={view === 'walkthrough'} />\n      {characterUrl ? <ImportedCharacter url={characterUrl} position={avatarPosition} visible={view !== 'walkthrough'} /> : null}`,
  'realistic lights and character',
);

replaceOne(
  /<WalkthroughCamera fov=\{walkthroughFov\} far=\{largest \* 12\} \/>/,
  `<FirstPersonInputGuard active />\n          <WalkthroughCamera fov={walkthroughFov} far={largest * 12} />`,
  'walkthrough input guard',
);

replaceOne(
  /<div className="three-view-wrap">/,
  `<div className={view === 'walkthrough' ? 'three-view-wrap walkthrough-active' : 'three-view-wrap'}>`,
  'walkthrough wrapper class',
);

replaceOne(
  /<Canvas shadows dpr=\{\[1, 2\]\} gl=\{\{ preserveDrawingBuffer: true, antialias: true \}\}>/,
  `<Canvas\n                shadows\n                dpr={[1, 2]}\n                gl={{ preserveDrawingBuffer: true, antialias: true, alpha: false, powerPreference: 'high-performance' }}\n                onCreated={({ gl }) => {\n                  gl.outputColorSpace = THREE.SRGBColorSpace;\n                  gl.toneMapping = THREE.ACESFilmicToneMapping;\n                  gl.toneMappingExposure = 1.08;\n                  gl.shadowMap.enabled = true;\n                  gl.shadowMap.type = THREE.PCFSoftShadowMap;\n                }}\n              >`,
  'filmic renderer settings',
);

replaceOne(
  /<small>Press Esc before adjusting controls\. Wider FOV changes only the projection matrix and never resets player position\.<\/small>/,
  '<small>Click the scene to lock the mouse to the character camera. While locked, mouse, arrows and wheel cannot scroll or move the application window. Press Esc to release.</small>',
  'pointer-lock help copy',
);

source = `// Generated by scripts/generate-v154-scene-preview.mjs. Do not edit directly.\n${source}`;
await writeFile(generatedPath, source, 'utf8');
console.log(`Generated ${path.relative(root, generatedPath)} with active panning, input lock, filmic PBR and character models.`);
