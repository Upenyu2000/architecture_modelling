import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle, Camera, CheckCircle2, Download, Image as ImageIcon, Layers3,
  Maximize2, RefreshCcw, Sparkles,
} from 'lucide-react';
import { absoluteUrl, api } from '../lib/api';
import {
  DESIGN_STYLES, type DesignStyle, type PresentationEngine, type RenderQuality, styleLabel,
} from '../lib/presentation';
import type { Job, Project } from '../types';
import Button from './ui/Button';

interface PresentationRenderMetadata {
  top_down_url?: string;
  perspective_url?: string;
  bundle_url?: string;
  style?: string;
  style_label?: string;
  quality?: string;
  perspective_room?: string;
  text_removed?: boolean;
  dining_adjusted?: boolean;
  furnishing_added?: number;
}

interface Props {
  project: Project | null;
  disabled?: boolean;
}

type PresentationView = 'top_down' | 'perspective';

type StartedConfiguration = {
  style: DesignStyle;
  quality: RenderQuality;
};

function safeDownloadName(value: string | undefined): string {
  const normalized = (value || 'dream-home')
    .normalize('NFKD')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
  return normalized || 'dream-home';
}

function clampProgress(value: number | undefined): number {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? Number(value) : 0));
}

export function PresentationStudio({ project, disabled = false }: Props) {
  const [style, setStyle] = useState<DesignStyle>('modern');
  const [quality, setQuality] = useState<RenderQuality>('1080p');
  const [engine, setEngine] = useState<PresentationEngine>('auto');
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [completedJob, setCompletedJob] = useState<Job | null>(null);
  const [activeView, setActiveView] = useState<PresentationView>('top_down');
  const [error, setError] = useState('');
  const [generationStarting, setGenerationStarting] = useState(false);
  const [startedConfiguration, setStartedConfiguration] = useState<StartedConfiguration | null>(null);
  const pollRef = useRef<number | null>(null);
  const runRevisionRef = useRef(0);
  const mountedRef = useRef(true);

  const resultJob = activeJob?.status === 'completed' ? activeJob : completedJob;
  const metadata = (resultJob?.metadata ?? {}) as PresentationRenderMetadata;
  const topDownUrl = absoluteUrl(metadata.top_down_url);
  const perspectiveUrl = absoluteUrl(metadata.perspective_url);
  const bundleUrl = absoluteUrl(metadata.bundle_url ?? resultJob?.output_url);
  const sourceUrl = absoluteUrl(project?.floorplan?.preview_url);
  const activeRenderUrl = activeView === 'top_down' ? topDownUrl : perspectiveUrl;
  const isRunning = activeJob?.status === 'queued' || activeJob?.status === 'running';
  const controlsLocked = disabled || isRunning || generationStarting;
  const selectedStyle = useMemo(
    () => DESIGN_STYLES.find((option) => option.value === style) ?? DESIGN_STYLES[0],
    [style],
  );
  const downloadBase = safeDownloadName(project?.name);

  const stopPolling = () => {
    if (pollRef.current !== null) window.clearTimeout(pollRef.current);
    pollRef.current = null;
  };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      runRevisionRef.current += 1;
      stopPolling();
    };
  }, []);

  useEffect(() => {
    runRevisionRef.current += 1;
    stopPolling();
    setActiveJob(null);
    setCompletedJob(null);
    setActiveView('top_down');
    setError('');
    setGenerationStarting(false);
    setStartedConfiguration(null);
  }, [project?.id]);

  const schedulePoll = (jobId: string, revision: number) => {
    stopPolling();
    pollRef.current = window.setTimeout(async () => {
      if (!mountedRef.current || revision !== runRevisionRef.current) return;
      try {
        const latest = await api.getJob(jobId);
        if (!mountedRef.current || revision !== runRevisionRef.current) return;
        setActiveJob(latest);
        if (latest.status === 'completed') {
          setCompletedJob(latest);
          setActiveView('top_down');
          stopPolling();
          return;
        }
        if (latest.status === 'failed') {
          stopPolling();
          setError(latest.error || latest.message || 'Presentation rendering failed.');
          return;
        }
        schedulePoll(jobId, revision);
      } catch (pollError) {
        if (!mountedRef.current || revision !== runRevisionRef.current) return;
        stopPolling();
        setError(pollError instanceof Error ? pollError.message : String(pollError));
      }
    }, 1000);
  };

  const watchJob = (created: Job, revision: number) => {
    if (!mountedRef.current || revision !== runRevisionRef.current) return;
    setActiveJob(created);
    schedulePoll(created.id, revision);
  };

  const generate = async () => {
    if (!project?.scene || controlsLocked) return;
    const projectId = project.id;
    const revision = runRevisionRef.current + 1;
    runRevisionRef.current = revision;
    stopPolling();
    setError('');
    setGenerationStarting(true);
    setStartedConfiguration({ style, quality });
    try {
      const created = await api.presentationRenders(projectId, style, quality, engine);
      if (!mountedRef.current || revision !== runRevisionRef.current || project.id !== projectId) return;
      watchJob(created, revision);
    } catch (generationError) {
      if (!mountedRef.current || revision !== runRevisionRef.current) return;
      setError(generationError instanceof Error ? generationError.message : String(generationError));
    } finally {
      if (mountedRef.current && revision === runRevisionRef.current) setGenerationStarting(false);
    }
  };

  const download = (url: string | undefined, suffix: string, extension = 'png') => {
    if (!url) return;
    const link = document.createElement('a');
    link.href = url;
    link.download = `${downloadBase}-${suffix}.${extension}`;
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const progress = clampProgress(activeJob?.progress);
  const runningStyle = startedConfiguration?.style ?? style;

  return (
    <section className="presentation-studio roomify-panel">
      <header className="roomify-panel-header">
        <div className="roomify-panel-meta">
          <span>Architectural presentation</span>
          <h2>Top-down plan and interior perspective</h2>
          <p>Verified geometry, text-free output and one consistent design language across both views.</p>
        </div>
        <div className="presentation-badge"><Layers3 size={17} /> Dual render</div>
      </header>

      <div className="presentation-controls">
        <label>
          Design style
          <select disabled={controlsLocked} value={style} onChange={(event) => setStyle(event.target.value as DesignStyle)}>
            {DESIGN_STYLES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <small>{selectedStyle.description}</small>
        </label>
        <label>
          Output quality
          <select disabled={controlsLocked} value={quality} onChange={(event) => setQuality(event.target.value as RenderQuality)}>
            <option value="preview">Preview</option>
            <option value="1080p">Presentation HD</option>
            <option value="4k">4K presentation</option>
          </select>
          <small>Both views are generated at the selected quality.</small>
        </label>
        <label>
          Photoreal engine
          <select disabled={controlsLocked} value={engine} onChange={(event) => setEngine(event.target.value as PresentationEngine)}>
            <option value="auto">Use configured Blender</option>
            <option value="blender">Require Blender 4.x</option>
          </select>
          <small>Blender produces PBR materials, realistic shadows and interior lighting.</small>
        </label>
        <Button
          size="lg"
          className="presentation-generate"
          disabled={controlsLocked || !project?.scene}
          onClick={() => void generate()}
        >
          {isRunning || generationStarting ? <RefreshCcw className="spin" size={18} /> : <Sparkles size={18} />}
          {generationStarting ? 'Starting renderer' : isRunning ? 'Rendering both views' : `Generate ${styleLabel(style)} presentation`}
        </Button>
      </div>

      {activeJob ? (
        <div className={`presentation-progress ${activeJob.status}`} role="status" aria-live="polite">
          <div>
            {activeJob.status === 'completed' ? <CheckCircle2 size={18} /> : activeJob.status === 'failed' ? <AlertCircle size={18} /> : <RefreshCcw className="spin" size={18} />}
            <span>{activeJob.message}</span>
          </div>
          <div className="presentation-progress-track"><i style={{ width: `${progress}%` }} /></div>
          <strong>{progress}%</strong>
        </div>
      ) : null}

      {error ? <div className="presentation-error" role="alert"><AlertCircle size={18} /> <span>{error}</span></div> : null}

      <div className="presentation-stage">
        <div className="presentation-view-tabs" role="tablist" aria-label="Presentation view">
          <button type="button" role="tab" aria-selected={activeView === 'top_down'} className={activeView === 'top_down' ? 'active' : ''} onClick={() => setActiveView('top_down')}>
            <ImageIcon size={16} /> Top-down layout
          </button>
          <button type="button" role="tab" aria-selected={activeView === 'perspective'} className={activeView === 'perspective' ? 'active' : ''} onClick={() => setActiveView('perspective')}>
            <Camera size={16} /> Eye-level interior
          </button>
        </div>

        <div className="presentation-render-frame">
          {activeRenderUrl ? (
            <img src={activeRenderUrl} alt={activeView === 'top_down' ? 'Photorealistic top-down architectural render' : 'Photorealistic eye-level interior render'} />
          ) : sourceUrl ? (
            <div className="presentation-source-placeholder">
              <img src={sourceUrl} alt="Uploaded floor plan awaiting presentation rendering" />
              <div><Sparkles size={26} /><strong>Ready to create both presentation views</strong><span>Plan labels are excluded because the render is rebuilt from verified geometry.</span></div>
            </div>
          ) : (
            <div className="presentation-empty"><ImageIcon size={34} /><strong>Upload and analyse a floor plan first</strong></div>
          )}
          {isRunning || generationStarting ? (
            <div className="presentation-render-overlay">
              <RefreshCcw className="spin" size={34} />
              <strong>{activeJob?.message || 'Starting architectural renderer'}</strong>
              <span>Applying {styleLabel(runningStyle)} materials, furniture and lighting.</span>
            </div>
          ) : null}
        </div>

        {topDownUrl || perspectiveUrl ? (
          <div className="presentation-output-actions">
            <Button variant="secondary" size="sm" disabled={!activeRenderUrl} onClick={() => download(activeRenderUrl, activeView)}>
              <Download size={15} /> Download current PNG
            </Button>
            {bundleUrl ? <button type="button" className="btn btn--outline btn--sm" onClick={() => download(bundleUrl, 'presentation', 'zip')}><Download size={15} /> Download presentation ZIP</button> : null}
            {activeRenderUrl ? <a className="btn btn--ghost btn--sm" href={activeRenderUrl} target="_blank" rel="noreferrer"><Maximize2 size={15} /> Open full size</a> : null}
          </div>
        ) : null}
      </div>

      {resultJob?.status === 'completed' ? (
        <div className="presentation-summary">
          <article><strong>{metadata.style_label || styleLabel(style)}</strong><span>Design language</span></article>
          <article><strong>{metadata.perspective_room || 'Best interior room'}</strong><span>Perspective vantage</span></article>
          <article><strong>{metadata.dining_adjusted ? 'Optimised' : 'Verified'}</strong><span>Dining circulation</span></article>
          <article><strong>{metadata.text_removed ? 'Removed' : 'Not imported'}</strong><span>Plan text and labels</span></article>
          <article><strong>{metadata.furnishing_added ?? 0}</strong><span>Render-only furnishings added</span></article>
        </div>
      ) : null}

      {sourceUrl && topDownUrl ? (
        <div className="presentation-compare">
          <header><div><span>Comparison</span><h3>Floor plan to verified 3D layout</h3></div><small>Source labels remain visible only in the source pane.</small></header>
          <div><figure><img src={sourceUrl} alt="Original floor plan" /><figcaption>Original plan</figcaption></figure><figure><img src={topDownUrl} alt="Top-down 3D architectural render" /><figcaption>Text-free 3D render</figcaption></figure></div>
        </div>
      ) : null}
    </section>
  );
}
