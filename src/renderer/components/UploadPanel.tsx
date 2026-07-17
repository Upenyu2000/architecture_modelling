import {
  type ChangeEvent, type DragEvent, useEffect, useMemo, useRef, useState,
} from 'react';
import {
  AlertCircle, CheckCircle2, FileImage, Layers3, RefreshCcw, Upload, UserRound,
} from 'lucide-react';
import type { AssetCategory, Project } from '../types';

const FLOORPLAN_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'pdf']);
const MAX_UPLOAD_BYTES = 250 * 1024 * 1024;

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

function fileExtension(file: File): string {
  return file.name.split('.').pop()?.toLowerCase() ?? '';
}

function validateCommonFile(file: File): string | null {
  if (!file.size) return 'The selected file is empty.';
  if (file.size > MAX_UPLOAD_BYTES) return 'The selected file is larger than 250 MB.';
  return null;
}

export function UploadPanel({ project, busy, onFloorplan, onAsset }: Props) {
  const [activeTab, setActiveTab] = useState<AssetCategory>('flooring');
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadingName, setUploadingName] = useState('');
  const [uploadError, setUploadError] = useState('');
  const progressTimer = useRef<number | null>(null);
  const uploadInFlight = useRef(false);
  const mountedRef = useRef(true);
  const tab = assetTabs[activeTab];
  const uploadedKeys = useMemo(() => new Set(Object.keys(project?.assets ?? {})), [project]);
  const uploadBlocked = busy || uploadInFlight.current || Boolean(uploadingName);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (progressTimer.current) window.clearInterval(progressTimer.current);
    };
  }, []);

  useEffect(() => {
    if (busy) setIsDragging(false);
  }, [busy]);

  const stopProgress = () => {
    if (progressTimer.current) window.clearInterval(progressTimer.current);
    progressTimer.current = null;
  };

  const processFile = async (handler: (file: File) => Promise<void>, file: File) => {
    if (busy || uploadInFlight.current) return;
    const validationError = validateCommonFile(file);
    if (validationError) {
      setUploadError(validationError);
      return;
    }

    uploadInFlight.current = true;
    stopProgress();
    setUploadError('');
    setUploadingName(file.name);
    setUploadProgress(6);
    progressTimer.current = window.setInterval(() => {
      if (!mountedRef.current) return;
      setUploadProgress((current) => Math.min(92, current + Math.max(1, Math.round((92 - current) * 0.12))));
    }, 180);

    try {
      await handler(file);
      if (mountedRef.current) {
        setUploadProgress(100);
        await new Promise((resolve) => window.setTimeout(resolve, 260));
      }
    } catch (uploadFailure) {
      if (mountedRef.current) {
        setUploadError(uploadFailure instanceof Error ? uploadFailure.message : String(uploadFailure));
      }
    } finally {
      uploadInFlight.current = false;
      stopProgress();
      if (mountedRef.current) {
        setUploadingName('');
        setUploadProgress(0);
      }
    }
  };

  const handleFile = (handler: (file: File) => Promise<void>) => async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) await processFile(handler, file);
  };

  const floorplanDrop = async (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (uploadBlocked) return;
    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length !== 1) {
      setUploadError('Drop one floor-plan file at a time.');
      return;
    }
    const file = files[0];
    if (!FLOORPLAN_EXTENSIONS.has(fileExtension(file))) {
      setUploadError('Floor plans must be PNG, JPG, JPEG or PDF files.');
      return;
    }
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
        className={`dropzone ${project?.floorplan ? 'complete' : ''} ${isDragging ? 'is-dragging' : ''} ${uploadBlocked ? 'is-disabled' : ''}`}
        onDragEnter={(event) => { event.preventDefault(); if (!uploadBlocked) setIsDragging(true); }}
        onDragOver={(event) => { event.preventDefault(); if (!uploadBlocked) setIsDragging(true); }}
        onDragLeave={(event) => {
          event.preventDefault();
          const nextTarget = event.relatedTarget;
          if (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) setIsDragging(false);
        }}
        onDrop={(event) => void floorplanDrop(event)}
      >
        {uploadingName ? <RefreshCcw className="spin" size={28} /> : project?.floorplan ? <CheckCircle2 size={28} /> : <FileImage size={28} />}
        <strong>{uploadingName || project?.floorplan?.filename || (isDragging ? 'Drop floor plan here' : 'Upload floor plan')}</strong>
        <span>Drag and drop or click · PNG, JPG or first page of a PDF blueprint</span>
        {uploadingName ? <div className="upload-progress-shell" aria-label={`Uploading ${uploadProgress}%`}><i style={{ width: `${uploadProgress}%` }} /></div> : null}
        <input disabled={uploadBlocked} type="file" accept="image/png,image/jpeg,application/pdf,.png,.jpg,.jpeg,.pdf" onChange={handleFile(onFloorplan)} />
      </label>

      {uploadError ? <div className="upload-inline-error" role="alert"><AlertCircle size={16} /> {uploadError}</div> : null}

      <div className="tabs" role="tablist" aria-label="Asset categories">
        {(Object.keys(assetTabs) as AssetCategory[]).map((category) => (
          <button
            type="button"
            key={category}
            role="tab"
            aria-selected={activeTab === category}
            disabled={uploadBlocked}
            className={activeTab === category ? 'active' : ''}
            onClick={() => setActiveTab(category)}
          >
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
            <label className={`asset-card ${uploadedKeys.has(key) ? 'complete' : ''} ${uploadBlocked ? 'is-disabled' : ''}`} key={slot}>
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
                disabled={uploadBlocked}
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
