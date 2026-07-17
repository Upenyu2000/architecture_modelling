import { useEffect, useRef, useState } from 'react';
import {
  Box, Clock3, Edit3, Film, FolderOpen, Image as ImageIcon, Play, RotateCcw,
  Save, ScanLine, Sparkles, Trash2,
} from 'lucide-react';
import { UploadPanel } from './components/UploadPanel';
import { ScenePreview } from './components/ScenePreview';
import { SettingsPanel } from './components/SettingsPanel';
import { ModelDrawingPanel } from './components/ModelDrawingPanel';
import { ArchitecturePanel } from './components/ArchitecturePanel';
import { absoluteUrl, api, initApi } from './lib/api';
import type { FurniturePayload } from './interior-types';
import type {
  AssetCategory, Job, MaterialUpdate, ModelUnits, OpeningPayload, PlanType, Project, SaveSlot,
  UpAxis, WallDetectionMode,
} from './types';

type Point = [number, number];

function savedAt(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function clampProgress(value: number | undefined): number {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? Number(value) : 0));
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
  const [wallDetection, setWallDetection] = useState<WallDetectionMode>('clean');
  const [minimumWallLength, setMinimumWallLength] = useState(0.9);
  const [planType, setPlanType] = useState<PlanType>('auto');
  const [renderEngine, setRenderEngine] = useState<'auto' | 'technical' | 'blender'>('auto');
  const [job, setJob] = useState<Job | null>(null);
  const pollTimer = useRef<number | null>(null);
  const jobRevisionRef = useRef(0);
  const projectIdRef = useRef<string | null>(null);
  const mountedRef = useRef(true);

  const stopJobPolling = () => {
    if (pollTimer.current !== null) window.clearTimeout(pollTimer.current);
    pollTimer.current = null;
  };

  const cancelJobTracking = () => {
    jobRevisionRef.current += 1;
    stopJobPolling();
  };

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;
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
        if (cancelled || !mountedRef.current) return;
        localStorage.setItem('dreamhome.currentProject', selected.id);
        projectIdRef.current = selected.id;
        setProject(selected);
        setSaveSlots(await api.listSaveSlots(selected.id));
        if (cancelled || !mountedRef.current) return;
        if (selected.scene) {
          setPlanWidth(selected.scene.width_m);
          setWallHeight(selected.scene.wall_height_m);
          setWallDetection((selected.scene.wall_detection_mode as WallDetectionMode) ?? 'clean');
          setPlanType(selected.scene.plan_type ?? 'auto');
        }
      } catch (e) {
        if (!cancelled && mountedRef.current) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled && mountedRef.current) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
      mountedRef.current = false;
      cancelJobTracking();
    };
  }, []);

  useEffect(() => {
    const nextProjectId = project?.id ?? null;
    if (projectIdRef.current !== nextProjectId) {
      cancelJobTracking();
      setJob(null);
      projectIdRef.current = nextProjectId;
    }
  }, [project?.id]);

  const run = async (task: () => Promise<void>) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await task();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (mountedRef.current) setBusy(false);
    }
  };

  const refreshSaveSlots = async (projectId: string) => {
    const slots = await api.listSaveSlots(projectId);
    if (projectIdRef.current === projectId) setSaveSlots(slots);
  };

  const uploadFloorplan = (file: File) => run(async () => {
    const projectId = project!.id;
    const updated = await api.uploadFloorplan(projectId, file);
    if (projectIdRef.current !== projectId) return;
    setProject(updated);
    setNotice('Floor plan uploaded and empty borders removed. Choose the plan type before analysis.');
  });

  const uploadAsset = (category: AssetCategory, slot: string, file: File) => run(async () => {
    const projectId = project!.id;
    const updated = await api.uploadAsset(projectId, category, slot, file);
    if (projectIdRef.current !== projectId) return;
    setProject(updated);
    setNotice('Reference image uploaded. It can now be mapped to a replaceable procedural furniture model or PBR surface.');
  });

  const uploadBuildingModel = (file: File) => run(async () => {
    const projectId = project!.id;
    const updated = await api.uploadBuildingModel(projectId, file);
    if (projectIdRef.current !== projectId) return;
    setProject(updated);
    setNotice('3D building model uploaded. Set the units and cut height, then generate drawings.');
  });

  const compileArchitecture = async (useVisionAi: boolean) => {
    await run(async () => {
      const scene = await api.compileArchitecture(
        project!.id,
        planWidth,
        wallHeight,
        wallDetection,
        minimumWallLength,
        planType,
        useVisionAi,
      );
      setProject((current) => current ? { ...current, scene, status: 'architecture_compiled' } : current);
      setNotice(
        useVisionAi
          ? 'Architectural scene compiled. The configured vision service was used only if private remote processing was enabled.'
          : 'Architectural scene compiled with merged walls, portal openings, furniture proposals, collision data and walkthrough coordinates.',
      );
    });
  };

  const analyze = () => run(async () => {
    const projectId = project!.id;
    const detected = await api.analyze(
      projectId,
      planWidth,
      wallHeight,
      wallDetection,
      minimumWallLength,
      planType,
    );
    if (projectIdRef.current !== projectId) return;
    setProject((current) => current ? { ...current, scene: detected, status: 'analyzed' } : current);
    setPlanType(detected.plan_type);
    const scene = await api.compileArchitecture(
      projectId,
      planWidth,
      wallHeight,
      wallDetection,
      minimumWallLength,
      detected.plan_type,
      false,
    );
    if (projectIdRef.current !== projectId) return;
    setProject((current) => current ? { ...current, scene, status: 'architecture_compiled' } : current);
    setNotice('Analysis and production compilation complete. Verify rooms, furniture, doors, windows, cutaway and portal walkthrough.');
  });

  const applyMaterials = async (settings: MaterialUpdate) => {
    await run(async () => {
      const scene = await api.updateMaterials(project!.id, settings);
      setProject((current) => current ? { ...current, scene, status: 'materials_updated' } : current);
      setNotice(`Applied “${settings.palette_name}” to the synchronized 3D scene.`);
    });
  };

  const startManualLayout = async () => {
    if (project?.scene?.rooms.length) {
      const confirmed = window.confirm(
        'Replace the current detected layout with a blank manual layout? Save the current build first if you may need it later.',
      );
      if (!confirmed) return;
    }
    await run(async () => {
      const scene = await api.startManualLayout(project!.id, planWidth, wallHeight, true);
      setProject((current) => current ? { ...current, scene, status: 'manual_layout' } : current);
      setNotice('Manual room layout started. Draw free-form rooms, then add shared-wall doors and interior furniture.');
    });
  };

  const addRoom = async () => {
    if (!project?.scene) return;
    const count = project.scene.rooms.length;
    const width = Math.min(3.2, Math.max(1.2, project.scene.width_m * 0.24));
    const depth = Math.min(3.2, Math.max(1.2, project.scene.depth_m * 0.24));
    const xRange = Math.max(0, project.scene.width_m - width);
    const zRange = Math.max(0, project.scene.depth_m - depth);
    const x = xRange ? (count * 0.75) % xRange : 0;
    const z = zRange ? (count * 0.62) % zRange : 0;
    const scene = await api.addRoom(project.id, `Room ${count + 1}`, x, z, width, depth);
    setProject((current) => current ? { ...current, scene, status: 'layout_updated' } : current);
  };

  const updateRoomGeometry = async (roomId: string, polygon: Point[]) => {
    if (!project) return;
    const scene = await api.updateRoomGeometry(project.id, roomId, polygon);
    setProject((current) => current ? { ...current, scene, status: 'layout_updated' } : current);
  };

  const deleteRoom = async (roomId: string) => {
    if (!project) return;
    const scene = await api.deleteRoom(project.id, roomId);
    setProject((current) => current ? { ...current, scene, status: 'layout_updated' } : current);
  };

  const renameRoom = async (roomId: string, name: string) => {
    if (!project) return;
    const scene = await api.updateRoom(project.id, roomId, name);
    setProject((current) => current ? { ...current, scene } : current);
  };

  const addOpening = async (payload: OpeningPayload) => {
    if (!project) return;
    const scene = await api.addOpening(project.id, payload);
    setProject((current) => current ? { ...current, scene, status: 'openings_updated' } : current);
    setNotice('Door, window or passage added. Open First Person and press E near an interactive door.');
  };

  const updateOpening = async (openingId: string, payload: Partial<OpeningPayload>) => {
    if (!project) return;
    const scene = await api.updateOpening(project.id, openingId, payload);
    setProject((current) => current ? { ...current, scene, status: 'openings_updated' } : current);
    setNotice('Opening updated and the portal wall cut-out was rebuilt.');
  };

  const deleteOpening = async (openingId: string) => {
    if (!project) return;
    const scene = await api.deleteOpening(project.id, openingId);
    setProject((current) => current ? { ...current, scene, status: 'openings_updated' } : current);
    setNotice('Opening removed.');
  };

  const addFurniture = async (payload: FurniturePayload) => {
    if (!project) return;
    const scene = await api.addFurniture(project.id, payload);
    setProject((current) => current ? { ...current, scene, status: 'interior_updated' } : current);
    setNotice(`${payload.object_type.replaceAll('_', ' ')} added as a detailed procedural PBR model.`);
  };

  const updateFurniture = async (objectId: string, payload: Partial<FurniturePayload>) => {
    if (!project) return;
    const scene = await api.updateFurniture(project.id, objectId, payload);
    setProject((current) => current ? { ...current, scene, status: 'interior_updated' } : current);
    setNotice('Furniture replaced and the live cutaway, first-person viewport and render scene were updated.');
  };

  const deleteFurniture = async (objectId: string) => {
    if (!project) return;
    const scene = await api.deleteFurniture(project.id, objectId);
    setProject((current) => current ? { ...current, scene, status: 'interior_updated' } : current);
    setNotice('Furniture removed.');
  };

  const saveCurrentBuild = () => run(async () => {
    const projectId = project!.id;
    const name = slotName.trim() || `Saved Build ${saveSlots.length + 1}`;
    await api.createSaveSlot(projectId, name);
    await refreshSaveSlots(projectId);
    if (projectIdRef.current !== projectId) return;
    setSlotName('');
    setNotice(`Saved “${name}” for later.`);
  });

  const loadSavedBuild = (slot: SaveSlot) => run(async () => {
    const projectId = project!.id;
    cancelJobTracking();
    setJob(null);
    const restored = await api.loadSaveSlot(projectId, slot.id);
    if (projectIdRef.current !== projectId) return;
    setProject(restored);
    if (restored.scene) {
      setPlanWidth(restored.scene.width_m);
      setWallHeight(restored.scene.wall_height_m);
      setWallDetection((restored.scene.wall_detection_mode as WallDetectionMode) ?? 'clean');
      setPlanType(restored.scene.plan_type ?? 'auto');
    }
    await refreshSaveSlots(restored.id);
    setNotice(`Loaded “${slot.name}”.`);
  });

  const removeSavedBuild = (slot: SaveSlot) => {
    if (!window.confirm(`Delete the save slot “${slot.name}”? This cannot be undone.`)) return;
    void run(async () => {
      const projectId = project!.id;
      await api.deleteSaveSlot(projectId, slot.id);
      await refreshSaveSlots(projectId);
      if (projectIdRef.current === projectId) setNotice(`Deleted “${slot.name}”.`);
    });
  };

  const resetProject = () => {
    const confirmed = window.confirm(
      'Clear the active floor plan, 3D model, all uploaded images, generated geometry, drawings and outputs? Saved slots will not be deleted.',
    );
    if (!confirmed) return;
    void run(async () => {
      const projectId = project!.id;
      cancelJobTracking();
      setJob(null);
      const cleared = await api.resetProject(projectId);
      if (projectIdRef.current !== projectId) return;
      setProject(cleared);
      setPlanWidth(14);
      setWallHeight(2.8);
      setWallDetection('clean');
      setMinimumWallLength(0.9);
      setPlanType('auto');
      setNotice('Active project cleared. Your saved slots are still available.');
    });
  };

  const scheduleJobPoll = (jobId: string, ownerProjectId: string, revision: number) => {
    stopJobPolling();
    pollTimer.current = window.setTimeout(async () => {
      if (!mountedRef.current || revision !== jobRevisionRef.current || projectIdRef.current !== ownerProjectId) return;
      try {
        const latest = await api.getJob(jobId);
        if (!mountedRef.current || revision !== jobRevisionRef.current || projectIdRef.current !== ownerProjectId) return;
        setJob(latest);
        if (latest.status === 'failed') {
          stopJobPolling();
          setError(latest.error || latest.message || 'Background job failed.');
          return;
        }
        if (latest.status === 'completed') {
          stopJobPolling();
          if (latest.kind === 'drawing_set') {
            const refreshed = await api.getProject(ownerProjectId);
            if (!mountedRef.current || revision !== jobRevisionRef.current || projectIdRef.current !== ownerProjectId) return;
            setProject(refreshed);
            setNotice('2D drawing set generated and saved with this project.');
          }
          return;
        }
        scheduleJobPoll(jobId, ownerProjectId, revision);
      } catch (pollError) {
        if (!mountedRef.current || revision !== jobRevisionRef.current) return;
        stopJobPolling();
        setError(pollError instanceof Error ? pollError.message : String(pollError));
      }
    }, 1000);
  };

  const watchJob = (created: Job, ownerProjectId: string) => {
    const revision = jobRevisionRef.current + 1;
    jobRevisionRef.current = revision;
    stopJobPolling();
    setJob(created);
    if (created.status === 'failed') {
      setError(created.error || created.message || 'Background job failed.');
      return;
    }
    if (created.status !== 'completed') scheduleJobPoll(created.id, ownerProjectId, revision);
  };

  const generateDrawings = (sliceHeight: number, upAxis: UpAxis, units: ModelUnits) => run(async () => {
    const projectId = project!.id;
    watchJob(await api.createDrawings(projectId, sliceHeight, upAxis, units), projectId);
  });

  const render = (quality: 'preview' | '1080p' | '4k') => run(async () => {
    const projectId = project!.id;
    watchJob(await api.render(projectId, quality, renderEngine), projectId);
  });

  const walkthrough = () => run(async () => {
    const projectId = project!.id;
    watchJob(await api.walkthrough(
      projectId,
      15,
      '1080p',
      renderEngine === 'technical' ? 'auto' : renderEngine,
    ), projectId);
  });

  const hasBuild = Boolean(
    project?.floorplan || project?.building_model || project?.scene || project?.drawing_set
      || Object.keys(project?.assets ?? {}).length,
  );
  const jobProgress = clampProgress(job?.progress);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark"><Box size={24} /></div>
        <div className="brand-copy"><span>Arch-AI Convert 1.5</span><strong>Architectural and Interior Design Visualizer</strong></div>
        <div className="topbar-meta"><span className="local-badge">Local-first Windows app</span><span>{project?.name ?? 'Starting…'}</span></div>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}
      {notice && <div className="notice-banner" role="status">{notice}</div>}

      <div className="workspace">
        <aside className="left-column">
          <UploadPanel project={project} busy={busy} onFloorplan={uploadFloorplan} onAsset={uploadAsset} />

          <section className="panel save-panel">
            <div className="panel-heading"><div><span className="eyebrow">Save manager</span><h2>Build save slots</h2></div><Save size={22} /></div>
            <p className="panel-copy">Keep named copies of the complete build, including uploads, geometry, interiors, materials, drawings and generated outputs.</p>
            <div className="save-row">
              <input value={slotName} maxLength={80} placeholder={`Saved Build ${saveSlots.length + 1}`} onChange={(event) => setSlotName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !busy && hasBuild) void saveCurrentBuild(); }} />
              <button type="button" className="secondary" disabled={busy || !hasBuild} onClick={saveCurrentBuild}><Save size={16} /> Save</button>
            </div>
            <div className="slot-list">
              {saveSlots.length === 0 ? <div className="empty-slots">No saved builds yet.</div> : saveSlots.map((slot) => (
                <article className="slot-card" key={slot.id}>
                  <div className="slot-copy"><strong>{slot.name}</strong><span><Clock3 size={12} /> {savedAt(slot.updated_at)}</span><small>{slot.floorplan_filename ?? slot.building_model_filename ?? 'No source file'} · {slot.asset_count} assets · {slot.has_drawings ? 'drawings ready' : slot.has_scene ? '3D scene ready' : slot.status}</small></div>
                  <div className="slot-actions"><button type="button" disabled={busy} title="Load saved build" onClick={() => loadSavedBuild(slot)}><FolderOpen size={16} /> Load</button><button type="button" className="danger-icon" disabled={busy} title="Delete save slot" onClick={() => removeSavedBuild(slot)}><Trash2 size={16} /></button></div>
                </article>
              ))}
            </div>
            <button type="button" className="danger-button" disabled={busy || !hasBuild} onClick={resetProject}><RotateCcw size={17} /> Reset active project</button>
            <span className="reset-note">Reset clears active files only. Save slots remain available.</span>
          </section>

          <section className="panel analysis-panel">
            <div className="panel-heading"><div><span className="eyebrow">2. Geometry</span><h2>Automatic or manual layout</h2></div><ScanLine size={22} /></div>
            <p className="panel-copy">Blueprint and rendered plans use separate processing paths. Manual mode supports free-form room polygons, shared-wall snapping and portal doorways.</p>
            <div className="two-inputs">
              <label>Plan width (metres)<input type="number" min="2" step="0.1" value={planWidth} onChange={(e) => setPlanWidth(Number(e.target.value))} /></label>
              <label>Wall height (metres)<input type="number" min="2" max="8" step="0.1" value={wallHeight} onChange={(e) => setWallHeight(Number(e.target.value))} /></label>
              <label>Plan type<select value={planType} onChange={(event) => setPlanType(event.target.value as PlanType)}><option value="auto">Auto detect</option><option value="blueprint">Blueprint / CAD line drawing</option><option value="rendered">Rendered / furnished plan</option></select></label>
              <label>Wall detection<select value={wallDetection} onChange={(event) => setWallDetection(event.target.value as WallDetectionMode)}><option value="clean">Clean — fewer walls</option><option value="balanced">Balanced</option><option value="detailed">Detailed — preserve short walls</option></select></label>
              <label>Minimum wall length<div className="unit-input"><input type="number" min="0.3" max="10" step="0.1" value={minimumWallLength} onChange={(event) => setMinimumWallLength(Number(event.target.value))} /><span>m</span></div></label>
            </div>
            <button type="button" className="primary" disabled={busy || !project?.floorplan} onClick={analyze}><Sparkles size={18} /> Analyze, classify and compile</button>
            <button type="button" className="secondary full-width" disabled={busy || !project?.floorplan} onClick={() => void startManualLayout()}><Edit3 size={18} /> Start blank manual room layout</button>
            <span className="manual-note">Use Edit Rooms, Doors & Windows and Interior Design to correct every result.</span>
          </section>

          <ArchitecturePanel project={project} busy={busy} onCompile={compileArchitecture} onApply={applyMaterials} />
          <ModelDrawingPanel project={project} busy={busy} onUpload={uploadBuildingModel} onGenerate={generateDrawings} />
          <SettingsPanel />
        </aside>

        <section className="right-column">
          <ScenePreview
            project={project}
            busy={busy}
            onAddRoom={addRoom}
            onUpdateRoom={updateRoomGeometry}
            onDeleteRoom={deleteRoom}
            onRenameRoom={renameRoom}
            onAddOpening={addOpening}
            onUpdateOpening={updateOpening}
            onDeleteOpening={deleteOpening}
            onAddFurniture={addFurniture}
            onUpdateFurniture={updateFurniture}
            onDeleteFurniture={deleteFurniture}
          />
          <section className="output-panel">
            <div className="output-copy"><span className="eyebrow">5. Output</span><h2>Photorealistic interior cutaway and walkthrough</h2><p>The same scene JSON drives detailed procedural furniture, uploaded-image materials, portal-aware first-person interaction and Blender HD/4K output.</p></div>
            <div className="render-controls">
              <select value={renderEngine} onChange={(e) => setRenderEngine(e.target.value as typeof renderEngine)}><option value="auto">Auto engine</option><option value="technical">Fast technical renderer</option><option value="blender">Blender 4 renderer</option></select>
              <button type="button" disabled={busy || !project?.scene} onClick={() => render('preview')}><ImageIcon size={17} /> Preview</button>
              <button type="button" disabled={busy || !project?.scene} onClick={() => render('1080p')}><Play size={17} /> HD</button>
              <button type="button" disabled={busy || !project?.scene} onClick={() => render('4k')}><Sparkles size={17} /> 4K</button>
              <button type="button" className="primary" disabled={busy || !project?.scene} onClick={walkthrough}><Film size={17} /> 15s walkthrough</button>
            </div>
          </section>

          {job && <section className={`job-panel ${job.status}`} role="status"><div><strong>{job.kind.replaceAll('_', ' ')}</strong><span>{job.message}</span></div><div className="progress"><i style={{ width: `${jobProgress}%` }} /></div><strong>{jobProgress}%</strong>{job.output_url && <a href={absoluteUrl(job.output_url)} target="_blank" rel="noreferrer">Open output</a>}{job.output_path && window.desktop && <button type="button" className="link-button" onClick={() => window.desktop?.openPath(job.output_path!)}>Show in Explorer</button>}</section>}
        </section>
      </div>
    </main>
  );
}

export default App;
