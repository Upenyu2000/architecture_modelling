import {
  type ChangeEvent, type DragEvent, useEffect, useMemo, useRef, useState,
} from 'react';
import { CheckCircle2, FileImage, Layers3, RefreshCcw, Upload, UserRound } from 'lucide-react';
import type { AssetCategory, Project } from '../types';

const assetTabs: Record<AssetCategory, { title: string; slots: string[] }> = {
  flooring: { title: 'Flooring', slots: ['main_floor', 'secondary_floor'] },
  walls: { title: 'Walls', slots: ['paint_or_wallpaper', 'feature_wall'] },
  kitchen: { title: 'Kitchen', slots: ['fridge', 'cabinetry', 'countertop', 'stove', 'kitchen_island'] },
  living_room: { title: 'Living', slots: ['couch', 'sectional_sofa', 'armchair', 'tv_unit', 'coffee_table', 'light_fixture'] },
  bathroom: { title: 'Bathroom', slots: ['sink', 'toilet', 'bathtub', 'tiles', 'vanity'] },
  bedroom: { title: 'Bedroom', slots: ['bed', 'wardrobe', 'nightstand', 'dresser', 'lamp'] },
  dining_room: { title: 'Dining', slots: ['dining_table', 'dining_chair', 'sideboard', 'pendant_light'] },
  office: { title: 'Office', slots: ['desk', 'office_chair', 'shelving', 'lamp'] },
  outdoor: { title: 'Outdoor', slots: ['patio_sofa', 'outdoor_table', 'outdoor_chair', 'planter'] },
  characters: { title: 'Characters', slots: ['walkthrough_avatar'] },
};

interface Props {
  project: Project | null;
  busy: boolean;
  onFloorplan: (file: File) => Promise<void>;
  onAsset: (category: AssetCategory, slot: string, file: File) => Promise<void>;
}

export function UploadPanel({ project, busy, onFloorplan, onAsset }: Props) {
  const [activeTab, setActiveTab] = useState<AssetCategory>('flooring');
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadingName, setUploadingName] = useState('');
  const progressTimer = useRef<number | null>(null);
  const tab = assetTabs[activeTab];
  const uploadedKeys = useMemo(() => new Set(Object.keys(project?.assets ?? {})), [project]);

  useEffect(() => () => {
    if (progressTimer.current) window.clearInterval(progressTimer.current);
  }, []);

  const processFile = async (handler: (file: File) => Promise<void>, file: File) => {
    if (busy) return;
    if (progressTimer.current) window.clearInterval(progressTimer.current);
    setUploadingName(file.name);
    setUploadProgress(6);
    progressTimer.current = window.setInterval(() => {
      setUploadProgress((current) => Math.min(92, current + 7));
    }, 110);
    try {
      await handler(file);
      setUploadProgress(100);
      await new Promise((resolve) => window.setTimeout(resolve, 350));
    } finally {
      if (progressTimer.current) window.clearInterval(progressTimer.current);
      progressTimer.current = null;
      setUploadingName('');
      setUploadProgress(0);
    }
  };

  const handleFile = (handler: (file: File) => Promise<void>) => async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) await processFile(handler, file);
    event.target.value = '';
  };

  const floorplanDrop = async (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (busy) return;
    const file = event.dataTransfer.files?.[0];
    if (!file) return;
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (!['png', 'jpg', 'jpeg', 'pdf'].includes(extension ?? '')) return;
    await processFile(onFloorplan, file);
  };

  const acceptedFiles = activeTab === 'characters'
    ? '.glb,.gltf,.obj,.stl,.ply,model/gltf-binary,model/gltf+json'
    : activeTab === 'flooring' || activeTab === 'walls'
      ? 'image/png,image/jpeg,image/webp'
      : 'image/png,image/jpeg,image/webp,.glb,.gltf,.obj,.stl,.ply';

  return (
    <section className="panel upload-panel">
      <div className="panel-heading">
        <div><span className="eyebrow">1. Inputs</span><h2>Plan, materials, interiors and characters</h2></div>
        <Layers3 size={22} />
      </div>

      <label
        className={`dropzone ${project?.floorplan ? 'complete' : ''} ${isDragging ? 'is-dragging' : ''}`}
        onDragEnter={(event) => { event.preventDefault(); if (!busy) setIsDragging(true); }}
        onDragOver={(event) => { event.preventDefault(); if (!busy) setIsDragging(true); }}
        onDragLeave={(event) => { event.preventDefault(); if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsDragging(false); }}
        onDrop={(event) => void floorplanDrop(event)}
      >
        {uploadingName ? <RefreshCcw className="spin" size={28} /> : project?.floorplan ? <CheckCircle2 size={28} /> : <FileImage size={28} />}
        <strong>{uploadingName || project?.floorplan?.filename || (isDragging ? 'Drop floor plan here' : 'Upload floor plan')}</strong>
        <span>Drag and drop or click · PNG, JPG or first page of a PDF blueprint</span>
        {uploadingName ? <div className="upload-progress-shell"><i style={{ width: `${uploadProgress}%` }} /></div> : null}
        <input disabled={busy} type="file" accept="image/png,image/jpeg,application/pdf" onChange={handleFile(onFloorplan)} />
      </label>

      <div className="tabs" role="tablist">
        {(Object.keys(assetTabs) as AssetCategory[]).map((category) => (
          <button key={category} className={activeTab === category ? 'active' : ''} onClick={() => setActiveTab(category)}>
            {assetTabs[category].title}
          </button>
        ))}
      </div>

      <div className="asset-grid">
        {tab.slots.map((slot) => {
          const key = `${activeTab}/${slot}`;
          const asset = project?.assets[key];
          const isCharacter = activeTab === 'characters';
          return (
            <label className={`asset-card ${uploadedKeys.has(key) ? 'complete' : ''}`} key={slot}>
              {isCharacter ? <UserRound size={18} /> : <Upload size={18} />}
              <strong>{slot.replaceAll('_', ' ')}</strong>
              <span>{asset?.filename ?? (
                isCharacter
                  ? 'Add a licensed GLB/GLTF/OBJ character model'
                  : activeTab === 'flooring' || activeTab === 'walls'
                    ? 'Add PBR texture image'
                    : 'Add furniture image or ready 3D model'
              )}</span>
              <input
                disabled={busy}
                type="file"
                accept={acceptedFiles}
                onChange={handleFile((file) => onAsset(activeTab, slot, file))}
              />
            </label>
          );
        })}
      </div>
      <small className="manual-note">
        Images can drive PBR surfaces or local image-to-3D reconstruction. Ready GLB/OBJ assets bypass reconstruction. Character realism depends on the licensed model supplied by the user; the app normalises and lights it locally.
      </small>
    </section>
  );
}
