import { ChangeEvent, useMemo, useState } from 'react';
import { FileImage, Layers3, Upload } from 'lucide-react';
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
};

interface Props {
  project: Project | null;
  busy: boolean;
  onFloorplan: (file: File) => Promise<void>;
  onAsset: (category: AssetCategory, slot: string, file: File) => Promise<void>;
}

export function UploadPanel({ project, busy, onFloorplan, onAsset }: Props) {
  const [activeTab, setActiveTab] = useState<AssetCategory>('flooring');
  const tab = assetTabs[activeTab];
  const uploadedKeys = useMemo(() => new Set(Object.keys(project?.assets ?? {})), [project]);

  const handleFile = (handler: (file: File) => Promise<void>) => async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) await handler(file);
    event.target.value = '';
  };

  return (
    <section className="panel upload-panel">
      <div className="panel-heading">
        <div><span className="eyebrow">1. Inputs</span><h2>Plan, materials and interiors</h2></div>
        <Layers3 size={22} />
      </div>

      <label className={`dropzone ${project?.floorplan ? 'complete' : ''}`}>
        <FileImage size={28} />
        <strong>{project?.floorplan ? project.floorplan.filename : 'Upload floor plan'}</strong>
        <span>PNG, JPG or first page of a PDF blueprint</span>
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
          return (
            <label className={`asset-card ${uploadedKeys.has(key) ? 'complete' : ''}`} key={slot}>
              <Upload size={18} />
              <strong>{slot.replaceAll('_', ' ')}</strong>
              <span>{asset?.filename ?? (activeTab === 'flooring' || activeTab === 'walls' ? 'Add PBR texture image' : 'Add furniture reference image')}</span>
              <input
                disabled={busy}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={handleFile((file) => onAsset(activeTab, slot, file))}
              />
            </label>
          );
        })}
      </div>
      <small className="manual-note">Interior images can be mapped onto procedural furniture or passed to your configured local image-to-3D command for GLB reconstruction.</small>
    </section>
  );
}
