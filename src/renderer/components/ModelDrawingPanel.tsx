import { ChangeEvent, useState } from 'react';
import { Box, FileDown, Ruler } from 'lucide-react';
import { absoluteUrl } from '../lib/api';
import type { ModelUnits, Project, UpAxis } from '../types';

interface Props {
  project: Project | null;
  busy: boolean;
  onUpload: (file: File) => Promise<void>;
  onGenerate: (sliceHeight: number, upAxis: UpAxis, units: ModelUnits) => Promise<void>;
}

export function ModelDrawingPanel({ project, busy, onUpload, onGenerate }: Props) {
  const [sliceHeight, setSliceHeight] = useState(1.2);
  const [upAxis, setUpAxis] = useState<UpAxis>('y');
  const [units, setUnits] = useState<ModelUnits>('auto');

  const handleModel = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) await onUpload(file);
    event.target.value = '';
  };

  return (
    <section className="panel model-drawing-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Reverse workflow</span>
          <h2>3D model to 2D drawings</h2>
        </div>
        <Ruler size={22} />
      </div>
      <p className="panel-copy">
        Upload a complete building model and cut a measured floor plan plus front and side elevations.
      </p>

      <label className={`model-dropzone ${project?.building_model ? 'complete' : ''}`}>
        <Box size={24} />
        <strong>{project?.building_model?.filename ?? 'Upload 3D building model'}</strong>
        <span>GLB, OBJ, STL or PLY</span>
        <input disabled={busy} type="file" accept=".glb,.obj,.stl,.ply" onChange={handleModel} />
      </label>

      <div className="drawing-options">
        <label>
          Model units
          <select value={units} onChange={(event) => setUnits(event.target.value as ModelUnits)}>
            <option value="auto">Auto detect</option>
            <option value="metres">Metres</option>
            <option value="millimetres">Millimetres</option>
            <option value="centimetres">Centimetres</option>
            <option value="feet">Feet</option>
          </select>
        </label>
        <label>
          Up axis
          <select value={upAxis} onChange={(event) => setUpAxis(event.target.value as UpAxis)}>
            <option value="y">Y-up (GLB/common)</option>
            <option value="z">Z-up (CAD/common)</option>
          </select>
        </label>
        <label>
          Floor-plan cut height
          <div className="unit-input"><input type="number" min="0.05" max="100" step="0.1" value={sliceHeight} onChange={(event) => setSliceHeight(Number(event.target.value))} /><span>m</span></div>
        </label>
      </div>

      <button
        className="primary"
        disabled={busy || !project?.building_model || !Number.isFinite(sliceHeight) || sliceHeight <= 0}
        onClick={() => onGenerate(sliceHeight, upAxis, units)}
      >
        <FileDown size={17} /> Generate drawing set
      </button>

      {project?.drawing_set ? (
        <div className="drawing-results">
          <div className="drawing-result-heading">
            <strong>Latest drawing set</strong>
            <span>{project.drawing_set.bounds_m.map((value) => `${value.toFixed(1)}m`).join(' × ')}</span>
          </div>
          {project.drawing_set.files.map((file) => (
            <div className="drawing-file" key={`${file.kind}-${file.filename}`}>
              <div><strong>{file.kind.replaceAll('_', ' ')}</strong><span>{file.format.toUpperCase()}</span></div>
              <div>
                <a href={absoluteUrl(file.url)} target="_blank" rel="noreferrer">Open</a>
                {window.desktop ? <button onClick={() => window.desktop?.openPath(file.path)}>Folder</button> : null}
              </div>
            </div>
          ))}
          {project.drawing_set.warnings.length ? <small className="drawing-warning">{project.drawing_set.warnings.join(' · ')}</small> : null}
        </div>
      ) : null}
    </section>
  );
}
