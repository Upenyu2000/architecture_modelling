import { useMemo } from 'react';
import { RoundedBox, useTexture } from '@react-three/drei';
import * as THREE from 'three';

export type FurnitureMaterialProfile = 'fabric' | 'leather' | 'oak' | 'walnut' | 'stone' | 'porcelain' | 'chrome' | 'painted_metal';

export interface FurnitureStyle {
  style: string;
  material: FurnitureMaterialProfile;
  color: string;
  referenceAssetKey?: string;
}

export interface FurnitureModelProps {
  id: string;
  objectType: string;
  position: [number, number, number];
  size: [number, number, number];
  rotationDeg?: number;
  style?: FurnitureStyle;
  textureUrl?: string;
  selected?: boolean;
  visible?: boolean;
  onSelect?: () => void;
}

const DEFAULT_STYLE: FurnitureStyle = {
  style: 'modern',
  material: 'fabric',
  color: '#486B5A',
};

export function decodeFurnitureAssetId(assetId?: string): FurnitureStyle {
  const [model, style, material, color, referenceAssetKey] = String(assetId ?? '').split('|');
  void model;
  const validMaterial = new Set<FurnitureMaterialProfile>([
    'fabric', 'leather', 'oak', 'walnut', 'stone', 'porcelain', 'chrome', 'painted_metal',
  ]);
  return {
    style: style || DEFAULT_STYLE.style,
    material: validMaterial.has(material as FurnitureMaterialProfile) ? material as FurnitureMaterialProfile : DEFAULT_STYLE.material,
    color: /^#[0-9a-f]{6}$/i.test(color || '') ? color : DEFAULT_STYLE.color,
    referenceAssetKey: referenceAssetKey || undefined,
  };
}

export function encodeFurnitureAssetId(objectType: string, style: FurnitureStyle): string {
  return [objectType, style.style, style.material, style.color, style.referenceAssetKey ?? ''].join('|');
}

function shade(hex: string, amount: number): string {
  const value = Number.parseInt(hex.replace('#', ''), 16);
  if (!Number.isFinite(value)) return hex;
  const clamp = (component: number) => Math.max(0, Math.min(255, component));
  const r = clamp((value >> 16) + amount);
  const g = clamp(((value >> 8) & 255) + amount);
  const b = clamp((value & 255) + amount);
  return `#${[r, g, b].map((component) => component.toString(16).padStart(2, '0')).join('')}`;
}

