import { useEffect, useRef, useState } from 'react';
import { Box, Film, Image as ImageIcon, Play, ScanLine, Sparkles } from 'lucide-react';
import { UploadPanel } from './components/UploadPanel';
import { ScenePreview } from './components/ScenePreview';
import { SettingsPanel } from './components/SettingsPanel';
import { absoluteUrl, api, initApi } from './lib/api';
import type { AssetCategory, Job, Project } from './types';

function App() {
  const [project, setProject] = useState<Project | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
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
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    })();
    return () => { if (pollTimer.current) window.clearInterval(pollTimer.current); };
  }, []);

  const run = async (task: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await task(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };

  const uploadFloorplan = (file: File) => run(async () => setProject(await api.uploadFloorplan(project!.id, file)));
  const uploadAsset = (category: AssetCategory, slot: string, file: File) => run(async () => setProject(await api.uploadAsset(project!.id, category, slot, file)));
  const analyze = () => run(async () => {
    const scene = await api.analyze(project!.id, planWidth, wallHeight);
    setProject((current) => current ? { ...current, scene, status: 'analyzed' } : current);
  });

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

  const render = (quality: 'preview' | '1080p' | '4k') => run(async () => watchJob(await api.render(project!.id, quality, renderEngine)));
  const walkthrough = () => run(async () => watchJob(await api.walkthrough(project!.id, 15, '1080p', renderEngine === 'technical' ? 'auto' : renderEngine)));

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
          <span>{project?.id.slice(0, 8) ?? 'Starting…'}</span>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div className="workspace">
        <aside className="left-column">
          <UploadPanel project={project} busy={busy} onFloorplan={uploadFloorplan} onAsset={uploadAsset} />
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
