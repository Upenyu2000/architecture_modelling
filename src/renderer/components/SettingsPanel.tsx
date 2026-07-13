import { useEffect, useState } from 'react';
import { Cpu, FolderOpen, Save } from 'lucide-react';
import { api } from '../lib/api';

export function SettingsPanel() {
  const [settings, setSettings] = useState<Record<string, string | boolean>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.getSettings().then(setSettings).catch(() => undefined); }, []);

  const update = (key: string, value: string | boolean) => setSettings((current) => ({ ...current, [key]: value }));
  const browseBlender = async () => {
    const selected = await window.desktop?.selectFile([{ name: 'Blender', extensions: ['exe'] }]);
    if (selected) update('blender_executable', selected);
  };
  const save = async () => {
    setSettings(await api.saveSettings(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <details className="settings-panel">
      <summary><Cpu size={17} /> AI and render settings</summary>
      <div className="settings-grid">
        <label>
          Blender executable
          <div className="input-with-button">
            <input value={String(settings.blender_executable ?? '')} onChange={(e) => update('blender_executable', e.target.value)} placeholder="Auto-detect or choose blender.exe" />
            <button onClick={browseBlender}><FolderOpen size={16} /></button>
          </div>
        </label>
        <label>
          Image-to-3D command
          <input value={String(settings.image_to_3d_command ?? '')} onChange={(e) => update('image_to_3d_command', e.target.value)} placeholder="Optional TRELLIS/Hunyuan command with {input} {output}" />
        </label>
        <label>
          Remote AI endpoint
          <input value={String(settings.ai_endpoint ?? '')} onChange={(e) => update('ai_endpoint', e.target.value)} placeholder="Optional RunPod or private API endpoint" />
        </label>
        <label>
          API token
          <input type="password" value={String(settings.ai_token ?? '')} onChange={(e) => update('ai_token', e.target.value)} placeholder="Stored only on this PC" />
        </label>
        <label className="checkbox-row">
          <input type="checkbox" checked={Boolean(settings.allow_remote_processing)} onChange={(e) => update('allow_remote_processing', e.target.checked)} />
          Allow this app to upload selected asset images to the configured private endpoint
        </label>
      </div>
      <button className="secondary" onClick={save}><Save size={16} /> {saved ? 'Saved' : 'Save settings'}</button>
    </details>
  );
}
