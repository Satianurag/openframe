import { useState } from 'react';
import type { Settings, Provider } from './types';
import { api, post } from './api';
import { Icon } from './Icon';
import { Modal, ErrorBox } from './ui';
type ConnectionResult = {
  available: boolean;
  detail: string;
  supported_tracking_methods?: string[];
  local_sam2?: { available: boolean; detail: string };
};
export function SettingsPanel({
  settings,
  providers,
  onSaved,
  onClose,
}: {
  settings: Settings;
  providers: Provider[];
  onSaved: (s: Settings) => void;
  onClose: () => void;
}) {
  const writableSettings = new Set([
    'default_provider',
    'comfy_url',
    'comfy_cloud_url',
    'comfy_cli_path',
    'modal_app',
    'modal_environment',
    'modal_function',
    'modal_volume',
    'modal_progress_dict',
  ]);
  const [draft, setDraft] = useState({ ...settings });
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [clearKeys, setClearKeys] = useState<string[]>([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [results, setResults] = useState<Record<string, ConnectionResult>>({});
  const field = (key: string, label: string, placeholder: string, password = false) => (
    <label className="input-label">
      {label}
      <input
        type={password ? 'password' : 'text'}
        autoComplete="off"
        value={password ? secrets[key] || '' : String(draft[key] || '')}
        placeholder={
          password && settings['has_' + key] ? 'Saved key · leave blank to keep' : placeholder
        }
        onChange={(e) =>
          password
            ? setSecrets((s) => ({ ...s, [key]: e.target.value }))
            : setDraft((s) => ({ ...s, [key]: e.target.value }))
        }
      />
      {password && !!settings['has_' + key] && (
        <button
          className="text-button"
          onClick={() =>
            setClearKeys((k) => (k.includes(key) ? k.filter((x) => x !== key) : [...k, key]))
          }
        >
          {clearKeys.includes(key) ? 'Undo key removal' : 'Remove saved key'}
        </button>
      )}
    </label>
  );
  async function save(close = false) {
    setError('');
    setNotice('');
    setBusy('save');
    try {
      const payload = {
        ...Object.fromEntries(Object.entries(draft).filter(([key]) => writableSettings.has(key))),
        ...Object.fromEntries(Object.entries(secrets).filter(([, v]) => v.trim())),
        ...Object.fromEntries(clearKeys.map((k) => [k, ''])),
      };
      const result = await api<Settings>('/settings', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      onSaved(result);
      setNotice('Connection settings saved.');
      if (close) onClose();
      return result;
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setBusy('');
    }
  }
  async function check(id: string) {
    const saved = await save();
    if (!saved) return;
    setBusy(id);
    try {
      const result = await post<ConnectionResult>(`/providers/${id}/check`);
      setResults((r) => ({ ...r, [id]: result }));
      onSaved(saved);
    } catch (e) {
      setResults((r) => ({ ...r, [id]: { available: false, detail: (e as Error).message } }));
    } finally {
      setBusy('');
    }
  }
  return (
    <Modal title="Your compute, your choice" onClose={onClose} wide>
      <div className="modal-content settings-content">
        <p className="muted">Choose local or cloud generation. Credentials stay on your server.</p>
        <label className="input-label">
          Default execution
          <select
            value={draft.default_provider || 'modal'}
            onChange={(e) => setDraft((s) => ({ ...s, default_provider: e.target.value }))}
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <div className="settings-grid">
          {providers.map((p) => (
            <section className="connection-card" key={p.id}>
              <h3>
                <Icon name={p.id === 'local' ? 'monitor' : 'cloud'} />
                {p.name}
              </h3>
              {p.id === 'local' ? (
                <>
                  {field('comfy_url', 'ComfyUI address', 'http://127.0.0.1:8188')}
                  {field('comfy_api_key', 'Bearer token (optional)', 'Token', true)}
                  <p>Run ComfyUI with the required models and OpenFrame nodes installed.</p>
                </>
              ) : p.id === 'modal' ? (
                <>
                  {field('modal_app', 'Modal app', 'openframe-comfy')}
                  {field('modal_environment', 'Environment', 'main')}
                  {field('modal_function', 'Render function', 'render')}
                  <p>
                    Uses the Modal account configured on your server. Model files stay cached on a
                    Modal Volume.
                  </p>
                </>
              ) : (
                <>
                  {field(
                    'comfy_cloud_url',
                    'Comfy Cloud / deployment URL',
                    'https://cloud.comfy.org',
                  )}
                  {field(
                    'comfy_cloud_api_key',
                    'Comfy API key (optional for hosted Cloud)',
                    'Paste key',
                    true,
                  )}
                  {field('comfy_cli_path', 'Comfy CLI path (optional)', 'Automatic discovery')}
                  <p>
                    Hosted Comfy Cloud can use a saved API key or a signed-in Comfy CLI session on
                    this server. API keys take precedence. CLI authentication applies only to
                    cloud.comfy.org.
                  </p>
                  <p>
                    Hosted Cloud runs generation with its available models and native nodes. Source
                    preparation, mask tracking, and final compositing run locally. SAM2 requires a
                    compatible local ComfyUI connection configured here; static and optical-flow
                    masks need no local model runtime. Check the available methods below. Custom
                    deployments must include the workflow’s nodes and checkpoints.
                  </p>
                  <p role="status">
                    {settings.comfy_cloud_auth?.mode === 'api-key' ? (
                      'Saved API key detected. Check the connection to verify access.'
                    ) : settings.comfy_cloud_auth?.mode === 'cli-oauth' ? (
                      'Signed-in Comfy CLI detected. Check the connection to verify access.'
                    ) : settings.comfy_cloud_auth?.cli_installed ? (
                      <>
                        No Cloud credentials detected. Run <code>comfy cloud login</code> on this
                        server, or add an API key.
                      </>
                    ) : (
                      <>
                        Set the Comfy CLI path and run <code>comfy cloud login</code> on this
                        server, or add an API key. Check the connection to verify access.
                      </>
                    )}
                  </p>
                  <a
                    className="text-link"
                    href="https://comfy.org/platform/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open Comfy Developer Platform <Icon name="external" size={14} />
                  </a>
                </>
              )}
              <button className="secondary" disabled={!!busy} onClick={() => check(p.id)}>
                <Icon name="refresh" />
                {busy === p.id ? 'Checking…' : 'Save & check connection'}
              </button>
              {results[p.id] && (
                <div
                  className={`connection-result ${results[p.id].available ? 'connected' : ''}`}
                  role="status"
                >
                  <Icon name={results[p.id].available ? 'check' : 'info'} />
                  <span>
                    {results[p.id].detail}
                    {results[p.id].supported_tracking_methods && (
                      <>
                        <br />
                        Mask tracking:{' '}
                        {results[p.id].supported_tracking_methods
                          ?.map((method) =>
                            method === 'sam2'
                              ? 'SAM2'
                              : method === 'flow'
                                ? 'optical flow'
                                : 'static',
                          )
                          .join(', ')}
                        .
                      </>
                    )}
                    {results[p.id].local_sam2 && (
                      <>
                        <br />
                        Local SAM2:{' '}
                        {results[p.id].local_sam2?.available ? 'detected' : 'not detected'}.
                      </>
                    )}
                  </span>
                </div>
              )}
            </section>
          ))}
        </div>
        {error && <ErrorBox message={error} />}
        <footer className="dialog-actions">
          <span className="muted" role="status">
            {notice}
          </span>
          <button className="secondary" onClick={onClose}>
            Close
          </button>
          <button className="primary" disabled={!!busy} onClick={() => save(true)}>
            Save settings
          </button>
        </footer>
      </div>
    </Modal>
  );
}
