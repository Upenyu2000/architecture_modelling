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

export function PresentationStudio({ project, disabled = false }: Props) {
  const [style, setStyle] = useState<DesignStyle>('modern');
  const [quality, setQuality] = useState<RenderQuality>('1080p');
  const [engine, setEngine] = useState<PresentationEngine>('auto');
  const [job, setJob] = useState<Job | null>(null);
  const [activeView, setActiveView] = useState<PresentationView>('top_down');
  const [error, setError] = useState('');
  const pollRef = useRef<number | null>(null);

  const metadata = (job?.metadata ?? {}) as PresentationRenderMetadata;
  const topDownUrl = absoluteUrl(metadata.top_down_url);
  const perspectiveUrl = absoluteUrl(metadata.perspective_url);
  const bundleUrl = absoluteUrl(metadata.bundle_url ?? job?.output_url);
  const sourceUrl = absoluteUrl(project?.floorplan?.preview_url);
  const activeRenderUrl = activeView === 'top_down' ? topDownUrl : perspectiveUrl;
  const isRunning = job?.status === 'queued' || job?.status === 'running';
  const selectedStyle = useMemo(
    () => DESIGN_STYLES.find((option) => option.value === style) ?? DESIGN_STYLES[0],
    [style],
  );

  useEffect(() => () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
  }, []);

  const stopPolling = () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = null;
  };

  const watchJob = (created: Job) => {
    setJob(created);
    stopPolling();
    pollRef.current = window.setInterval(async () => {
      try {
        const latest = await api.getJob(created.id);
        setJob(latest);
        if (latest.status === 'completed') {
          stopPolling();
          setActiveView('top_down');
        } else if (latest.status === 'failed') {
          stopPolling();
          setError(latest.error || latest.message || 'Presentation rendering failed.');
        }
      } catch (pollError) {
        stopPolling();
        setError(pollError instanceof Error ? pollError.message : String(pollError));
      }
    }, 1000);
  };

  const generate = async () => {
    if (!project?.scene || disabled || isRunning) return;
    setError('');
    setJob(null);
    try {
      watchJob(await api.presentationRenders(project.id, style, quality, engine));
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : String(generationError));
    }
  };

  const download = (url: string | undefined, suffix: string) => {
    if (!url) return;
    const link = document.createElement('a');
    link.href = url;
    link.download = `${project?.name || 'dream-home'}-${suffix}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

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
          <select value={style} onChange={(event) => setStyle(event.target.value as DesignStyle)}>
            {DESIGN_STYLES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <small>{selectedStyle.description}</small>
        </label>
        <label>
          Output quality
          <select value={quality} onChange={(event) => setQuality(event.target.value as RenderQuality)}>
            <option value="preview">Preview</option>
            <option value="1080p">Presentation HD</option>
            <option value="4k">4K presentation</option>
          </select>
          <small>Both views are generated at the selected quality.</small>
        </label>
        <label>
          Photoreal engine
          <select value={engine} onChange={(event) => setEngine(event.target.value as PresentationEngine)}>
            <option value="auto">Auto-detect Blender</option>
            <option value="blender">Require Blender 4.x</option>
          </select>
          <small>Blender produces PBR materials, realistic shadows and interior lighting.</small>
        </label>
        <Button
          size="lg"
          className="presentation-generate"
          disabled={disabled || !project?.scene || isRunning}
          onClick={() => void generate()}
        >
          {isRunning ? <RefreshCcw className="spin" size={18} /> : <Sparkles size={18} />}
          {isRunning ? 'Rendering both views' : `Generate ${styleLabel(style)} presentation`}
        </Button>
      </div>

      {job ? (
        <div className={`presentation-progress ${job.status}`}>
          <div>
            {job.status === 'completed' ? <CheckCircle2 size={18} /> : <RefreshCcw className={isRunning ? 'spin' : ''} size={18} />}
            <span>{job.message}</span>
          </div>
          <div className="presentation-progress-track"><i style={{ width: `${job.progress}%` }} /></div>
          <strong>{job.progress}%</strong>
        </div>
      ) : null}

      {error ? <div className="presentation-error"><AlertCircle size={18} /> {error}</div> : null}

      <div className="presentation-stage">
        <div className="presentation-view-tabs" role="tablist">
          <button className={activeView === 'top_down' ? 'active' : ''} onClick={() => setActiveView('top_down')}>
            <ImageIcon size={16} /> Top-down layout
          </button>
          <button className={activeView === 'perspective' ? 'active' : ''} onClick={() => setActiveView('perspective')}>
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
          {isRunning ? (
            <div className="presentation-render-overlay">
              <RefreshCcw className="spin" size={34} />
              <strong>{job?.message || 'Building presentation scene'}</strong>
              <span>Applying {styleLabel(style)} materials, furniture and lighting.</span>
            </div>
          ) : null}
        </div>

        {topDownUrl || perspectiveUrl ? (
          <div className="presentation-output-actions">
            <Button variant="secondary" size="sm" disabled={!activeRenderUrl} onClick={() => download(activeRenderUrl, activeView)}>
              <Download size={15} /> Download current PNG
            </Button>
            {bundleUrl ? <a className="btn btn--outline btn--sm" href={bundleUrl} download><Download size={15} /> Download presentation ZIP</a> : null}
            {activeRenderUrl ? <a className="btn btn--ghost btn--sm" href={activeRenderUrl} target="_blank" rel="noreferrer"><Maximize2 size={15} /> Open full size</a> : null}
          </div>
        ) : null}
      </div>

      {job?.status === 'completed' ? (
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
