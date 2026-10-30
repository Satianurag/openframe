import { useRef, useState } from 'react';
import { api, mediaUrl, post, upload } from '../api';
import { Icon } from '../Icon';
import type { Asset } from '../types';
import { useAppDocument } from './useAppDocument';
import {
  AssetPicker,
  ReferenceMedia,
  useReferenceLibrary,
  useWorkspaceAssets,
  WorkspaceDialog,
} from './engine-apps-shared';
import type { EngineAppProps } from './engine-apps-shared';
import { useTrainedCharacters } from './trainedCharacters';
import type { TrainedCharacter } from './trainedCharacters';
import './character-training.css';

type State = {
  kind: 'trained-character';
  title: string;
  dataset_asset_ids: string[];
  loss_mask_asset_ids?: string[];
  trigger_word: string;
  steps: number;
  resolution: 512 | 768 | 1024;
  rank: 16 | 32;
  learning_rate: number;
  seed: number;
};
const initial: State = {
  kind: 'trained-character',
  title: '',
  dataset_asset_ids: [],
  trigger_word: 'of_character',
  steps: 1200,
  resolution: 1024,
  rank: 32,
  learning_rate: 0.0001,
  seed: 42,
};
const ids = (state: State) => [...(state.dataset_asset_ids || []), ...(state.loss_mask_asset_ids || [])];
const MiB = 1024 ** 2;