function useGeneratedSurface(profile: FurnitureMaterialProfile, color: string): THREE.CanvasTexture {
  return useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const context = canvas.getContext('2d');
    if (!context) return new THREE.CanvasTexture(canvas);
    context.fillStyle = color;
    context.fillRect(0, 0, 128, 128);
    const seed = Number.parseInt(color.replace('#', ''), 16) || 17;
    let state = seed >>> 0;
    const random = () => {
      state = (state * 1664525 + 1013904223) >>> 0;
      return state / 0xffffffff;
    };
    if (profile === 'fabric') {
      context.lineWidth = 1;
      for (let index = 0; index < 128; index += 4) {
        context.strokeStyle = index % 8 === 0 ? 'rgba(255,255,255,.10)' : 'rgba(0,0,0,.08)';
        context.beginPath(); context.moveTo(index, 0); context.lineTo(index, 128); context.stroke();
        context.beginPath(); context.moveTo(0, index); context.lineTo(128, index); context.stroke();
      }
    } else if (profile === 'leather') {
      for (let index = 0; index < 1200; index += 1) {
        const alpha = 0.025 + random() * 0.055;
        context.fillStyle = random() > 0.5 ? `rgba(255,255,255,${alpha})` : `rgba(0,0,0,${alpha})`;
        const radius = 0.4 + random() * 1.5;
        context.beginPath(); context.arc(random() * 128, random() * 128, radius, 0, Math.PI * 2); context.fill();
      }
    } else if (profile === 'oak' || profile === 'walnut') {
      for (let index = 0; index < 95; index += 1) {
        const x = random() * 128;
        const width = 0.35 + random() * 1.8;
        context.strokeStyle = profile === 'walnut' ? `rgba(30,12,4,${0.08 + random() * 0.22})` : `rgba(74,43,16,${0.05 + random() * 0.16})`;
        context.lineWidth = width;
        context.beginPath();
        context.moveTo(x, 0);
        for (let y = 0; y <= 128; y += 8) context.lineTo(x + Math.sin((y + index) * 0.08) * (1 + random() * 2.5), y);
        context.stroke();
      }
    } else if (profile === 'stone' || profile === 'porcelain') {
      for (let index = 0; index < 900; index += 1) {
        const alpha = profile === 'stone' ? 0.12 : 0.045;
        context.fillStyle = random() > 0.45 ? `rgba(255,255,255,${alpha})` : `rgba(20,20,20,${alpha})`;
        context.fillRect(random() * 128, random() * 128, 0.6 + random() * 2.2, 0.6 + random() * 2.2);
      }
    } else {
      const gradient = context.createLinearGradient(0, 0, 128, 128);
      gradient.addColorStop(0, 'rgba(255,255,255,.28)');
      gradient.addColorStop(0.35, 'rgba(255,255,255,.03)');
      gradient.addColorStop(1, 'rgba(0,0,0,.24)');
      context.fillStyle = gradient;
      context.fillRect(0, 0, 128, 128);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(profile === 'fabric' ? 4 : 2, profile === 'fabric' ? 4 : 2);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 8;
    texture.needsUpdate = true;
    return texture;
  }, [profile, color]);
}

function UploadedMaterial({ url, profile, color }: { url: string; profile: FurnitureMaterialProfile; color: string }) {
  const texture = useTexture(url);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(2, 2);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  const metallic = profile === 'chrome' || profile === 'painted_metal' ? 0.78 : 0.02;
  const roughness = profile === 'leather' ? 0.34 : profile === 'chrome' ? 0.2 : profile === 'stone' ? 0.52 : 0.62;
  return <meshPhysicalMaterial map={texture} color={color} roughness={roughness} metalness={metallic} clearcoat={profile === 'leather' ? 0.22 : 0.05} clearcoatRoughness={0.35} />;
}

function Surface({ profile, color, textureUrl }: { profile: FurnitureMaterialProfile; color: string; textureUrl?: string }) {
  const generated = useGeneratedSurface(profile, color);
  if (textureUrl) return <UploadedMaterial url={textureUrl} profile={profile} color={color} />;
  const metallic = profile === 'chrome' || profile === 'painted_metal' ? 0.82 : 0.02;
  const roughness = profile === 'fabric' ? 0.78 : profile === 'leather' ? 0.34 : profile === 'chrome' ? 0.18 : profile === 'porcelain' ? 0.24 : profile === 'stone' ? 0.54 : 0.48;
  return <meshPhysicalMaterial map={generated} bumpMap={generated} bumpScale={profile === 'fabric' ? 0.012 : profile === 'leather' ? 0.006 : 0.018} color={color} roughness={roughness} metalness={metallic} clearcoat={profile === 'leather' || profile === 'porcelain' ? 0.28 : 0.04} clearcoatRoughness={0.32} />;
}

function Metal({ color = '#A6ADB2', roughness = 0.24 }: { color?: string; roughness?: number }) {
  return <meshStandardMaterial color={color} roughness={roughness} metalness={0.9} />;
}

function SoftPart({ position, size, style, textureUrl, radius = 0.08 }: {
  position: [number, number, number];
  size: [number, number, number];
  style: FurnitureStyle;
  textureUrl?: string;
  radius?: number;
}) {
  return (
    <RoundedBox args={size} radius={Math.min(radius, Math.min(...size) * 0.35)} smoothness={4} position={position} castShadow receiveShadow>
      <Surface profile={style.material} color={style.color} textureUrl={textureUrl} />
    </RoundedBox>
  );
}

