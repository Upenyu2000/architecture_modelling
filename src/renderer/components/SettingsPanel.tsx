import { useEffect, useState } from 'react';
import { Cpu, FolderOpen, Save } from 'lucide-react';
import { api } from '../lib/api';

type SettingValue = string | boolean | number;

export function SettingsPanel() {
  const [settings, setSettings] = useState<Record<string, SettingValue>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.getSettings().then(setSettings).catch(() => undefined); }, []);

  const update = (key: string, value: SettingValue) => setSettings((current) => ({ ...current, [key]: value }));
  const browseFile = async (key: string, name: string, extensions: string[]) => {
    const selected = await window.desktop?.selectFile([{ name, extensions }]);
    if (selected) update(key, selected);
  };
  const save = async () => {
    setSettings(await api.saveSettings(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <details className="settings-panel">
      <summary><Cpu size={17} /> AI, OCR, training and render settings</summary>
      <div className="settings-grid">
        <label>
          Local floor-plan segmentation model
          <div className="input-with-button">
            <input value={String(settings.segmentation_model_path ?? '')} onChange={(e) => update('segmentation_model_path', e.target.value)} placeholder="Optional ONNX model: background, wall, room, door, window" />
            <button onClick={() => void browseFile('segmentation_model_path', 'ONNX segmentation model', ['onnx'])}><FolderOpen size={16} /></button>
          </div>
          <small>When configured, this model guides wall, room, door and window extraction before the deterministic vector-cleaning stage.</small>
        </label>
        <label>
          Segmentation input size
          <input type="number" min="128" max="2048" step="32" value={Number(settings.segmentation_input_size ?? 512)} onChange={(e) => update('segmentation_input_size', Number(e.target.value) || 512)} />
        </label>
        <label>
          Segmentation confidence threshold
          <input type="number" min="0.05" max="0.95" step="0.05" value={Number(settings.segmentation_threshold ?? 0.5)} onChange={(e) => update('segmentation_threshold', Number(e.target.value) || 0.5)} />
        </label>
        <label>
          Training workspace
          <input value={String(settings.training_workspace ?? '')} onChange={(e) => update('training_workspace', e.target.value)} placeholder="Optional local folder containing prepared datasets and exported models" />
        </label>
        <label>
          Blender executable
          <div className="input-with-button">
            <input value={String(settings.blender_executable ?? '')} onChange={(e) => update('blender_executable', e.target.value)} placeholder="Auto-detect or choose blender.exe" />
            <button onClick={() => void browseFile('blender_executable', 'Blender', ['exe'])}><FolderOpen size={16} /></button>
          </div>
        </label>
        <label>
          Tesseract OCR executable
          <div className="input-with-button">
            <input value={String(settings.tesseract_executable ?? '')} onChange={(e) => update('tesseract_executable', e.target.value)} placeholder="Optional tesseract.exe for room labels and dimensions" />
            <button onClick={() => void browseFile('tesseract_executable', 'Tesseract OCR', ['exe'])}><FolderOpen size={16} /></button>
          </div>
        </label>
        <label>
          Image-to-3D command
          <input value={String(settings.image_to_3d_command ?? '')} onChange={(e) => update('image_to_3d_command', e.target.value)} placeholder="Optional TRELLIS/Hunyuan command with {input} {output}" />
        </label>
        <label>
          Architectural vision endpoint
          <input value={String(settings.vision_endpoint ?? '')} onChange={(e) => update('vision_endpoint', e.target.value)} placeholder="Private multimodal parser endpoint returning strict scene JSON" />
        </label>
        <label>
          Vision model identifier
          <input value={String(settings.vision_model ?? '')} onChange={(e) => update('vision_model', e.target.value)} placeholder="custom-multimodal-parser" />
        </label>
        <label>
          Vision API token
          <input type="password" value={String(settings.vision_token ?? '')} onChange={(e) => update('vision_token', e.target.value)} placeholder="Stored only on this PC" />
        </label>
        <label>
          Image-to-3D endpoint
          <input value={String(settings.ai_endpoint ?? '')} onChange={(e) => update('ai_endpoint', e.target.value)} placeholder="Optional RunPod or private asset-generation endpoint" />
        </label>
        <label>
          Image-to-3D token
          <input type="password" value={String(settings.ai_token ?? '')} onChange={(e) => update('ai_token', e.target.value)} placeholder="Stored only on this PC" />
        </label>
        <label className="checkbox-row">
          <input type="checkbox" checked={Boolean(settings.allow_remote_processing)} onChange={(e) => update('allow_remote_processing', e.target.checked)} />
          Allow this app to upload explicitly selected plans or asset images to the configured private endpoints. Disabled by default.
        </label>
      </div>
      <button className="secondary" onClick={save}><Save size={16} /> {saved ? 'Saved' : 'Save settings'}</button>
    </details>
  );
}
