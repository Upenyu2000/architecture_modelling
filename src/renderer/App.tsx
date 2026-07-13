import { useEffect, useRef, useState } from 'react';
import {
  Box, Clock3, Film, FolderOpen, Image as ImageIcon, Play, RotateCcw,
  Save, ScanLine, Sparkles, Trash2,
} from 'lucide-react';
import { UploadPanel } from './components/UploadPanel';
import { ScenePreview } from './components/ScenePreview';
import { SettingsPanel } from './components/SettingsPanel';
import { absoluteUrl, api, initApi } from './lib/api';
import type { AssetCategory, Job, Project, SaveSlot } from './types';

function savedAt(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function App() {
  const [project, setProject] = useState<Project | null>(null);
  const [saveSlots, setSaveSlots] = useState<SaveSlot[]>([]);
  const [slotName, setSlotName] = useState('');
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [planWidth, setPlanWidth] = useState(14);
  const [wallHeight, setWallHeight] = useState(2.8);
  const [renderEngine, setRenderEngine] = useState<'auto' | 'technical' | 'blender'>('auto');
  const [job, setJob] = useState<Job | null>(null);
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        await initApi();
        const savedId = localStorage.getItem('dreamhome.currentProject');
        let selected: Project | null = null;
        if (savedId) {
          try { selected = await api.getProject(savedId); } catch { selected = null; }
        }
        if (!selected) {
          const existing = await api.listProjects();
          selected = existing[0] ?? await api.createProject('Dream Home Project');
        }
        localStorage.setItem('dreamhome.currentProject', selected.id);
        setProject(selected);
        setSaveSlots(await api.listSaveSlots(selected.id));
        if (selected.scene) {
          setPlanWidth(selected.scene.width_m);
          setWallHeight(selected.scene.wall_height_m);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    })();
    return () => { if (pollTimer.current) window.clearInterval(pollTimer.current); };
  }, []);

  const run = async (task: () => Promise<void>) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await task();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const refreshSaveSlots = async (projectId: string) => {
    setSaveSlots(await api.listSaveSlots(projectId));
  };

  const uploadFloorplan = (file: File) => run(async () => {
    setProject(await api.uploadFloorplan(project!.id, file));
  });

  const uploadAsset = (category: AssetCategory, slot: string, file: File) => run(async () => {
    setProject(await api.uploadAsset(project!.id, category, slot, file));
  });

  const analyze = () => run(async () => {
    const scene = await api.analyze(project!.id, planWidth, wallHeight);
    setProject((current) => current ? { ...current, scene, status: 'analyzed' } : current);
  });

  const saveCurrentBuild = () => run(async () => {
    const name = slotName.trim() || `Saved Build ${saveSlots.length + 1}`;
    await api.createSaveSlot(project!.id, name);
    await refreshSaveSlots(project!.id);
    setSlotName('');
    setNotice(`Saved “${name}” for later.`);
  });

  const loadSavedBuild = (slot: SaveSlot) => run(async () => {
    const restored = await api.loadSaveSlot(project!.id, slot.id);
    setProject(restored);
    setJob(null);
    if (restored.scene) {
      setPlanWidth(restored.scene.width_m);
      setWallHeight(restored.scene.wall_height_m);
    }
    await refreshSaveSlots(restored.id);
    setNotice(`Loaded “${slot.name}”.`);
  });

  const removeSavedBuild = (slot: SaveSlot) => {
    if (!window.confirm(`Delete the save slot “${slot.name}”? This cannot be undone.`)) return;
    void run(async () => {
      await api.deleteSaveSlot(project!.id, slot.id);
      await refreshSaveSlots(project!.id);
      setNotice(`Deleted “${slot.name}”.`);
    });
  };

  const resetProject = () => {
    const confirmed = window.confirm(
      'Clear the active floor plan, all uploaded images, generated geometry and outputs? Saved slots will not be deleted.',
    );
    if (!confirmed) return;
    void run(async () => {
      const cleared = await api.resetProject(project!.id);
      setProject(cleared);
      setJob(null);
      setPlanWidth(14);
      setWallHeight(2.8);
      setNotice('Active project cleared. Your saved slots are still available.');
    });
  };

  const watchJob = (created: Job) => {
    setJob(created);
    if (pollTimer.current) window.clearInterval(pollTimer.current);
    pollTimer.current = window.setInterval(async () => {
      const latest = await api.getJob(created.id);
      setJob(latest);
      if (latest.status === 'completed' || latest.status === 'failed') {
        if (pollTimer.current) window.clearInterval(pollTimer.current);
      }
    }, 1000);
  };

  const render = (quality: 'preview' | '1080p' | '4k') => run(async () => {
    watchJob(await api.render(project!.id, quality, renderEngine));
  });

  const walkthrough = () => run(async () => {
    watchJob(await api.walkthrough(
      project!.id,
      15,
      '1080p',
      renderEngine === 'technical' ? 'auto' : renderEngine,
    ));
  });

  const hasBuild = Boolean(
    project?.floorplan || project?.scene || Object.keys(project?.assets ?? {}).length,
  );

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark"><Box size={24} /></div>
        <div className="brand-copy">
          <span>Architecture Modelling</span>
          <strong>Dream Home Visualizer</strong>
        </div>
        <div className="topbar-meta">
          <span className="local-badge">Local-first Windows app</span>
          <span>{project?.name ?? 'Starting…'}</span>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {notice && <div className="notice-banner">{notice}</div>}

      <div className="workspace">
        <aside className="left-column">
          <UploadPanel project={project} busy={busy} onFloorplan={uploadFloorplan} onAsset={uploadAsset} />

          <section className="panel save-panel">
            <div className="panel-heading">
              <div><span className="eyebrow">Save manager</span><h2>Build save slots</h2></div>
              <Save size={22} />
            </div>
            <p className="panel-copy">Keep named copies of the complete build, including uploads, geometry and generated outputs.</p>
            <div className="save-row">
              <input
                value={slotName}
                maxLength={80}
                placeholder={`Saved Build ${saveSlots.length + 1}`}
                onChange={(event) => setSlotName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !busy && hasBuild) void saveCurrentBuild();
                }}
              />
              <button className="secondary" disabled={busy || !hasBuild} onClick={saveCurrentBuild}>
                <Save size={16} /> Save
              </button>
            </div>

            <div className="slot-list">
              {saveSlots.length === 0 ? (
                <div className="empty-slots">No saved builds yet.</div>
              ) : saveSlots.map((slot) => (
                <article className="slot-card" key={slot.id}>
                  <div className="slot-copy">
                    <strong>{slot.name}</strong>
                    <span><Clock3 size={12} /> {savedAt(slot.updated_at)}</span>
                    <small>
                      {slot.floorplan_filename ?? 'No floor plan'} · {slot.asset_count} assets · {slot.has_scene ? '3D scene ready' : slot.status}
                    </small>
                  </div>
                  <div className="slot-actions">
                    <button disabled={busy} title="Load saved build" onClick={() => loadSavedBuild(slot)}>
                      <FolderOpen size={16} /> Load
                    </button>
                    <button className="danger-icon" disabled={busy} title="Delete save slot" onClick={() => removeSavedBuild(slot)}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                </article>
              ))}
            </div>

            <button className="danger-button" disabled={busy || !hasBuild} onClick={resetProject}>
              <RotateCcw size={17} /> Reset active project
            </button>
            <span className="reset-note">Reset clears active uploads only. Save slots remain available.</span>
          </section>

          <section className="panel analysis-panel">
            <div className="panel-heading"><div><span className="eyebrow">2. Geometry</span><h2>Structural extraction</h2></div><ScanLine size={22} /></div>
            <div className="two-inputs">
              <label>Plan width (metres)<input type="number" min="2" step="0.1" value={planWidth} onChange={(e) => setPlanWidth(Number(e.target.value))} /></label>
              <label>Wall height (metres)<input type="number" min="2" max="8" step="0.1" value={wallHeight} onChange={(e) => setWallHeight(Number(e.target.value))} /></label>
            </div>
            <button className="primary" disabled={busy || !project?.floorplan} onClick={analyze}><Sparkles size={18} /> Analyze and build 3D scene</button>
            {project?.scene?.rooms?.length ? (
              <div className="room-editor">
                <span className="eyebrow">Detected rooms</span>
                {project.scene.rooms.map((room) => (
                  <label key={room.id}>
                    {room.area_m2.toFixed(1)} m²
                    <input defaultValue={room.name} onBlur={(event) => {
                      const name = event.currentTarget.value.trim();
                      if (!name || name === room.name) return;
                      void run(async () => {
                        const scene = await api.updateRoom(project.id, room.id, name);
                        setProject((current) => current ? { ...current, scene } : current);
                      });
                    }} />
                  </label>
                ))}
              </div>
            ) : null}
          </section>
          <SettingsPanel />
        </aside>

        <section className="right-column">
          <ScenePreview scene={project?.scene} />
          <section className="output-panel">
            <div className="output-copy">
              <span className="eyebrow">4. Output</span>
              <h2>Render and walkthrough</h2>
              <p>Technical previews work immediately. Blender produces deterministic HD/4K images and MP4 walkthroughs when installed.</p>
            </div>
            <div className="render-controls">
              <select value={renderEngine} onChange={(e) => setRenderEngine(e.target.value as typeof renderEngine)}>
                <option value="auto">Auto engine</option>
                <option value="technical">Fast technical renderer</option>
                <option value="blender">Blender 4 renderer</option>
              </select>
              <button disabled={busy || !project?.scene} onClick={() => render('preview')}><ImageIcon size={17} /> Preview</button>
              <button disabled={busy || !project?.scene} onClick={() => render('1080p')}><Play size={17} /> HD</button>
              <button disabled={busy || !project?.scene} onClick={() => render('4k')}><Sparkles size={17} /> 4K</button>
              <button className="primary" disabled={busy || !project?.scene} onClick={walkthrough}><Film size={17} /> 15s walkthrough</button>
            </div>
          </section>

          {job && (
            <section className="job-panel">
              <div><strong>{job.kind.replaceAll('_', ' ')}</strong><span>{job.message}</span></div>
              <div className="progress"><i style={{ width: `${job.progress}%` }} /></div>
              <strong>{job.progress}%</strong>
              {job.output_url && <a href={absoluteUrl(job.output_url)} target="_blank" rel="noreferrer">Open output</a>}
              {job.output_path && window.desktop && <button className="link-button" onClick={() => window.desktop?.openPath(job.output_path!)}>Show in Explorer</button>}
            </section>
          )}
        </section>
      </div>
    </main>
  );
}

export default App;