function Sofa({ size: [sx, sy, sz], style, textureUrl }: { size: [number, number, number]; style: FurnitureStyle; textureUrl?: string }) {
  const seats = sx > 2.35 ? 3 : 2;
  const seatWidth = sx * 0.72 / seats;
  return (
    <group>
      <SoftPart position={[0, sy * 0.28, 0]} size={[sx * 0.9, sy * 0.3, sz * 0.82]} style={{ ...style, color: shade(style.color, -18) }} textureUrl={textureUrl} radius={0.1} />
      <SoftPart position={[-sx * 0.43, sy * 0.55, 0]} size={[sx * 0.14, sy * 0.64, sz * 0.9]} style={style} textureUrl={textureUrl} radius={0.1} />
      <SoftPart position={[sx * 0.43, sy * 0.55, 0]} size={[sx * 0.14, sy * 0.64, sz * 0.9]} style={style} textureUrl={textureUrl} radius={0.1} />
      {Array.from({ length: seats }, (_, index) => {
        const x = (index - (seats - 1) / 2) * seatWidth;
        return <SoftPart key={`seat-${index}`} position={[x, sy * 0.5, sz * 0.08]} size={[seatWidth * 0.92, sy * 0.22, sz * 0.62]} style={style} textureUrl={textureUrl} radius={0.075} />;
      })}
      {Array.from({ length: seats }, (_, index) => {
        const x = (index - (seats - 1) / 2) * seatWidth;
        return <SoftPart key={`back-${index}`} position={[x, sy * 0.83, -sz * 0.31]} size={[seatWidth * 0.94, sy * 0.54, sz * 0.2]} style={{ ...style, color: shade(style.color, 8) }} textureUrl={textureUrl} radius={0.09} />;
      })}
      {[-1, 1].flatMap((xSign) => [-1, 1].map((zSign) => (
        <mesh key={`${xSign}-${zSign}`} position={[xSign * sx * 0.36, sy * 0.09, zSign * sz * 0.31]} castShadow>
          <cylinderGeometry args={[0.035, 0.045, sy * 0.18, 16]} /><Metal color={style.style === 'classic' ? '#5B3824' : '#AEB7BC'} />
        </mesh>
      )))}
    </group>
  );
}

function Armchair({ size, style, textureUrl }: { size: [number, number, number]; style: FurnitureStyle; textureUrl?: string }) {
  return <Sofa size={[Math.min(size[0], 1.15), size[1], Math.min(size[2], 1.05)]} style={style} textureUrl={textureUrl} />;
}

function Bed({ size: [sx, sy, sz], style, textureUrl }: { size: [number, number, number]; style: FurnitureStyle; textureUrl?: string }) {
  const wood: FurnitureStyle = { ...style, material: style.material === 'fabric' ? 'walnut' : style.material, color: style.material === 'fabric' ? '#704A32' : style.color };
  return (
    <group>
      <SoftPart position={[0, sy * 0.22, 0]} size={[sx, sy * 0.3, sz]} style={wood} textureUrl={textureUrl} radius={0.04} />
      <SoftPart position={[0, sy * 0.49, sz * 0.02]} size={[sx * 0.96, sy * 0.34, sz * 0.92]} style={{ ...style, material: 'fabric', color: '#E9E5DC' }} radius={0.09} />
      <SoftPart position={[0, sy * 0.92, -sz * 0.46]} size={[sx, sy * 1.05, sz * 0.09]} style={wood} textureUrl={textureUrl} radius={0.04} />
      {[-0.26, 0.26].map((x) => <SoftPart key={x} position={[sx * x, sy * 0.73, -sz * 0.23]} size={[sx * 0.38, sy * 0.22, sz * 0.28]} style={{ ...style, material: 'fabric', color: '#F7F5EF' }} radius={0.08} />)}
      <SoftPart position={[0, sy * 0.65, sz * 0.17]} size={[sx * 0.9, sy * 0.08, sz * 0.52]} style={{ ...style, material: 'fabric', color: shade(style.color, 22) }} radius={0.035} />
    </group>
  );
}

