import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle, Boxes, CheckCircle2, Download, ExternalLink, FileUp, FolderCog,
  History, Layers3, Redo2, Ruler, Table2, Undo2, Wrench,
} from 'lucide-react';
import { absoluteUrl, api } from '../lib/api';
import type { Job, Project } from '../types';

type FreeCADStatus = {
  installed: boolean;
  command_path?: string | null;
  gui_path?: string | null;
  gui_available?: boolean;
  version?: string | null;
  modules?: Record<string, boolean>;
  export_formats?: string[];
  error?: string | null;
};

type Parameters = {
  wall_height_m: number;
  default_wall_thickness_m: number;
  ceiling_height_m: number;
  cutaway_height_m: number;
  unit_system: 'metric' | 'imperial';
};

type QuantityPayload = {
  summary?: Record<string, number>;
  room_types?: Record<string, number>;
  furniture?: Record<string, number>;
};

type TreeNode = {
  id: string;
  label: string;
  type?: string;
  properties?: Record<string, unknown>;
  children?: TreeNode[];
};

type HistoryPayload = {
  cursor: number;
  entries: { id: string; label: string; created_at: string }[];
  can_undo: boolean;
  can_redo: boolean;
};

interface Props {
  project: Project | null;
  disabled: boolean;
  onProjectChange: (project: Project) => void;
}

const DEFAULT_PARAMETERS: Parameters = {
  wall_height_m: 2.8,
  default_wall_thickness_m: 0.16,
  ceiling_height_m: 2.8,
  cutaway_height_m: 1.65,
  unit_system: 'metric',
};

const FORMAT_LABELS: Record<string, string> = {
  fcstd: 'FCStd',
  step: 'STEP',
  iges: 'IGES',
  brep: 'BRep',
  ifc: 'IFC',
  dxf: 'DXF',
  svg: 'SVG',
  stl: 'STL',
  obj: 'OBJ',
};

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

function formatMetric(key: string, value: number): string {
  if (key.endsWith('_m2')) return `${value.toLocaleString()} m²`;
  if (key.endsWith('_m3')) return `${value.toLocaleString()} m³`;
  if (key.endsWith('_m')) return `${value.toLocaleString()} m`;
  return value.toLocaleString();
}

function TreeBranch({ node, depth = 0 }: { node: TreeNode; depth?: number }) {
  const children = node.children ?? [];
  return (
    <details className="fc-tree-node" open={depth < 1}>
      <summary>
        <span className="fc-tree-indent" style={{ width: `${depth * 12}px` }} />
        <Layers3 size={14} />
        <strong>{node.label}</strong>
        <small>{node.type}</small>
      </summary>
      {node.properties && (
        <div className="fc-tree-properties">
          {Object.entries(node.properties).slice(0, 8).map(([key, value]) => (
            <span key={key}><b>{key.replaceAll('_', ' ')}</b>{String(value ?? '—')}</span>
          ))}
        </div>
      )}
      {children.map((child) => <TreeBranch node={child} depth={depth + 1} key={child.id} />)}
    </details>
  );
}

