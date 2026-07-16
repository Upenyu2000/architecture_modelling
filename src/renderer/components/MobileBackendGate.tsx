import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CloudCog, RefreshCcw, Server, Settings2, ShieldCheck, WifiOff, X } from 'lucide-react';
import {
  api,
  configureApiConnection,
  testApiConnection,
} from '../lib/api';
import {
  clearMobileBackendConfig,
  isNativeMobile,
  loadMobileBackendConfig,
  normalizeBackendUrl,
  saveMobileBackendConfig,
  type MobileBackendConfig,
} from '../lib/mobile-platform';
import Button from './ui/Button';

interface Props {
  children: ReactNode;
}

type ConnectionState = 'loading' | 'setup' | 'testing' | 'connected' | 'error';

const defaultUrl = import.meta.env.VITE_DREAMHOME_API_URL || '';
const defaultToken = import.meta.env.VITE_DREAMHOME_API_TOKEN || '';

export function MobileBackendGate({ children }: Props) {
  const native = isNativeMobile();
  const [state, setState] = useState<ConnectionState>(native ? 'loading' : 'connected');
  const [baseUrl, setBaseUrl] = useState(defaultUrl);
  const [apiToken, setApiToken] = useState(defaultToken);
  const [error, setError] = useState('');
  const [serverVersion, setServerVersion] = useState('');
  const [showSettings, setShowSettings] = useState(false);

  const displayHost = useMemo(() => {
    try {
      return baseUrl ? new URL(normalizeBackendUrl(baseUrl)).host : 'Rendering server';
    } catch {
      return 'Rendering server';
    }
  }, [baseUrl]);

  const connect = async (config: MobileBackendConfig, persist: boolean) => {
    setState('testing');
    setError('');
    try {
      const normalized = {
        baseUrl: normalizeBackendUrl(config.baseUrl),
        apiToken: config.apiToken.trim(),
      };
      configureApiConnection(normalized.baseUrl, normalized.apiToken);
      const health = await testApiConnection(normalized.baseUrl, normalized.apiToken);
      if (persist) await saveMobileBackendConfig(normalized);
      setBaseUrl(normalized.baseUrl);
      setApiToken(normalized.apiToken);
      setServerVersion(health.version || 'connected');
      setState('connected');
      setShowSettings(false);
    } catch (connectionError) {
      setState('error');
      setError(connectionError instanceof Error ? connectionError.message : String(connectionError));
    }
  };

  useEffect(() => {
    if (!native) return;
    let mounted = true;
    void (async () => {
      const stored = await loadMobileBackendConfig();
      if (!mounted) return;
      if (!stored) {
        setState('setup');
        return;
      }
      setBaseUrl(stored.baseUrl);
      setApiToken(stored.apiToken);
      await connect(stored, false);
    })();
    return () => { mounted = false; };
  }, [native]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void connect({ baseUrl, apiToken }, true);
  };

  const forgetServer = async () => {
    await clearMobileBackendConfig();
    configureApiConnection('http://127.0.0.1:8765', '');
    setBaseUrl(defaultUrl);
    setApiToken(defaultToken);
    setServerVersion('');
    setError('');
    setState('setup');
    setShowSettings(false);
  };

  const verifyCurrentServer = async () => {
    try {
      setState('testing');
      const currentProjects = await api.listProjects();
      setServerVersion(`${serverVersion || 'connected'} · ${currentProjects.length} project${currentProjects.length === 1 ? '' : 's'}`);
      setState('connected');
    } catch (verificationError) {
      setState('error');
      setError(verificationError instanceof Error ? verificationError.message : String(verificationError));
      setShowSettings(true);
    }
  };

  if (!native) return <>{children}</>;

  const setupPanel = (
    <div className="mobile-backend-card">
      <div className="mobile-backend-icon"><CloudCog size={30} /></div>
      <span className="mobile-backend-eyebrow">Android rendering connection</span>
      <h1>Connect Roomify Studio</h1>
      <p>
        The Android app runs the editor and native sharing on your phone. Floor-plan analysis and
        photoreal Blender rendering run on your computer or hosted Roomify API.
      </p>
      <form onSubmit={submit}>
        <label>
          Rendering server address
          <input
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            inputMode="url"
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="http://192.168.1.20:8765"
            required
          />
          <small>Use your computer's local-network address when both devices are on the same Wi-Fi.</small>
        </label>
        <label>
          API token <span>optional on a private network</span>
          <input
            value={apiToken}
            onChange={(event) => setApiToken(event.target.value)}
            type="password"
            autoCapitalize="none"
            autoComplete="off"
            placeholder="DREAMHOME_API_TOKEN"
          />
          <small>Use a token whenever the server is reachable outside your private network.</small>
        </label>
        {error ? <div className="mobile-backend-error"><WifiOff size={17} /> {error}</div> : null}
        <Button fullWidth size="lg" disabled={state === 'testing'}>
          {state === 'testing' ? <RefreshCcw className="spin" size={18} /> : <Server size={18} />}
          {state === 'testing' ? 'Testing server' : 'Connect to server'}
        </Button>
      </form>
      <div className="mobile-backend-security"><ShieldCheck size={17} /> Your server details stay in Android app preferences.</div>
    </div>
  );

  if (state === 'loading') {
    return <main className="mobile-backend-gate"><div className="mobile-backend-loading"><RefreshCcw className="spin" /><span>Loading Roomify Studio</span></div></main>;
  }

  if (state === 'setup' || (state === 'error' && !showSettings)) {
    return <main className="mobile-backend-gate">{setupPanel}</main>;
  }

  return (
    <>
      {children}
      <button className="mobile-server-chip" onClick={() => setShowSettings(true)} aria-label="Open Android server settings">
        <CheckCircle2 size={15} />
        <span>{displayHost}</span>
        <Settings2 size={15} />
      </button>
      {showSettings ? (
        <div className="mobile-backend-modal" role="dialog" aria-modal="true" aria-label="Rendering server settings">
          <div className="mobile-backend-modal-panel">
            <button className="mobile-backend-close" onClick={() => setShowSettings(false)} aria-label="Close server settings"><X size={19} /></button>
            {setupPanel}
            <div className="mobile-backend-secondary-actions">
              <Button variant="secondary" onClick={() => void verifyCurrentServer()} disabled={state === 'testing'}>
                <RefreshCcw size={16} /> Verify current server
              </Button>
              <button className="mobile-forget-server" onClick={() => void forgetServer()}>Forget saved server</button>
            </div>
            {serverVersion ? <small className="mobile-server-version">Server {serverVersion}</small> : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
