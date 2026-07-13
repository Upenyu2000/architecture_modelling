import { ChangeEvent, useMemo, useState } from 'react';
import { FileImage, Layers3, Upload } from 'lucide-react';
import type { AssetCategory, Project } from '../types';

const assetTabs: Record<AssetCategory, { title: string; slots: string[] }> = {
  flooring: { title: 'Flooring', slots: ['main_floor', 'secondary_floor'] },
  walls: { title: 'Walls', slots: ['paint_or_wallpaper', 'feature_wall'] },
  kitchen: { title: 'Kitchen', slots: ['fridge', 'cabinetry', 'countertop', 'stove'] },
  living_room: { title: 'Living Room', slots: ['couch', 'tv_unit', 'coffee_table', 'light_fixture'] },
  bathroom: { title: 'Bathroom', slots: ['sink', 'bathtub', 'tiles', 'vanity'] },
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
        <div>
          <span className="eyebrow">1. Inputs</span>
          <h2>Plan and materials</h2>
        </div>
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
              <span>{asset?.filename ?? 'Add image or texture'}</span>
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
    </section>
  );
}