export function FreeCADWorkbench({ project, disabled, onProjectChange }: Props) {
  const [status, setStatus] = useState<FreeCADStatus | null>(null);
  const [parameters, setParameters] = useState<Parameters>(DEFAULT_PARAMETERS);
  const [quantities, setQuantities] = useState<QuantityPayload | null>(null);
  const [tree, setTree] = useState<TreeNode | null>(null);
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [format, setFormat] = useState('fcstd');
  const [includeFurniture, setIncludeFurniture] = useState(true);
  const [working, setWorking] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const refreshProjectData = async () => {
    if (!project?.id || !project.scene) return;
    const [nextParameters, nextQuantities, nextTree, nextHistory] = await Promise.all([
      api.freecadParameters(project.id),
      api.freecadQuantities(project.id),
      api.freecadModelTree(project.id),
      api.freecadHistory(project.id),
    ]);
    setParameters(nextParameters as Parameters);
    setQuantities(nextQuantities as QuantityPayload);
    setTree(nextTree as TreeNode);
    setHistory(nextHistory as HistoryPayload);
  };

  useEffect(() => {
    let mounted = true;
    void api.freecadStatus().then((next) => {
      if (mounted) setStatus(next as FreeCADStatus);
    }).catch((reason) => {
      if (mounted) setStatus({ installed: false, error: reason instanceof Error ? reason.message : String(reason) });
    });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    void refreshProjectData().catch(() => undefined);
  }, [project?.id, project?.scene]);

  const supportedFormats = useMemo(
    () => status?.export_formats?.length ? status.export_formats : ['fcstd', 'step', 'iges', 'brep', 'stl', 'obj'],
    [status],
  );

  useEffect(() => {
    if (!supportedFormats.includes(format)) setFormat(supportedFormats[0] ?? 'fcstd');
  }, [format, supportedFormats]);

  const pollJob = async (created: Job): Promise<Job> => {
    setJob(created);
    let latest = created;
    for (let attempt = 0; attempt < 3600; attempt += 1) {
      if (latest.status === 'completed' || latest.status === 'failed') return latest;
      await wait(1000);
      latest = await api.getJob(created.id);
      setJob(latest);
    }
    throw new Error('The FreeCAD operation exceeded the one-hour polling limit.');
  };

  const run = async (operation: () => Promise<void>) => {
    setWorking(true);
    setError('');
    setNotice('');
    try {
      await operation();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setWorking(false);
    }
  };

  const saveParameters = () => run(async () => {
    if (!project) return;
    const updated = await api.updateFreecadParameters(project.id, parameters);
    onProjectChange(updated);
    setNotice('Parametric wall, ceiling and cutaway properties recomputed across the complete model.');
    await refreshProjectData();
  });

  const restoreHistory = (direction: 'undo' | 'redo') => run(async () => {
    if (!project) return;
    const updated = direction === 'undo'
      ? await api.freecadUndo(project.id)
      : await api.freecadRedo(project.id);
    onProjectChange(updated);
    setNotice(direction === 'undo' ? 'Restored the previous parametric model state.' : 'Reapplied the next parametric model state.');
    await refreshProjectData();
  });

  const exportModel = () => run(async () => {
    if (!project) return;
    const completed = await pollJob(await api.freecadExport(project.id, format, includeFurniture, parameters.unit_system));
    if (completed.status === 'failed') throw new Error(completed.error || completed.message);
    setNotice(`${FORMAT_LABELS[format] ?? format.toUpperCase()} export completed with an editable model tree and quantity schedule.`);
  });

  const openModel = () => run(async () => {
    if (!project) return;
    const completed = await pollJob(await api.freecadOpen(project.id));
    if (completed.status === 'failed') throw new Error(completed.error || completed.message);
    setNotice('The editable FCStd building model has been opened in FreeCAD.');
  });

  const importModel = (event: ChangeEvent<HTMLInputElement>) => run(async () => {
    if (!project) return;
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    const completed = await pollJob(await api.freecadImport(project.id, file));
    if (completed.status === 'failed') throw new Error(completed.error || completed.message);
    const updated = await api.getProject(project.id);
    onProjectChange(updated);
    setNotice('CAD/BIM source imported through FreeCAD and converted to an editable FCStd document plus an app-compatible OBJ model.');
  });

  const unavailable = !status?.installed;
  const summary = quantities?.summary ?? {};

  return (
    <section className="panel freecad-workbench">
      <div className="panel-heading">
        <div><span className="eyebrow">CAD & BIM workbench</span><h2>FreeCAD parametric model</h2></div>
        <Boxes size={23} />
      </div>
      <p className="panel-copy">
        Use FreeCAD’s Open CASCADE solid kernel for precise BRep and NURBS-capable building models, editable properties,
        model history, quantity schedules and engineering file exchange while the Roomify workspace remains the visual design layer.
      </p>

      <div className={`freecad-status ${unavailable ? 'offline' : 'online'}`}>
        {unavailable ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
        <div>
          <strong>{unavailable ? 'FreeCAD is not connected' : `FreeCAD ${status?.version || '1.x'} connected`}</strong>
          <span>{unavailable ? 'Install FreeCAD or select FreeCADCmd.exe in Settings.' : status?.command_path}</span>
          {status?.error && <small>{status.error}</small>}
        </div>
      </div>

      <div className="freecad-feature-grid">
        <article><Wrench size={16} /><strong>Parametric</strong><span>Recomputable dimensions and object properties</span></article>
        <article><FolderCog size={16} /><strong>BRep & NURBS</strong><span>Open CASCADE solids, surfaces and Boolean opening cuts</span></article>
        <article><Table2 size={16} /><strong>BOM</strong><span>Room, wall, opening and fixture quantities</span></article>
        <article><Ruler size={16} /><strong>Real units</strong><span>Metric or imperial document metadata</span></article>
      </div>

      {project?.scene ? (
        <>
          <div className="freecad-subhead"><span>Parametric properties</span><History size={16} /></div>
          <div className="freecad-parameter-grid">
            <label>Wall height<input type="number" min="1.8" max="20" step="0.05" value={parameters.wall_height_m} onChange={(event) => setParameters((current) => ({ ...current, wall_height_m: Number(event.target.value) }))} /><span>m</span></label>
            <label>Wall thickness<input type="number" min="0.04" max="1.5" step="0.01" value={parameters.default_wall_thickness_m} onChange={(event) => setParameters((current) => ({ ...current, default_wall_thickness_m: Number(event.target.value) }))} /><span>m</span></label>
            <label>Ceiling height<input type="number" min="1.8" max="20" step="0.05" value={parameters.ceiling_height_m} onChange={(event) => setParameters((current) => ({ ...current, ceiling_height_m: Number(event.target.value) }))} /><span>m</span></label>
            <label>Cutaway height<input type="number" min="0.4" max="10" step="0.05" value={parameters.cutaway_height_m} onChange={(event) => setParameters((current) => ({ ...current, cutaway_height_m: Number(event.target.value) }))} /><span>m</span></label>
            <label>Document units<select value={parameters.unit_system} onChange={(event) => setParameters((current) => ({ ...current, unit_system: event.target.value as Parameters['unit_system'] }))}><option value="metric">Metric</option><option value="imperial">Imperial metadata</option></select></label>
          </div>
          <div className="freecad-history-actions">
            <button className="secondary" disabled={disabled || working || !history?.can_undo} onClick={() => void restoreHistory('undo')}><Undo2 size={16} /> Undo</button>
            <button className="secondary" disabled={disabled || working || !history?.can_redo} onClick={() => void restoreHistory('redo')}><Redo2 size={16} /> Redo</button>
            <button className="primary" disabled={disabled || working} onClick={saveParameters}><Wrench size={16} /> Recompute model</button>
          </div>

          <div className="freecad-subhead"><span>Quantity schedule</span><Table2 size={16} /></div>
          <div className="freecad-quantity-grid">
            {Object.entries(summary).slice(0, 12).map(([key, value]) => (
              <article key={key}><strong>{formatMetric(key, value)}</strong><span>{key.replaceAll('_', ' ')}</span></article>
            ))}
          </div>

          {tree && (
            <details className="freecad-model-tree">
              <summary><Layers3 size={16} /> Parametric model tree</summary>
              <TreeBranch node={tree} />
            </details>
          )}

          <div className="freecad-subhead"><span>Import and export</span><Download size={16} /></div>
          <div className="freecad-export-row">
            <select value={format} onChange={(event) => setFormat(event.target.value)}>
              {supportedFormats.map((item) => <option value={item} key={item}>{FORMAT_LABELS[item] ?? item.toUpperCase()}</option>)}
            </select>
            <label className="freecad-checkbox"><input type="checkbox" checked={includeFurniture} onChange={(event) => setIncludeFurniture(event.target.checked)} /> Include furniture</label>
            <button className="primary" disabled={disabled || working || unavailable} onClick={exportModel}><Download size={16} /> Export model</button>
            <button className="secondary" disabled={disabled || working || unavailable || !status?.gui_available} onClick={openModel}><ExternalLink size={16} /> Open in FreeCAD</button>
          </div>
          <label className={`freecad-import ${unavailable ? 'disabled' : ''}`}>
            <FileUp size={20} />
            <span><strong>Import CAD or BIM model</strong><small>FCStd, STEP, IGES, BRep, IFC, DXF, SVG, STL, OBJ, DAE, OFF or 3MF</small></span>
            <input disabled={disabled || working || unavailable} type="file" accept=".FCStd,.fcstd,.step,.stp,.iges,.igs,.brep,.brp,.ifc,.dxf,.svg,.stl,.obj,.dae,.off,.3mf" onChange={importModel} />
          </label>
        </>
      ) : (
        <div className="freecad-empty">Compile or draw the architectural scene before creating a parametric CAD/BIM document.</div>
      )}

      {job && (
        <div className={`freecad-job ${job.status}`}>
          <div><strong>{job.kind.replaceAll('_', ' ')}</strong><span>{job.message}</span></div>
          <div className="progress"><i style={{ width: `${job.progress}%` }} /></div>
          <b>{job.progress}%</b>
          {job.output_url && job.status === 'completed' && <a href={absoluteUrl(job.output_url)} target="_blank" rel="noreferrer"><Download size={14} /> Download</a>}
        </div>
      )}
      {notice && <div className="freecad-notice">{notice}</div>}
      {error && <div className="freecad-error">{error}</div>}
    </section>
  );
}