function Table({ size: [sx, sy, sz], style, textureUrl, dining = false }: { size: [number, number, number]; style: FurnitureStyle; textureUrl?: string; dining?: boolean }) {
  const topStyle = { ...style, material: style.material === 'fabric' ? 'walnut' as const : style.material };
  const legHeight = sy * 0.82;
  return (
    <group>
      <SoftPart position={[0, sy * 0.91, 0]} size={[sx, sy * 0.14, sz]} style={topStyle} textureUrl={textureUrl} radius={0.035} />
      {[-1, 1].flatMap((xSign) => [-1, 1].map((zSign) => (
        <mesh key={`${xSign}-${zSign}`} position={[xSign * sx * 0.39, legHeight * 0.5, zSign * sz * 0.34]} castShadow>
          <cylinderGeometry args={[dining ? 0.055 : 0.04, dining ? 0.065 : 0.05, legHeight, 20]} />
          {style.style === 'industrial' ? <Metal color="#252A2D" /> : <Surface profile={topStyle.material} color={shade(topStyle.color, -20)} textureUrl={textureUrl} />}
        </mesh>
      )))}
      {dining ? [-1, 1].flatMap((side) => [-0.28, 0.28].map((offset) => (
        <group key={`${side}-${offset}`} position={[offset * sx, 0, side * sz * 0.82]} rotation={[0, side < 0 ? Math.PI : 0, 0]}>
          <SoftPart position={[0, sy * 0.48, 0]} size={[sx * 0.2, sy * 0.1, sz * 0.28]} style={{ ...style, material: 'fabric' }} radius={0.035} />
          <SoftPart position={[0, sy * 0.73, sz * 0.1]} size={[sx * 0.2, sy * 0.48, sz * 0.08]} style={{ ...style, material: 'fabric' }} radius={0.035} />
          {[-1, 1].map((leg) => <mesh key={leg} position={[leg * sx * 0.075, sy * 0.22, 0]}><cylinderGeometry args={[0.025, 0.03, sy * 0.44, 12]} /><Metal color="#33393C" /></mesh>)}
        </group>
      ))) : null}
    </group>
  );
}

function Storage({ size: [sx, sy, sz], style, textureUrl, wardrobe = false }: { size: [number, number, number]; style: FurnitureStyle; textureUrl?: string; wardrobe?: boolean }) {
  const material = style.material === 'fabric' ? 'walnut' : style.material;
  return (
    <group>
      <SoftPart position={[0, sy * 0.5, 0]} size={[sx, sy, sz]} style={{ ...style, material }} textureUrl={textureUrl} radius={0.025} />
      <mesh position={[0, sy * 0.5, sz * 0.505]}>
        <boxGeometry args={[0.015, sy * 0.86, 0.018]} /><Metal color="#2E3436" />
      </mesh>
      {[-0.24, 0.24].map((x) => <mesh key={x} position={[sx * x, sy * 0.52, sz * 0.525]}><cylinderGeometry args={[0.012, 0.012, wardrobe ? 0.22 : 0.1, 12]} /><Metal color="#C2C8C9" /></mesh>)}
      {!wardrobe ? <mesh position={[0, sy * 0.72, sz * 0.54]}><boxGeometry args={[sx * 0.72, sy * 0.035, 0.02]} /><Metal color="#1A1E20" /></mesh> : null}
    </group>
  );
}

