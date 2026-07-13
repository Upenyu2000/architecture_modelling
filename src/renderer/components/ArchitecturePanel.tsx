import { useEffect, useState } from 'react';
import { Boxes, BrainCircuit, Database, Download, Palette, RefreshCw, ShieldCheck } from 'lucide-react';
import { api } from '../lib/api';
import type { MaterialUpdate, Project, SceneManifest } from '../types';

interface Props {
  project: Project | null;
  busy: boolean;
  onCompile: (useVisionAi: boolean) => Promise<void>;
  onApply: (settings: MaterialUpdate) => Promise<void>;
}

const presets: Record<string, Omit<MaterialUpdate, 'cutaway_height_m'>> = {
  'Light Oak / Modern Tech': {
    palette_name: 'Light Oak / Modern Tech',
    floor_type: 'hardwood',
    floor_color: '#B99268',
    wall_color: '#E8E5DE',
    exterior_color: '#9C9C96',
    accent_color: '#2E79C6',
    roughness: 0.46,
  },
  'Warm Walnut / Blue Accents': {
    palette_name: 'Warm Walnut / Blue Accents',
    floor_type: 'hardwood',
    floor_color: '#74513B',
    wall_color: '#EEE8DD',
    exterior_color: '#81756D',
    accent_color: '#1F4772',
    roughness: 0.42,
  },
  'Minimal White / Black Metal': {
    palette_name: 'Minimal White / Black Metal',
    floor_type: 'hardwood',
    floor_color: '#C7B9A4',
    wall_color: '#F3F3F0',
    exterior_color: '#555A5D',
    accent_color: '#171A1C',
    roughness: 0.48,
  },
  'Natural Stone / Sage': {
    palette_name: 'Natural Stone / Sage',
    floor_type: 'stone',
    floor_color: '#BEB09B',
    wall_color: '#E7E1D5',
    exterior_color: '#A9A08E',
    accent_color: '#6F8068',
    roughness: 0.62,
  },
};

function fromScene(scene?: SceneManifest | null): MaterialUpdate {
  const materials = scene?.materials;
  return {
    palette_name: materials?.palette_name ?? 'Light Oak / Modern Tech',
    floor_type: materials?.floor_global.material_type ?? 'hardwood',
    floor_color: materials?.floor_global.hex_color ?? '#B99268',
    wall_color: materials?.walls_global.hex_color ?? '#E8E5DE',
    exterior_color: materials?.exterior_walls.hex_color ?? '#9C9C96',
    accent_color: materials?.accent.hex_color ?? '#2E79C6',
    roughness: materials?.floor_global.roughness ?? 0.46,
    cutaway_height_m: scene?.cutaway_height_m ?? 1.65,
  };
}

