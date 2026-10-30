import { useState } from 'react';
import { mediaUrl, post, upload } from '../api';
import { Icon } from '../Icon';
import type { Job } from '../types';
import { useAppDocument } from './useAppDocument';
import { renderRequest, renderSize } from './renderRequest';
import {
  AssetPicker,
  exportDraft,
  ReferenceMedia,
  ResultDialog,
  useReferenceLibrary,
  useWorkspaceAssets,
  WorkspaceHistory,
} from './engine-apps-shared';
import type { EngineAppProps } from './engine-apps-shared';
import { CharacterTraining } from './CharacterTraining';
import './root-apps.css';

type CharacterState = {
  model_id?: string;
  kind: 'reference-set';
  title: string;
  reference_asset_ids: string[];
  prompt: string;
  ratio: string;
  batch: number;
};
const initial: CharacterState = {
  model_id: 'flux3-klein',
  kind: 'reference-set',
  title: '',
  reference_asset_ids: [],
  prompt:
    'Create a character reference sheet showing the same adult character from front, three-quarter and side views, consistent face, hairstyle and outfit, neutral studio background, no text.',
  ratio: '3:4',
  batch: 1,
};
const ids = (state: CharacterState) => state.reference_asset_ids;
export function SoulIdentity(props: EngineAppProps) {
  const query = new URLSearchParams(location.search);
  const references =
    query.get('mode') === 'references' || (!query.has('mode') && query.has('document'));
  return (
    <>
      <nav className="identity-mode-nav" aria-label="Character method">
        <a className={!references ? 'active' : ''} href="/soul-id?mode=training">
          Trained characters
        </a>
        <a className={references ? 'active' : ''} href="/soul-id?mode=references">
          Reference sets
        </a>
      </nav>
      {references ? <ReferenceCharacters {...props} /> : <CharacterTraining {...props} />}
    </>
  );
}
function ReferenceCharacters({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('soul-id-cast', initial, ids, 'reference-set'),
    { state, update } = session,
    assets = useWorkspaceAssets(ids(state)),
    library = useReferenceLibrary('soul-id-cast');
  const [editing, setEditing] = useState(!!new URLSearchParams(location.search).get('document')),
    [picker, setPicker] = useState(false),
    [view, setView] = useState<'Characters' | 'History'>('Characters'),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [selected, setSelected] = useState<Job | null>(null);
  const model = catalog.models.find((item) => item.id === (state.model_id || 'flux-klein-4b')),
    provider = settings.default_provider || 'local';
  async function save() {
    setError('');
    if (!state.title.trim()) {
      setError('Give this character a name.');
      return null;
    }
    if (!state.reference_asset_ids.length) {
      setError('Add at least one character image.');
      return null;
    }
    return session.save(true);
  }
  async function generate() {
    if (!model || busy) return;
    setBusy(true);
    setError('');
    try {
      if (provider === 'comfy-cloud')
        throw new Error('Choose a supported local ComfyUI connection for this reference-image workflow.');
      if (!state.prompt.trim()) throw new Error('Describe the character image to create.');
      const record = await save();
      if (!record) return;
      const request = renderRequest(model, {
        effect_id: 'edit-image',
        provider,
        prompt: `Use the reference photographs for the same character. Keep the face, hair, proportions and distinctive features consistent. ${state.prompt}`,
        ...renderSize(model, state.ratio, 1024),
        frames: 1,
        fps: 1,
        source_asset_id: state.reference_asset_ids[0],
        reference_asset_ids: state.reference_asset_ids.slice(1),
        batch_size: state.batch,
      });
      const job = await post<Job>(`/apps/soul-id-cast/documents/${record.id}/jobs`, {
        expected_revision: record.revision,
        operation: 'edit-image',
        request,
      });
      setSelected(job);
      await session.refreshJobs();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function addFiles(files: File[]) {
    if (!files.length) return;
    setBusy(true);
    setError('');
    const references = [...state.reference_asset_ids];
    try {
      for (const file of files.slice(0, 4 - references.length)) {
        if (!file.type.startsWith('image/'))
          throw new Error('Choose image files for the character.');
        const asset = await upload(file);
        assets.add(asset);
        references.push(asset.id);
      }
      update({ reference_asset_ids: references });
    } catch (reason) {
      update({ reference_asset_ids: references });
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function useCharacter() {
    const record = await save();
    if (record) location.href = `/soul?character=${encodeURIComponent(record.id)}`;
  }
  return (
    <main className="identity-app">
      <nav className="soul-view-nav">
        <button
          className={view === 'Characters' ? 'active' : ''}
          onClick={() => setView('Characters')}
        >
          Characters
        </button>
        <button className={view === 'History' ? 'active' : ''} onClick={() => setView('History')}>
          History
        </button>
        <span />
        <button onClick={onSettings}>
          <Icon name="cloud" size={14} />
          {provider === 'local' ? 'Local ComfyUI' : provider === 'comfy-cloud' ? 'Comfy Cloud' : 'Saved connection unavailable'}
        </button>
      </nav>
      {view === 'History' ? (
        <WorkspaceHistory
          jobs={session.jobs.filter((job) => job.request.effect_id !== 'train-identity')}
          total={session.jobTotal}
          onSelect={setSelected}
          onMore={session.loadMoreJobs}
        />
      ) : editing ? (
        <>
          <nav className="identity-breadcrumb">
            <button onClick={() => setEditing(false)}>Characters</button>
            <span>/</span>
            <span>{state.title || 'New'}</span>
            <small>{session.saving ? 'Saving…' : session.document ? 'Saved' : ''}</small>
          </nav>
          <section className="identity-editor">
            <div
              className="identity-drop"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                void addFiles(Array.from(event.dataTransfer.files));
              }}
            >
              {state.reference_asset_ids.length ? (
                <div className="identity-reference-grid">
                  {state.reference_asset_ids.map((id, index) => (
                    <article key={id}>
                      {assets.get(id) && (
                        <img
                          src={mediaUrl(assets.get(id)!)}
                          alt={`Character reference ${index + 1}`}
                        />
                      )}
                      <button
                        aria-label={`Remove reference ${index + 1}`}
                        onClick={() =>
                          update({
                            reference_asset_ids: state.reference_asset_ids.filter(
                              (value) => value !== id,
                            ),
                          })
                        }
                      >
                        <Icon name="close" size={16} />
                      </button>
                    </article>
                  ))}
                </div>
              ) : null}
              <button
                className="ea-lime"
                disabled={busy || state.reference_asset_ids.length >= 4}
                onClick={() => setPicker(true)}
              >
                {busy ? 'Uploading…' : 'Upload'}
                <Icon name="image" size={16} />
              </button>
              <p>
                {state.reference_asset_ids.length}/4 reference images · choose files or drop images
                here
              </p>
            </div>
            <div className="identity-guide">
              <div>
                <i>✓</i>
                <p>
                  One character, clear face,
                  <br />
                  different angles and consistent appearance.
                </p>
              </div>
              <div className="identity-examples">
                {library.characters?.slice(0, 4).map((item, index) => (
                  <ReferenceMedia key={index} item={item} />
                ))}
              </div>
            </div>
            <div className="identity-fields">
              <label>
                Character name
                <input
                  value={state.title}
                  maxLength={120}
                  onChange={(event) => update({ title: event.target.value })}
                  placeholder="Name your character"
                />
              </label>
              <label>
                Next image
                <textarea
                  value={state.prompt}
                  onChange={(event) => update({ prompt: event.target.value })}
                />
              </label>
              <div>
                <label>
                  Aspect ratio
                  <select
                    value={state.ratio}
                    onChange={(event) => update({ ratio: event.target.value })}
                  >
                    {['1:1', '3:4', '4:3', '9:16', '16:9'].map((value) => (
                      <option key={value}>{value}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Variations
                  <select
                    value={state.batch}
                    onChange={(event) => update({ batch: Number(event.target.value) })}
                  >
                    {[1, 2, 3, 4].map((value) => (
                      <option key={value}>{value}</option>
                    ))}
                  </select>
                </label>
              </div>
              <p className="ea-muted">
                Uses {model?.name || 'the saved model'} reference conditioning. No model training;
                identity consistency varies with the images and prompt.
              </p>
            </div>
            <footer>
              <button onClick={() => void save()}>Save character</button>
              <button
                onClick={() =>
                  exportDraft(state, `${state.title || 'character'}-reference-set.json`)
                }
              >
                Export references manifest
              </button>
              <button
                disabled={!session.ready || busy || !state.reference_asset_ids.length}
                onClick={() => void useCharacter()}
              >
                Use in Image Studio
              </button>
              <button
                className="ea-lime"
                disabled={!session.ready || !model || busy || !state.reference_asset_ids.length}
                onClick={() => void generate()}
              >
                {busy ? 'Preparing…' : 'Generate character image'}
              </button>
            </footer>
          </section>
        </>
      ) : (
        <>
          <section className="identity-hero">
            <div className="identity-hero-images">
              {library.hero?.slice(0, 4).map((item, index) => (
                <ReferenceMedia key={index} item={item} />
              ))}
            </div>
            <article>
              <h1>Make your own character</h1>
              <p>
                Build a reference set from multiple angles.
                <br />
                Reuse the same character across new images.
              </p>
              <button
                className="ea-lime"
                onClick={() => {
                  void session.newDocument().then((created) => {
                    if (created) setEditing(true);
                  });
                }}
              >
                Create character <Icon name="plus" size={16} />
              </button>
            </article>
          </section>
          <section className="identity-saved">
            {session.documents
              .filter((record) => record.state.reference_asset_ids?.length)
              .map((record) => (
                <button
                  key={record.id}
                  onClick={() =>
                    void session.openDocument(record).then((opened) => {
                      if (opened) setEditing(true);
                    })
                  }
                >
                  <img
                    src={`/api/assets/${record.state.reference_asset_ids[0]}/file`}
                    alt={record.title}
                  />
                  <strong>{record.title}</strong>
                  <small>{record.state.reference_asset_ids.length} references</small>
                </button>
              ))}
          </section>
        </>
      )}
      {(error || session.error || assets.error) && (
        <p role="alert" className="ea-error identity-error">
          {error || session.error || assets.error}
        </p>
      )}
      {picker && (
        <AssetPicker
          title="Character reference images"
          kind="image"
          assets={assets.assets}
          onAdded={assets.add}
          onClose={() => setPicker(false)}
          onSelect={(asset) =>
            update({
              reference_asset_ids: [...new Set([...state.reference_asset_ids, asset.id])].slice(
                0,
                4,
              ),
            })
          }
        />
      )}
      {selected && (
        <ResultDialog
          job={session.jobs.find((job) => job.id === selected.id) || selected}
          onClose={() => setSelected(null)}
          onRefresh={() => void session.refreshJobs()}
          useKind="image"
          useLabel="Use as reference"
          onUse={(asset) => {
            assets.add(asset);
            update({
              reference_asset_ids: [
                asset.id,
                ...state.reference_asset_ids.filter((id) => id !== asset.id),
              ].slice(0, 4),
            });
          }}
        />
      )}
    </main>
  );
}