function Appliance({ type, size: [sx, sy, sz], style, textureUrl }: { type: string; size: [number, number, number]; style: FurnitureStyle; textureUrl?: string }) {
  const bodyStyle: FurnitureStyle = { ...style, material: style.material === 'fabric' ? 'painted_metal' : style.material, color: style.color || '#B5BDC1' };
  const frontZ = sz * 0.51;
  return (
    <group>
      <SoftPart position={[0, sy * 0.5, 0]} size={[sx, sy, sz]} style={bodyStyle} textureUrl={textureUrl} radius={0.035} />
      {type === 'fridge' ? (
        <>
          <mesh position={[0, sy * 0.56, frontZ]}><boxGeometry args={[sx * 0.9, 0.018, 0.02]} /><Metal color="#31383B" /></mesh>
          <mesh position={[sx * 0.32, sy * 0.58, frontZ + 0.02]}><cylinderGeometry args={[0.018, 0.018, sy * 0.42, 12]} /><Metal /></mesh>
        </>
      ) : null}
      {type === 'stove' ? (
        <>
          {[[-0.25, -0.23], [0.25, -0.23], [-0.25, 0.23], [0.25, 0.23]].map(([x, z], index) => <mesh key={index} position={[x * sx, sy * 1.01, z * sz]} rotation={[-Math.PI / 2, 0, 0]}><torusGeometry args={[Math.min(sx, sz) * 0.13, 0.014, 10, 28]} /><Metal color="#15191B" /></mesh>)}
          <mesh position={[0, sy * 0.48, frontZ + 0.015]}><boxGeometry args={[sx * 0.72, sy * 0.48, 0.025]} /><meshPhysicalMaterial color="#11191D" roughness={0.12} metalness={0.35} /></mesh>
          {[-0.3, -0.1, 0.1, 0.3].map((x) => <mesh key={x} position={[x * sx, sy * 0.82, frontZ + 0.04]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.035, 0.035, 0.035, 16]} /><Metal color="#24292C" /></mesh>)}
        </>
      ) : null}
      {type === 'washing_machine' || type === 'dryer' ? (
        <>
          <mesh position={[0, sy * 0.52, frontZ + 0.02]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[sx * 0.28, sx * 0.045, 16, 48]} /><Metal color="#252B2E" /></mesh>
          <mesh position={[0, sy * 0.52, frontZ + 0.025]}><circleGeometry args={[sx * 0.235, 48]} /><meshPhysicalMaterial color="#243641" roughness={0.08} metalness={0.15} transparent opacity={0.72} /></mesh>
          <mesh position={[0, sy * 0.86, frontZ + 0.025]}><boxGeometry args={[sx * 0.72, sy * 0.09, 0.02]} /><meshStandardMaterial color="#22282B" roughness={0.3} metalness={0.65} /></mesh>
        </>
      ) : null}
    </group>
  );
}