export function ArchitecturePanel({ project, busy, onCompile, onApply }: Props) {
  const scene = project?.scene;
  const [settings, setSettings] = useState<MaterialUpdate>(() => fromScene(scene));
  const [useVision, setUseVision] = useState(false);
  const [trainingMessage, setTrainingMessage] = useState('');
  const [trainingBusy, setTrainingBusy] = useState(false);

  useEffect(() => setSettings(fromScene(scene)), [scene?.project_id, scene?.materials.palette_name, scene?.cutaway_height_m]);

  const update = <K extends keyof MaterialUpdate>(key: K, value: MaterialUpdate[K]) => {
    setSettings((current) => ({ ...current, [key]: value }));
  };

  const choosePreset = (name: string) => {
    const preset = presets[name];
    setSettings((current) => ({ ...preset, cutaway_height_m: current.cutaway_height_m }));
  };

  const addTrainingExample = async () => {
    if (!project || !scene) return;
    const confirmed = window.confirm(
      'Add this floor plan and your corrected free-form room geometry to the local training workspace? Continue only if you own the plan or are authorised to use it for model training.',
    );
    if (!confirmed) return;
    setTrainingBusy(true);
    setTrainingMessage('');
    try {
      const exported = await api.exportTrainingExample(project.id);
      setTrainingMessage(`Added to ${exported.split}: ${exported.workspace}`);
    } catch (error) {
      setTrainingMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setTrainingBusy(false);
    }
  };

  const metadata = scene?.project_metadata;

  return (
    <section className="panel architecture-panel">
      <div className="panel-heading">
        <div><span className="eyebrow">3. Production compile</span><h2>Architectural dataset and materials</h2></div>
        <BrainCircuit size={22} />
      </div>
      <p className="panel-copy">
        Compile free-form room polygons, walls, dimensions, openings, procedural fixtures, collision geometry and synchronized camera data into one exportable scene.
      </p>

      {metadata ? (
        <div className="compile-metrics">
          <span><strong>{metadata.detected_rooms}</strong> rooms</span>
          <span><strong>{metadata.detected_openings}</strong> openings</span>
          <span><strong>{metadata.detected_objects}</strong> objects</span>
          <span><strong>{Math.round(metadata.structural_confidence * 100)}%</strong> structural confidence</span>
        </div>
      ) : null}

      <label className="checkbox-row vision-consent">
        <input type="checkbox" checked={useVision} onChange={(event) => setUseVision(event.target.checked)} />
        Use the configured private vision endpoint to refine labels and symbols. Images are never uploaded unless remote processing is enabled in Settings.
      </label>

      <button className="primary" disabled={busy || !scene} onClick={() => void onCompile(useVision)}>
        <RefreshCw size={17} /> Compile production scene
      </button>

      <div className="architecture-divider" />
      <div className="palette-heading"><Palette size={17} /><strong>Real-world material mapper</strong></div>
      <div className="two-inputs material-grid">
        <label>Design palette
          <select value={settings.palette_name} onChange={(event) => choosePreset(event.target.value)}>
            {Object.keys(presets).map((name) => <option value={name} key={name}>{name}</option>)}
          </select>
        </label>
        <label>Floor material
          <select value={settings.floor_type} onChange={(event) => update('floor_type', event.target.value)}>
            <option value="hardwood">Hardwood</option>
            <option value="tile">Porcelain tile</option>
            <option value="carpet">Carpet</option>
            <option value="stone">Natural stone</option>
            <option value="polished_concrete">Polished concrete</option>
          </select>
        </label>
        <label>Floor colour<input type="color" value={settings.floor_color} onChange={(event) => update('floor_color', event.target.value)} /></label>
        <label>Wall colour<input type="color" value={settings.wall_color} onChange={(event) => update('wall_color', event.target.value)} /></label>
        <label>Exterior colour<input type="color" value={settings.exterior_color} onChange={(event) => update('exterior_color', event.target.value)} /></label>
        <label>Accent colour<input type="color" value={settings.accent_color} onChange={(event) => update('accent_color', event.target.value)} /></label>
        <label>Material roughness
          <div className="range-row"><input type="range" min="0" max="1" step="0.01" value={settings.roughness} onChange={(event) => update('roughness', Number(event.target.value))} /><span>{Math.round(settings.roughness * 100)}</span></div>
        </label>
        <label>Cutaway wall height
          <div className="unit-input"><input type="number" min="0.6" max="3.5" step="0.05" value={settings.cutaway_height_m} onChange={(event) => update('cutaway_height_m', Number(event.target.value))} /><span>m</span></div>
        </label>
      </div>
      <button className="secondary full-width" disabled={busy || !scene} onClick={() => void onApply(settings)}>
        <Boxes size={17} /> Apply palette and cutaway
      </button>

      {scene ? (
        <div className="training-export-card">
          <div><Database size={18} /><span><strong>Continuous learning</strong><small>After correcting every room vertex, export this plan as a supervised local training example.</small></span></div>
          <button className="secondary" disabled={busy || trainingBusy || !project?.floorplan || scene.rooms.length === 0} onClick={() => void addTrainingExample()}>
            <Database size={15} /> {trainingBusy ? 'Exporting…' : 'Add corrected plan to training set'}
          </button>
          {trainingMessage ? <small className="training-export-message">{trainingMessage}</small> : null}
        </div>
      ) : null}

      {scene ? (
        <div className="architecture-actions">
          <a className="download-json" href={api.architectureJsonUrl(project!.id)} target="_blank" rel="noreferrer"><Download size={15} /> Export architecture JSON</a>
          <span><ShieldCheck size={14} /> {metadata?.ocr_status ?? 'Deterministic parser ready'}</span>
        </div>
      ) : null}
    </section>
  );
}