export function CharacterTraining({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('soul-id-cast', initial, ids, 'trained-character');
  const state = { ...initial, ...session.state };
  const assets = useWorkspaceAssets(ids(state));
  const library = useReferenceLibrary('soul-id-cast');
  const registry = useTrainedCharacters();
  const files = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(!!new URLSearchParams(location.search).get('document'));
  const [picker, setPicker] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [actionId, setActionId] = useState('');
  const [renaming, setRenaming] = useState<TrainedCharacter | null>(null);
  const [newName, setNewName] = useState('');
  const [removing, setRemoving] = useState<TrainedCharacter | null>(null);
  const [cancelled, setCancelled] = useState<string[]>([]);
  const provider = settings.default_provider || 'local';
  const localTraining = catalog.providers.find((item) => item.id === 'local');
  const trainingReady = provider === 'local' && localTraining?.training_available === true;
  const trainingIssue = provider === 'comfy-cloud'
    ? 'Character training requires your configured Linux CUDA ComfyUI host; direct Comfy Cloud does not provide this runtime.'
    : provider === 'local'
      ? localTraining?.training_detail || 'Configure the isolated training runtime on your Linux CUDA ComfyUI host, then check the Local connection in Settings.'
      : 'This saved connection is unavailable. Select your configured Local ComfyUI explicitly.';
  const totalSize = state.dataset_asset_ids.reduce(
    (sum, id) => sum + (assets.get(id)?.size || 0),
    0,
  );
  const drafts = session.documents.filter((item) => item.state.kind === 'trained-character');

  async function addFiles(selected: File[]) {
    if (!selected.length || busy) return;
    setError('');
    setNotice('');
    setBusy(true);
    const added = [...state.dataset_asset_ids];
    let skipped = 0;
    try {
      if (selected.length > 50 - added.length)
        throw new Error(`Choose at most ${50 - added.length} more photos.`);
      if (selected.some((file) => !file.type.startsWith('image/') || file.size > 32 * MiB))
        throw new Error('Each training photo must be an image no larger than 32 MiB.');
      const known = await Promise.all(
        added.map((id) => assets.get(id) || api<Asset>(`/assets/${id}`)),
      );
      if (
        known.reduce((sum, asset) => sum + (asset.size || 0), 0) +
          selected.reduce((sum, file) => sum + file.size, 0) >
        512 * MiB
      )
        throw new Error('Keep the complete training dataset within 512 MiB.');
      const hashes = new Set(known.map((asset) => asset.sha256).filter(Boolean));
      for (const [index, file] of selected.entries()) {
        setUploadProgress(`Preparing photo ${index + 1} of ${selected.length}`);
        const hash = Array.from(
          new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer())),
        )
          .map((byte) => byte.toString(16).padStart(2, '0'))
          .join('');
        if (hashes.has(hash)) {
          skipped++;
          continue;
        }
        const existing = assets.assets.find(
          (asset) => asset.kind === 'image' && asset.sha256 === hash,
        );
        const asset = existing || (await upload(file));
        assets.add(asset);
        if ((asset.width || 0) < 256 || (asset.height || 0) < 256)
          throw new Error(
            `${asset.name} is smaller than 256 pixels on one side. It remains in your workspace but was not attached for training.`,
          );
        hashes.add(hash);
        added.push(asset.id);
      }
      if (skipped) setNotice(`Skipped ${skipped} duplicate ${skipped === 1 ? 'photo' : 'photos'}.`);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      if (added.join(',') !== state.dataset_asset_ids.join(','))
        await session.updateAndSave({ dataset_asset_ids: added, loss_mask_asset_ids: [] });
      setUploadProgress('');
      setBusy(false);
    }
  }
  async function choose(asset: Asset) {
    setError('');
    if (state.dataset_asset_ids.length >= 50) {
      setError('Use at most 50 training photos.');
      return;
    }
    if (
      asset.kind !== 'image' ||
      (asset.width || 0) < 256 ||
      (asset.height || 0) < 256 ||
      (asset.size || 0) > 32 * MiB
    ) {
      setError('Choose an image of at least 256 × 256 pixels and no larger than 32 MiB.');
      return;
    }
    if (
      state.dataset_asset_ids.includes(asset.id) ||
      (asset.sha256 &&
        state.dataset_asset_ids.some((id) => assets.get(id)?.sha256 === asset.sha256))
    ) {
      setNotice('This photo is already attached. Choose a different photograph.');
      return;
    }
    if (totalSize + (asset.size || 0) > 512 * MiB) {
      setError('Keep the complete dataset within 512 MiB.');
      return;
    }
    assets.add(asset);
    await session.updateAndSave({ dataset_asset_ids: [...state.dataset_asset_ids, asset.id], loss_mask_asset_ids: [] });
  }
  async function train() {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (!trainingReady) throw new Error(trainingIssue);
      if (!state.title.trim()) throw new Error('Give this character a name.');
      if (state.dataset_asset_ids.length < 20 || state.dataset_asset_ids.length > 50)
        throw new Error('Attach 20–50 distinct photos of the same person.');
      if (!/^[a-z][a-z0-9_]{3,31}$/.test(state.trigger_word))
        throw new Error(
          'The trigger must be 4–32 lowercase letters, digits or underscores, starting with a letter.',
        );
      const document = await session.save(true);
      if (!document) throw new Error('Save the training draft before starting.');
      const result = await post<{ character: TrainedCharacter }>(
        `/apps/soul-id-cast/documents/${document.id}/characters`,
        {
          expected_revision: document.revision,
          name: state.title.trim(),
          dataset_asset_ids: state.dataset_asset_ids,
          ...(state.loss_mask_asset_ids?.length ? { loss_mask_asset_ids: state.loss_mask_asset_ids } : {}),
          trigger_token: state.trigger_word,
          steps: state.steps,
          resolution: state.resolution,
          rank: state.rank,
          learning_rate: state.learning_rate,
          seed: state.seed,
          provider,
        },
      );
      registry.replace(result.character);
      void registry.refresh();
      setEditing(false);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function action(character: TrainedCharacter, name: 'cancel' | 'retry') {
    setActionId(character.id);
    setError('');
    try {
      const result = await post<{ id: string }>(`/jobs/${character.job_id}/${name}`);
      if (name === 'cancel') setCancelled((current) => [...current, character.id]);
      else {
        registry.replace(await api<TrainedCharacter>(`/characters/${result.id}`));
        setNotice(
          'A new training run was created from the saved dataset and settings. It starts from the base model, not a saved checkpoint.',
        );
      }
      await registry.refresh();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setActionId('');
    }
  }
  async function rename() {
    if (!renaming || !newName.trim()) return;
    setActionId(renaming.id);
    setError('');
    try {
      registry.replace(
        await api<TrainedCharacter>(`/characters/${renaming.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ name: newName.trim() }),
        }),
      );
      setRenaming(null);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setActionId('');
    }
  }
  async function remove() {
    if (!removing) return;
    setActionId(removing.id);
    setError('');
    try {
      await api(`/characters/${removing.id}`, { method: 'DELETE' });
      registry.remove(removing.id);
      setRemoving(null);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setActionId('');
    }
  }

  return (
    <main className="identity-app training-app">
      {editing ? (
        <>
          <nav className="identity-breadcrumb">
            <button onClick={() => setEditing(false)}>Characters</button>
            <span>/</span>
            <span>{state.title || 'New'}</span>
            <small>{session.saving ? 'Saving…' : session.document ? 'Saved draft' : ''}</small>
          </nav>
          <section className="training-upload-layout">
            <div
              className="training-upload-zone"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                void addFiles(Array.from(event.dataTransfer.files));
              }}
            >
              <div className="training-photos">
                {state.dataset_asset_ids.map((id, index) => (
                  <article key={id}>
                    {assets.get(id) && (
                      <img
                        src={assets.get(id)!.thumbnail_url || mediaUrl(assets.get(id)!)}
                        alt={`Training photograph ${index + 1}`}
                      />
                    )}
                    <button
                      disabled={busy}
                      aria-label={`Remove training photo ${index + 1}`}
                      onClick={() =>
                        session.update({
                          loss_mask_asset_ids: [],
                          dataset_asset_ids: state.dataset_asset_ids.filter(
                            (value) => value !== id,
                          ),
                        })
                      }
                    >
                      <Icon name="close" size={14} />
                    </button>
                  </article>
                ))}
              </div>
              <button
                className="training-upload-button"
                disabled={busy || state.dataset_asset_ids.length >= 50}
                onClick={() => files.current?.click()}
              >
                <Icon name="upload" size={19} />
                {busy ? uploadProgress || 'Preparing…' : 'Upload'}
              </button>
              <p>Upload 20+ photos for best results</p>
              {!!state.loss_mask_asset_ids?.length && (
                <p>{state.loss_mask_asset_ids.length} reviewed head-loss masks attached · outside weight0.1, normalized per image. Changing photos clears their masks.</p>
              )}
              <small>
                {state.dataset_asset_ids.length}/50 photos · {(totalSize / MiB).toFixed(1)} MiB of
                512 MiB
              </small>
              <button
                className="training-workspace-pick"
                disabled={busy || state.dataset_asset_ids.length >= 50}
                onClick={() => setPicker(true)}
              >
                Choose existing workspace photos
              </button>
              <input
                ref={files}
                type="file"
                hidden
                multiple
                accept="image/png,image/jpeg,image/webp"
                onChange={(event) => {
                  const list = Array.from(event.target.files || []);
                  event.target.value = '';
                  void addFiles(list);
                }}
              />
            </div>
            <aside className="training-photo-guide">
              <h2>20+ photos of one person</h2>
              <p>
                Use clear photographs from different angles, with varied expressions and lighting.
              </p>
              <div>
                {library.characters?.slice(0, 4).map((item, index) => (
                  <ReferenceMedia key={index} item={item} />
                ))}
              </div>
              <p>
                Avoid duplicates, group shots, strong filters and covered faces, including masks or
                sunglasses.
              </p>
              <small>Example photographs from the captured Higgsfield reference.</small>
            </aside>
          </section>
          <section className="training-configuration">
            <label>
              Character name
              <input
                maxLength={100}
                value={state.title}
                onChange={(event) => session.update({ title: event.target.value })}
                placeholder="Name your character"
              />
            </label>
            <button
              className="training-advanced-toggle"
              onClick={() => setAdvanced(!advanced)}
              aria-expanded={advanced}
            >
              Training settings
              <Icon name="chevron" size={14} />
            </button>
            {advanced && (
              <div className="training-fields">
                <label>
                  Trigger word
                  <input
                    value={state.trigger_word}
                    maxLength={32}
                    onChange={(event) => session.update({ trigger_word: event.target.value })}
                  />
                  <small>The generation workflow inserts this automatically.</small>
                </label>
                <label>
                  Training steps
                  <input
                    type="number"
                    min={500}
                    max={3000}
                    step={100}
                    value={state.steps}
                    onChange={(event) => session.update({ steps: Number(event.target.value) })}
                  />
                </label>
                <label>
                  Resolution
                  <select
                    value={state.resolution}
                    onChange={(event) =>
                      session.update({
                        resolution: Number(event.target.value) as State['resolution'],
                      })
                    }
                  >
                    {[512, 768, 1024].map((value) => (
                      <option key={value}>{value}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Adapter rank
                  <select
                    value={state.rank}
                    onChange={(event) =>
                      session.update({ rank: Number(event.target.value) as State['rank'] })
                    }
                  >
                    <option>16</option>
                    <option>32</option>
                  </select>
                </label>
                <label>
                  Learning rate
                  <input
                    type="number"
                    min={0.00001}
                    max={0.0002}
                    step={0.00001}
                    value={state.learning_rate}
                    onChange={(event) =>
                      session.update({ learning_rate: Number(event.target.value) })
                    }
                  />
                </label>
                <label>
                  Seed
                  <input
                    type="number"
                    min={0}
                    max={4294967295}
                    step={1}
                    value={state.seed}
                    onChange={(event) => session.update({ seed: Number(event.target.value) })}
                  />
                </label>
              </div>
            )}
            <p>
              {trainingReady ? 'Trains a private FLUX3 Base adapter on the selected GPU host. Weights and checkpoints stay there. ' : `${trainingIssue} `}
              Training is distinct from saving a reference set; resemblance still needs review in
              generated images.
            </p>
            <footer>
              <button onClick={onSettings}>
                <Icon name="cloud" size={15} />
                Connection settings
              </button>
              <button disabled={busy || !session.ready} onClick={() => void session.save(true)}>
                Save draft
              </button>
              <button
                className="ea-lime"
                disabled={
                  busy ||
                  !trainingReady ||
                  !session.ready ||
                  state.dataset_asset_ids.length < 20 ||
                  !state.title.trim()
                }
                onClick={() => void train()}
              >
                {busy ? 'Preparing…' : 'Train character'}
                <Icon name="spark" size={16} />
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
                Train a character from 20 or more photographs.
                <br />
                Use the actual adapter across new images.
              </p>
              <button
                className="ea-lime"
                onClick={() =>
                  void session.newDocument(initial).then((created) => {
                    if (created) setEditing(true);
                  })
                }
              >
                Create character
                <Icon name="plus" size={16} />
              </button>
            </article>
          </section>
          {!!drafts.length && (
            <section className="training-drafts">
              <h2>Training drafts</h2>
              <div>
                {drafts.map((document) => (
                  <button
                    key={document.id}
                    onClick={() =>
                      void session.openDocument(document).then((opened) => {
                        if (opened) setEditing(true);
                      })
                    }
                  >
                    <Icon name="folder" size={18} />
                    <span>
                      {document.state.title || 'Untitled character'}
                      <small>{document.state.dataset_asset_ids?.length || 0} photographs</small>
                    </span>
                    <Icon name="arrow" size={15} />
                  </button>
                ))}
              </div>
            </section>
          )}
          <section className="trained-library">
            <header>
              <h2>Your trained characters</h2>
              <button disabled={registry.loading} onClick={() => void registry.refresh()}>
                <Icon name="refresh" size={14} />
                Refresh
              </button>
            </header>
            {!registry.items.length && (
              <p className="training-empty">
                {registry.loading
                  ? 'Loading characters…'
                  : 'Training runs and ready adapters will appear here. Reference sets remain in their separate tab.'}
              </p>
            )}
            <div className="trained-character-grid">
              {registry.items.map((character) => (
                <article key={character.id}>
                  <div className="trained-character-photo">
                    {character.dataset_asset_ids[0] && (
                      <img
                        src={`/api/assets/${character.dataset_asset_ids[0]}/thumbnail`}
                        alt={`Training photograph for ${character.name}`}
                      />
                    )}
                    <small>Training photograph</small>
                    <span className={`training-status ${character.status}`}>
                      {character.status === 'ready' ? 'Ready' : character.status}
                    </span>
                  </div>
                  <h3>{character.name}</h3>
                  <p>
                    {character.dataset_asset_ids.length} photos · trigger {character.trigger_token}
                  </p>
                  {['queued', 'running'].includes(character.status) && (
                    <>
                      <progress value={character.progress || 0} max={1} />
                      <p>
                        {Math.round((character.progress || 0) * 100)}% ·{' '}
                        {character.stage || 'Queued for training'}
                      </p>
                      <button
                        disabled={actionId === character.id || cancelled.includes(character.id)}
                        onClick={() => void action(character, 'cancel')}
                      >
                        {cancelled.includes(character.id)
                          ? 'Cancellation requested'
                          : 'Cancel training'}
                      </button>
                    </>
                  )}
                  {character.error && (
                    <>
                      <p className="training-error">
                        Training did not complete. Review the diagnostic before retrying.
                      </p>
                      <details className="training-diagnostic">
                        <summary>Full training diagnostic</summary>
                        <pre>{character.error}</pre>
                      </details>
                    </>
                  )}
                  {['failed', 'cancelled'].includes(character.status) && (
                    <>
                      <button
                        disabled={actionId === character.id}
                        onClick={() => void action(character, 'retry')}
                      >
                        Retry training
                      </button>
                      <small>
                        Starts a new run from the saved dataset; does not resume a checkpoint.
                      </small>
                    </>
                  )}
                  {character.status === 'ready' && (
                    <a className="ea-lime" href={`/soul?trained_character=${character.id}`}>
                      Use in Image Studio
                      <Icon name="arrow" size={15} />
                    </a>
                  )}
                  <div className="trained-character-actions">
                    <a href={`/api/characters/${character.id}/manifest`} download>
                      Manifest
                    </a>
                    <button
                      onClick={() => {
                        setRenaming(character);
                        setNewName(character.name);
                      }}
                    >
                      Rename
                    </button>
                    {!['queued', 'running'].includes(character.status) && (
                      <button onClick={() => setRemoving(character)}>Remove</button>
                    )}
                  </div>
                </article>
              ))}
            </div>
            {registry.items.length < registry.total && (
              <button disabled={registry.loading} onClick={() => void registry.loadMore()}>
                Load more characters
              </button>
            )}
          </section>
        </>
      )}
      {(error || session.error || assets.error || registry.error) && (
        <p className="training-error" role="alert">
          {error || session.error || assets.error || registry.error}
        </p>
      )}
      {notice && <p className="training-notice">{notice}</p>}
      {picker && (
        <AssetPicker
          title="Choose training photo"
          kind="image"
          assets={assets.assets}
          onAdded={assets.add}
          onSelect={(asset) => void choose(asset)}
          onClose={() => setPicker(false)}
        />
      )}
      {renaming && (
        <WorkspaceDialog title="Rename character" onClose={() => setRenaming(null)}>
          <label className="ea-field">
            Name
            <input
              autoFocus
              maxLength={100}
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
            />
          </label>
          <button
            className="ea-lime"
            disabled={!newName.trim() || !!actionId}
            onClick={() => void rename()}
          >
            Save name
          </button>
          {error && <p className="training-error">{error}</p>}
        </WorkspaceDialog>
      )}
      {removing && (
        <WorkspaceDialog
          title={`Remove ${removing.name} from the library?`}
          onClose={() => setRemoving(null)}
        >
          <p>
            The training job, photographs and GPU-host adapter files are retained. Saved generations
            may prevent removing the registry entry.
          </p>
          <button className="ea-lime" disabled={!!actionId} onClick={() => void remove()}>
            Remove library entry
          </button>
          {error && <p className="training-error">{error}</p>}
        </WorkspaceDialog>
      )}
    </main>
  );
}