function BathroomFixture({ type, size: [sx, sy, sz], style }: { type: string; size: [number, number, number]; style: FurnitureStyle }) {
  const porcelain: FurnitureStyle = { ...style, material: 'porcelain', color: '#F2F2EE' };
  if (type === 'bathtub') {
    return (
      <group>
        <SoftPart position={[0, sy * 0.42, -sz * 0.42]} size={[sx, sy * 0.84, sz * 0.16]} style={porcelain} radius={0.07} />
        <SoftPart position={[0, sy * 0.42, sz * 0.42]} size={[sx, sy * 0.84, sz * 0.16]} style={porcelain} radius={0.07} />
        <SoftPart position={[-sx * 0.43, sy * 0.42, 0]} size={[sx * 0.16, sy * 0.84, sz * 0.7]} style={porcelain} radius={0.07} />
        <SoftPart position={[sx * 0.43, sy * 0.42, 0]} size={[sx * 0.16, sy * 0.84, sz * 0.7]} style={porcelain} radius={0.07} />
        <mesh position={[0, sy * 0.25, 0]}><boxGeometry args={[sx * 0.74, sy * 0.06, sz * 0.62]} /><meshPhysicalMaterial color="#8CC6DA" roughness={0.08} transmission={0.2} transparent opacity={0.75} /></mesh>
        <mesh position={[sx * 0.31, sy * 0.92, -sz * 0.34]}><torusGeometry args={[0.09, 0.016, 10, 24, Math.PI]} /><Metal /></mesh>
      </group>
    );
  }
  if (type === 'toilet') {
    return (
      <group>
        <mesh position={[0, sy * 0.34, sz * 0.08]} scale={[sx * 0.5, sy * 0.34, sz * 0.52]}><sphereGeometry args={[1, 36, 24]} /><Surface profile="porcelain" color="#F4F4F0" /></mesh>
        <mesh position={[0, sy * 0.49, sz * 0.08]} rotation={[-Math.PI / 2, 0, 0]}><torusGeometry args={[Math.min(sx, sz) * 0.31, 0.035, 12, 36]} /><Surface profile="porcelain" color="#F8F8F4" /></mesh>
        <SoftPart position={[0, sy * 0.7, -sz * 0.3]} size={[sx * 0.72, sy * 0.5, sz * 0.34]} style={porcelain} radius={0.055} />
        <mesh position={[0, sy * 0.88, -sz * 0.48]}><cylinderGeometry args={[0.026, 0.026, 0.018, 16]} /><Metal /></mesh>
      </group>
    );
  }
  return (
    <group>
      <mesh position={[0, sy * 0.75, 0]} scale={[sx * 0.5, sy * 0.18, sz * 0.5]}><sphereGeometry args={[1, 32, 18]} /><Surface profile="porcelain" color="#F2F2EE" /></mesh>
      <mesh position={[0, sy * 0.39, 0]}><cylinderGeometry args={[sx * 0.18, sx * 0.25, sy * 0.64, 28]} /><Surface profile="porcelain" color="#F2F2EE" /></mesh>
      <mesh position={[0, sy * 1.02, -sz * 0.18]}><torusGeometry args={[0.1, 0.018, 12, 28, Math.PI]} /><Metal /></mesh>
    </group>
  );
}

function KitchenIsland({ size: [sx, sy, sz], style, textureUrl }: { size: [number, number, number]; style: FurnitureStyle; textureUrl?: string }) {
  return (
    <group>
      <SoftPart position={[0, sy * 0.47, 0]} size={[sx * 0.88, sy * 0.86, sz * 0.84]} style={{ ...style, material: 'oak', color: shade(style.color, 18) }} textureUrl={textureUrl} radius={0.025} />
      <SoftPart position={[0, sy * 0.96, 0]} size={[sx, sy * 0.12, sz]} style={{ ...style, material: 'stone', color: '#D7D0C4' }} radius={0.025} />
      {[-0.28, 0, 0.28].map((x) => <mesh key={x} position={[x * sx, sy * 0.5, sz * 0.43]}><boxGeometry args={[0.012, sy * 0.62, 0.018]} /><Metal color="#657068" /></mesh>)}
    </group>
  );
}

function Staircase({ size: [sx, sy, sz], style, textureUrl }: { size: [number, number, number]; style: FurnitureStyle; textureUrl?: string }) {
  const steps = 11;
  return (
    <group>
      {Array.from({ length: steps }, (_, index) => {
        const depth = sz / steps;
        const height = sy / steps;
        return <SoftPart key={index} position={[0, height * (index + 0.5), -sz / 2 + depth * (index + 0.5)]} size={[sx, height, depth]} style={{ ...style, material: 'oak' }} textureUrl={textureUrl} radius={0.015} />;
      })}
      <mesh position={[sx * 0.48, sy * 0.62, 0]} rotation={[Math.atan2(sy, sz), 0, 0]}><cylinderGeometry args={[0.025, 0.025, Math.hypot(sy, sz), 12]} /><Metal color="#33383A" /></mesh>
    </group>
  );
}

function GenericDetailed({ size: [sx, sy, sz], style, textureUrl }: { size: [number, number, number]; style: FurnitureStyle; textureUrl?: string }) {
  return (
    <group>
      <SoftPart position={[0, sy * 0.45, 0]} size={[sx * 0.9, sy * 0.72, sz * 0.86]} style={style} textureUrl={textureUrl} radius={0.06} />
      <SoftPart position={[0, sy * 0.88, 0]} size={[sx, sy * 0.16, sz]} style={{ ...style, color: shade(style.color, 16) }} textureUrl={textureUrl} radius={0.04} />
      {[-1, 1].flatMap((xSign) => [-1, 1].map((zSign) => <mesh key={`${xSign}-${zSign}`} position={[xSign * sx * 0.36, sy * 0.08, zSign * sz * 0.34]}><cylinderGeometry args={[0.03, 0.04, sy * 0.16, 12]} /><Metal /></mesh>))}
    </group>
  );
}

export function FurnitureModel({
  id, objectType, position, size, rotationDeg = 0, style = DEFAULT_STYLE, textureUrl, selected = false, visible = true, onSelect,
}: FurnitureModelProps) {
  const normalised = objectType.toLowerCase().replaceAll(' ', '_');
  const rotation = THREE.MathUtils.degToRad(rotationDeg);
  if (!visible) return null;
  let model: React.ReactNode;
  if (normalised === 'sofa' || normalised === 'couch' || normalised === 'sectional_sofa') model = <Sofa size={size} style={style} textureUrl={textureUrl} />;
  else if (normalised === 'armchair' || normalised === 'chair') model = <Armchair size={size} style={style} textureUrl={textureUrl} />;
  else if (normalised === 'bed') model = <Bed size={size} style={style} textureUrl={textureUrl} />;
  else if (normalised === 'coffee_table') model = <Table size={size} style={style} textureUrl={textureUrl} />;
  else if (normalised === 'dining_table') model = <Table size={size} style={style} textureUrl={textureUrl} dining />;
  else if (normalised === 'tv_unit') model = <Storage size={size} style={style} textureUrl={textureUrl} />;
  else if (normalised === 'wardrobe' || normalised === 'cabinetry' || normalised === 'vanity') model = <Storage size={size} style={style} textureUrl={textureUrl} wardrobe={normalised === 'wardrobe'} />;
  else if (['fridge', 'stove', 'washing_machine', 'dryer'].includes(normalised)) model = <Appliance type={normalised} size={size} style={style} textureUrl={textureUrl} />;
  else if (['toilet', 'sink', 'bathtub'].includes(normalised)) model = <BathroomFixture type={normalised} size={size} style={style} />;
  else if (normalised === 'kitchen_island' || normalised === 'countertop') model = <KitchenIsland size={size} style={style} textureUrl={textureUrl} />;
  else if (normalised === 'staircase') model = <Staircase size={size} style={style} textureUrl={textureUrl} />;
  else if (normalised === 'light_fixture') model = (
    <group>
      <mesh position={[0, size[1] * 0.45, 0]}><sphereGeometry args={[Math.min(size[0], size[2]) * 0.42, 32, 20]} /><meshPhysicalMaterial color={style.color} roughness={0.18} transmission={0.32} transparent opacity={0.78} /></mesh>
      <mesh position={[0, size[1] * 0.85, 0]}><cylinderGeometry args={[0.025, 0.025, size[1] * 0.45, 12]} /><Metal /></mesh>
      <pointLight position={[0, size[1] * 0.42, 0]} intensity={0.35} distance={4} color={style.color} />
    </group>
  );
  else model = <GenericDetailed size={size} style={style} textureUrl={textureUrl} />;

  return (
    <group
      name={`furniture-${id}`}
      position={[position[0], 0, position[2]]}
      rotation={[0, rotation, 0]}
      onClick={(event) => { event.stopPropagation(); onSelect?.(); }}
    >
      {model}
      {selected ? (
        <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[Math.max(size[0], size[2]) * 0.56, Math.max(size[0], size[2]) * 0.61, 48]} />
          <meshBasicMaterial color="#FFD36A" transparent opacity={0.85} side={THREE.DoubleSide} />
        </mesh>
      ) : null}
    </group>
  );
}
