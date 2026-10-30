import { useEffect, useRef, useState } from 'react';
import { api, mediaUrl, upload } from '../api';
import type { Asset, Catalog, Settings } from '../types';
import type { AppDocument } from './registry';
import { SequencePlanner, sequenceStatus } from './SequencePlanner';
import type { Sequence } from './SequencePlanner';
import { Icon } from '../Icon';
import { AnchoredPopover } from '../Popovers';
import { useAppDocument } from './useAppDocument';
import { importReference, useReferenceLibrary } from './engine-apps-shared';
import './content-factory.css';

type FactoryState = {
  prompt: string;
  length: number;
  episodes: number;
  mode: 'claude' | 'local';
  tab: 'explore' | 'generations';
  reference_url: string | null;
  reference_asset_id: string | null;
  attachment_asset_ids: string[];
  style_id: string | null;
};
type Style = { id: string; title?: string; video: string; poster?: string; source_url?: string };
const initial: FactoryState = {
  prompt: '',
  length: 30,
  episodes: 1,
  mode: 'local',
  tab: 'explore',
  reference_url: null,
  reference_asset_id: null,
  attachment_asset_ids: [],
  style_id: null,
};
const referencedAssets = (state: FactoryState) =>
  [state.reference_asset_id, ...state.attachment_asset_ids].filter((id): id is string => !!id);

export function ContentFactory({ catalog, settings }: { catalog: Catalog; settings: Settings }) {
  const session = useAppDocument('content-factory', initial, referencedAssets);
  const { state, update } = session;
  const [planDocument, setPlanDocument] = useState<AppDocument<Record<string, unknown>> | null>(
    null,
  );
  const [selectedSequenceId, setSelectedSequenceId] = useState<string>();
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [sequenceTotal, setSequenceTotal] = useState(0);
  const [sequenceLimit, setSequenceLimit] = useState(100);
  const [sequenceError, setSequenceError] = useState('');
  const library = useReferenceLibrary('content-factory');
  const styles = (library.styles || []) as Style[];
  const linkPreview = library.link_preview || '';
  const [assets, setAssets] = useState<Asset[]>([]);
  const [menu, setMenu] = useState<'length' | 'episodes' | 'reference' | null>(null);
  const [dialog, setDialog] = useState<'link' | 'media' | 'capability' | null>(null);
  const [referenceLink, setReferenceLink] = useState('');
  const [message, setMessage] = useState('');
  const [uploading, setUploading] = useState(false);
  const [mediaRole, setMediaRole] = useState<'reference' | 'attachment'>('reference');
  const [stylePreview, setStylePreview] = useState<Style | null>(null);
  const [importingStyle, setImportingStyle] = useState<string | null>(null);
  const styleImportPending = useRef(false);
  const lengthButton = useRef<HTMLButtonElement>(null);
  const episodeButton = useRef<HTMLButtonElement>(null);
  const referenceButton = useRef<HTMLButtonElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const modal = useRef<HTMLDialogElement>(null);
  const reference = assets.find((asset) => asset.id === state.reference_asset_id);
  const selectedStyle = styles.find((style) => style.id === state.style_id);
  const operation = session.application?.operations.find(
    (item) => item.id === (state.mode === 'claude' ? 'claude-export' : 'generate-series'),
  );

  useEffect(() => {
    api<{ items: Asset[] }>('/assets?limit=100')
      .then((result) => setAssets(result.items))
      .catch(() => {});
  }, []);
  useEffect(() => {
    const element = modal.current;
    if (dialog || stylePreview) element?.showModal();
    return () => element?.close();
  }, [dialog, stylePreview]);
  useEffect(() => {
    if (!state.reference_asset_id || reference) return;
    api<Asset>(`/assets/${state.reference_asset_id}`)
      .then((asset) => setAssets((current) => [...current, asset]))
      .catch(() => {});
  }, [state.reference_asset_id, reference]);

  const hasActiveSequence = sequences.some((item) => ['queued', 'running'].includes(item.status));
  useEffect(() => {
    if (state.tab !== 'generations') return;
    let live = true,
      loading = false;
    const refresh = async () => {
      if (loading) return;
      loading = true;
      try {
        const pages = await Promise.all(
          Array.from({ length: Math.ceil(sequenceLimit / 500) }, (_, index) =>
            api<{ items: Sequence[]; total: number }>(
              `/apps/content-factory/sequences?limit=${Math.min(500, sequenceLimit - index * 500)}&offset=${index * 500}`,
            ),
          ),
        );
        if (live) {
          setSequences(pages.flatMap((page) => page.items));
          setSequenceTotal(pages[0]?.total || 0);
          setSequenceError('');
        }
      } catch (reason) {
        if (live) setSequenceError((reason as Error).message);
      } finally {
        loading = false;
      }
    };
    void refresh();
    const timer = setInterval(() => void refresh(), hasActiveSequence ? 2000 : 10000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [state.tab, sequenceLimit, hasActiveSequence]);
  async function openSequence(sequence: Sequence) {
    try {
      const document = await api<AppDocument<FactoryState>>(
        `/apps/content-factory/documents/${sequence.document_id}`,
      );
      if (await session.openDocument(document)) {
        setSelectedSequenceId(sequence.id);
        setPlanDocument(document);
      }
    } catch (reason) {
      setSequenceError((reason as Error).message);
    }
  }

  function chooseAsset(asset: Asset) {
    if (mediaRole === 'reference')
      update({ reference_asset_id: asset.id, reference_url: null, style_id: null });
    else update({ attachment_asset_ids: [...new Set([...state.attachment_asset_ids, asset.id])] });
    setDialog(null);
  }
  async function chooseStyle(style: Style) {
    if (styleImportPending.current || !session.ready) return;
    styleImportPending.current = true;
    setImportingStyle(style.id);
    setMessage('');
    try {
      const asset = state.style_id === style.id && reference?.kind === 'image'
        ? reference
        : await importReference({ ...style, title: style.title || 'Style reference' }, 'image');
      setAssets((current) => [asset, ...current.filter((item) => item.id !== asset.id)]);
      const saved = await session.updateAndSave({
        style_id: style.id,
        reference_asset_id: asset.id,
        reference_url: null,
      });
      if (!saved) throw new Error('The reference was loaded but could not be saved. Check the connection and retry.');
      setStylePreview(null);
      setDialog(null);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (reason) {
      setMessage((reason as Error).message);
      setStylePreview(null);
      setDialog('capability');
    } finally {
      styleImportPending.current = false;
      setImportingStyle(null);
    }
  }
  async function uploadFiles(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    setMessage('');
    try {
      const uploaded: Asset[] = [];
      for (const file of Array.from(files)) uploaded.push(await upload(file));
      setAssets((current) => [
        ...uploaded,
        ...current.filter((asset) => !uploaded.some((item) => item.id === asset.id)),
      ]);
      if (mediaRole === 'reference') chooseAsset(uploaded[0]);
      else
        update({
          attachment_asset_ids: [
            ...new Set([...state.attachment_asset_ids, ...uploaded.map((asset) => asset.id)]),
          ],
        });
    } catch (reason) {
      setMessage((reason as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }
  async function generate() {
    const document = await session.save(true);
    if (!document) {
      setMessage(session.error || 'Your brief could not be saved.');
      setDialog('capability');
      return;
    }
    if (state.mode === 'local') {
      setPlanDocument(document);
      return;
    }
    setMessage(
      operation?.reason ||
        'This app’s episode-generation handler is not connected. Your brief can be saved, but no render has been submitted.',
    );
    setDialog('capability');
  }
  function saveLink() {
    try {
      const url = new URL(referenceLink);
      if (!['https:', 'http:'].includes(url.protocol)) throw Error();
      update({ reference_url: url.href, reference_asset_id: null, style_id: null });
      setDialog(null);
      setMessage('');
    } catch {
      setMessage('Enter a valid TikTok or Instagram URL.');
    }
  }
  const closeDialog = () => {
    setDialog(null);
    setStylePreview(null);
    setMessage('');
  };

  return (
    <main className="content-factory">
      {planDocument && (
        <SequencePlanner
          appId="content-factory"
          document={planDocument}
          initialPrompt={state.prompt}
          initialStyle={selectedStyle?.title || ''}
          initialSequenceId={selectedSequenceId}
          initialRequest={
            reference?.kind === 'image'
              ? { source_asset_id: reference.id, effect_id: 'image-to-video' }
              : undefined
          }
          targetDuration={state.length}
          episodeCount={state.episodes}
          catalog={catalog}
          settings={settings}
          onClose={() => {
            setPlanDocument(null);
            setSelectedSequenceId(undefined);
          }}
          onPrepareDocument={async (ids) => {
            const doc = await session.updateAndSave({
              attachment_asset_ids: [...new Set([...state.attachment_asset_ids, ...ids])],
            });
            if (!doc) throw new Error('Could not save the attached media.');
            setPlanDocument(doc);
            return doc;
          }}
          onCreated={(sequence) => {
            setSequences((items) => [sequence, ...items.filter((item) => item.id !== sequence.id)]);
            if (sequence.status !== 'draft') update({ tab: 'generations' });
            void session.refreshJobs();
          }}
        />
      )}
      <div className="cf-view-tabs" role="tablist" aria-label="Content Factory views">
        <button
          role="tab"
          aria-selected={state.tab === 'explore'}
          onClick={() => update({ tab: 'explore' })}
        >
          <Icon name="spark" size={15} />
          Explore
        </button>
        <button
          role="tab"
          aria-selected={state.tab === 'generations'}
          onClick={() => update({ tab: 'generations' })}
        >
          <Icon name="copy" size={15} />
          My generations
        </button>
      </div>
      {session.error && (
        <p className="cf-connection-error" role="alert">
          {session.error}
        </p>
      )}
      {state.tab === 'explore' ? (
        <>
          <section className={`cf-hero ${state.mode === 'claude' ? 'cf-claude' : ''}`}>
            <div className="cf-mode-tabs" role="tablist" aria-label="Generate with">
              <button
                role="tab"
                aria-selected={state.mode === 'claude'}
                onClick={() => update({ mode: 'claude' })}
              >
                <span className="cf-claude-mark">✳</span>Generate in Claude
              </button>
              <button
                role="tab"
                aria-selected={state.mode === 'local'}
                onClick={() => update({ mode: 'local' })}
              >
                <Icon name="code" size={15} />
                Generate here
              </button>
            </div>
            <h1>
              {state.mode === 'claude' ? (
                <>
                  Generate viral faceless short videos
                  <br />
                  <span>
                    Inside <i className="cf-claude-mark">✳</i> Claude with a connected MCP
                  </span>
                </>
              ) : (
                'Generate viral short videos'
              )}
            </h1>
            <div className="cf-composer">
              <button
                ref={referenceButton}
                className="cf-reference"
                aria-label="Add reference"
                onClick={() => setMenu(menu === 'reference' ? null : 'reference')}
              >
                <span className="cf-reference-tile">
                  {reference?.thumbnail_url ? (
                    <img src={reference.thumbnail_url} alt="Selected reference" />
                  ) : selectedStyle?.poster ? (
                    <img src={selectedStyle.poster} alt="Selected style" />
                  ) : (
                    <Icon name={state.reference_url ? 'external' : 'image'} size={16} />
                  )}
                </span>
                <span>
                  {reference || selectedStyle || state.reference_url
                    ? 'Change reference'
                    : 'Add reference'}
                </span>
              </button>
              <div className="cf-prompt-column">
                <label htmlFor="factory-prompt">Make a video about…</label>
                <textarea
                  id="factory-prompt"
                  aria-label="Make a video about…"
                  rows={1}
                  placeholder="What if the Moon had a city"
                  value={state.prompt}
                  onChange={(event) => update({ prompt: event.target.value })}
                />
                <div className="cf-composer-tools">
                  <button
                    className="cf-add"
                    aria-label="Add images or videos"
                    onClick={() => {
                      setMediaRole('attachment');
                      setDialog('media');
                    }}
                  >
                    <Icon name="plus" size={14} />
                  </button>
                  <button
                    ref={lengthButton}
                    aria-label={`Length: ${state.length} sec`}
                    onClick={() => setMenu(menu === 'length' ? null : 'length')}
                  >
                    <Icon name="clock" size={12} />
                    {state.length} sec
                  </button>
                  <button
                    ref={episodeButton}
                    aria-label={`Episodes: ${state.episodes} ${state.episodes === 1 ? 'episode' : 'episodes'}`}
                    onClick={() => setMenu(menu === 'episodes' ? null : 'episodes')}
                  >
                    <Icon name="square" size={11} />
                    {state.episodes} {state.episodes === 1 ? 'episode' : 'episodes'}
                  </button>
                </div>
              </div>
              <button
                className={`cf-generate ${state.mode === 'claude' ? 'cf-generate-claude' : ''}`}
                onClick={generate}
                disabled={!session.ready || uploading || !!importingStyle}
              >
                {state.mode === 'claude' ? (
                  <>
                    Generate
                    <br />
                    in Claude
                  </>
                ) : (
                  <>
                    Generate
                    <small>
                      {state.mode === 'local'
                        ? 'Review plan'
                        : operation?.available
                          ? 'Ready'
                          : 'Setup required'}
                    </small>
                  </>
                )}
              </button>
            </div>
            <button
              className="cf-execution-info"
              onClick={() => {
                setMessage(
                  operation?.reason ||
                    'Episode planning, narration and assembly require a connected Content Factory operation. No credits are estimated and no video is submitted until that operation is available.',
                );
                setDialog('capability');
              }}
            >
              <Icon name={state.mode === 'claude' ? 'code' : 'info'} size={13} />
              {state.mode === 'claude' ? 'Connect an MCP to generate' : 'How does generation work?'}
            </button>
            {selectedStyle && (
              <p className="cf-reference-note">
                {reference?.kind === 'image'
                  ? 'The selected preview image is attached to your shot plan as the starting reference. You can edit the style notes before generating.'
                  : 'Select Use as reference to attach this preset’s preview image to your shot plan.'}
              </p>
            )}
            {(reference?.kind === 'video' || (state.reference_url && !selectedStyle)) && (
              <p className="cf-reference-note">
                Reference saved. Describe its style in the shot plan; videos and links are not
                automatically analyzed.{' '}
                {state.reference_url && <>Remove the link before planning or rendering.</>}
              </p>
            )}
            {!!state.attachment_asset_ids.length && (
              <div className="cf-attachments">
                {state.attachment_asset_ids.map((id) => (
                  <button
                    key={id}
                    onClick={() =>
                      update({
                        attachment_asset_ids: state.attachment_asset_ids.filter(
                          (item) => item !== id,
                        ),
                      })
                    }
                  >
                    {assets.find((asset) => asset.id === id)?.name || 'Attached media'}
                    <Icon name="close" size={12} />
                  </button>
                ))}
              </div>
            )}
          </section>
          <section className="cf-trending">
            <h2>Pick a trending style to start from</h2>
            <div className="cf-style-grid">
              {styles.map((style) => (
                <article className="cf-style-card" key={style.id}>
                  <button
                    className="cf-style-preview"
                    aria-label={style.title || 'Preview style'}
                    onClick={() => setStylePreview(style)}
                  >
                    <video
                      src={style.video}
                      poster={style.poster}
                      muted
                      loop
                      playsInline
                      preload="metadata"
                      onMouseEnter={(event) => void event.currentTarget.play().catch(() => {})}
                      onMouseLeave={(event) => event.currentTarget.pause()}
                    />
                  </button>
                  <button
                    className="cf-use-style"
                    disabled={!!importingStyle || !session.ready}
                    onClick={() => void chooseStyle(style)}
                  >
                    {importingStyle === style.id ? 'Loading reference…' : 'Use as reference'}
                  </button>
                </article>
              ))}
            </div>
            {!styles.length && (
              <p className="cf-media-status">
                Reference previews are not available in this workspace.
              </p>
            )}
          </section>
        </>
      ) : (
        <section className="cf-generations">
          <h1>My generations</h1>
          {sequenceError && <p role="alert">{sequenceError}</p>}
          {!!sequences.length && (
            <>
              <div className="cf-job-grid">
                {sequences.map((sequence) => (
                  <article key={sequence.id}>
                    <strong>{sequence.episodes[0]?.title || 'Sequence'}</strong>
                    <span>
                      {sequenceStatus(sequence)}
                      {['queued', 'running'].includes(sequence.status)
                        ? ` · ${Math.round(sequence.progress * 100)}%`
                        : ''}
                    </span>
                    {sequence.episodes.map((episode, index) =>
                      episode.output ? (
                        <div key={episode.id || index}>
                          <video src={mediaUrl(episode.output)} controls playsInline />
                          <a href={mediaUrl(episode.output)} download={episode.output.name}>
                            {episode.title} · Download episode
                          </a>
                        </div>
                      ) : null,
                    )}
                    {sequence.error && <p role="alert">{sequence.error}</p>}
                    <button onClick={() => void openSequence(sequence)}>Open plan</button>
                  </article>
                ))}
              </div>
              <p>
                {sequences.length} of {sequenceTotal} saved sequences loaded
              </p>
              {sequences.length < sequenceTotal && (
                <button onClick={() => setSequenceLimit((limit) => limit + 100)}>Load more</button>
              )}
            </>
          )}
          {session.jobs.length ? (
            <details>
              <summary>Individual shots and narration ({session.jobs.length})</summary>
              <div className="cf-job-grid">
                {session.jobs.map((job) => (
                  <article key={job.id}>
                    <strong>{job.request.prompt || 'Episode'}</strong>
                    <span>{job.status}</span>
                    {job.outputs
                      .filter((output) => output.role !== 'mask')
                      .map((output) =>
                        output.kind === 'audio' ? (
                          <audio key={output.id} src={mediaUrl(output)} controls />
                        ) : output.kind === 'image' ? (
                          <img key={output.id} src={mediaUrl(output)} alt="Generated image" />
                        ) : (
                          <video key={output.id} src={mediaUrl(output)} controls playsInline />
                        ),
                      )}
                    {job.error && <p role="alert">{job.error}</p>}
                  </article>
                ))}
              </div>
              {session.jobs.length < session.jobTotal && (
                <button onClick={session.loadMoreJobs}>Load more shots</button>
              )}
            </details>
          ) : !sequences.length ? (
            <p>No generations yet. Your Content Factory episodes will appear here.</p>
          ) : null}
        </section>
      )}
      <span className="cf-save-status" aria-live="polite">
        {session.saving ? 'Saving…' : session.document ? 'Saved' : ''}
      </span>
      {menu && (
        <AnchoredPopover
          anchor={
            menu === 'length'
              ? lengthButton.current
              : menu === 'episodes'
                ? episodeButton.current
                : referenceButton.current
          }
          width={menu === 'length' ? 320 : menu === 'episodes' ? 160 : 240}
          label={menu === 'length' ? 'Length' : menu === 'episodes' ? 'Episodes' : 'Add reference'}
          className={`cf-popover cf-popover-${menu}`}
          onClose={() => setMenu(null)}
        >
          {menu === 'length' ? (
            <>
              <div className="cf-length-label">
                <span>
                  <Icon name="clock" size={12} />
                  Length
                </span>
                <strong>{state.length} sec</strong>
              </div>
              <input
                type="range"
                aria-label="Length in seconds"
                min={15}
                max={300}
                step={5}
                value={state.length}
                onChange={(event) => update({ length: +event.target.value })}
              />
            </>
          ) : menu === 'episodes' ? (
            <>
              <p>Episodes</p>
              {[1, 2, 3, 4].map((count) => (
                <button
                  key={count}
                  role="menuitemradio"
                  aria-checked={state.episodes === count}
                  onClick={() => {
                    update({ episodes: count });
                    setMenu(null);
                  }}
                >
                  {count} {count === 1 ? 'episode' : 'episodes'}
                </button>
              ))}
            </>
          ) : (
            <>
              <button
                onClick={() => {
                  setReferenceLink(state.reference_url || '');
                  setMenu(null);
                  setDialog('link');
                }}
              >
                <Icon name="external" />
                Add TikTok
                <br />
                or Instagram link
              </button>
              {(state.reference_asset_id || state.reference_url || state.style_id) && (
                <button
                  onClick={() => {
                    update({ reference_asset_id: null, reference_url: null, style_id: null });
                    setMenu(null);
                  }}
                >
                  <Icon name="close" />
                  Remove reference
                </button>
              )}
              <hr />
              <button
                onClick={() => {
                  setMediaRole('reference');
                  setMenu(null);
                  setDialog('media');
                }}
              >
                <Icon name="upload" />
                Upload or select file
              </button>
            </>
          )}
        </AnchoredPopover>
      )}
      <input
        ref={fileInput}
        hidden
        type="file"
        accept="image/*,video/*"
        multiple={mediaRole === 'attachment'}
        onChange={(event) => void uploadFiles(event.target.files)}
      />
      {(dialog || stylePreview) && (
        <dialog
          ref={modal}
          className={`cf-dialog ${dialog === 'link' ? 'cf-link-dialog' : ''}`}
          onCancel={closeDialog}
          aria-label={
            dialog === 'link'
              ? 'Generate new episode'
              : dialog === 'media'
                ? 'Select media'
                : stylePreview
                  ? 'Style preview'
                  : 'Generation availability'
          }
        >
          <header>
            <h2>
              {dialog === 'link'
                ? 'Generate new episode'
                : dialog === 'media'
                  ? 'Select media'
                  : stylePreview
                    ? stylePreview.title || 'Style preview'
                    : 'Generation availability'}
            </h2>
            <button aria-label="Close dialog" onClick={closeDialog}>
              <Icon name="close" size={16} />
            </button>
          </header>
          {dialog === 'link' ? (
            <div className="cf-link-body">
              <div className="cf-link-art">
                {linkPreview && <img src={linkPreview} alt="Reference video preview" />}
                <span />
              </div>
              <h3>
                Recreate video style
                <br />
                from reels or TikTok
              </h3>
              <div className="cf-link-form">
                <label htmlFor="factory-reference-url">Paste link</label>
                <div>
                  <Icon name="external" size={16} />
                  <input
                    id="factory-reference-url"
                    placeholder="TikTok or Instagram link"
                    value={referenceLink}
                    onChange={(event) => setReferenceLink(event.target.value)}
                  />
                </div>
                <button onClick={saveLink} disabled={!referenceLink.trim()}>
                  Continue
                </button>
              </div>
            </div>
          ) : dialog === 'media' ? (
            <div className="cf-media-picker">
              <button
                className="cf-upload"
                disabled={uploading}
                onClick={() => fileInput.current?.click()}
              >
                <Icon name="upload" />
                {uploading ? 'Uploading…' : 'Upload image or video'}
              </button>
              <div>
                {assets
                  .filter((asset) => ['image', 'video'].includes(asset.kind))
                  .map((asset) => (
                    <button key={asset.id} onClick={() => chooseAsset(asset)}>
                      {asset.thumbnail_url && <img src={asset.thumbnail_url} alt="" />}
                      <span>{asset.name}</span>
                    </button>
                  ))}
              </div>
            </div>
          ) : stylePreview ? (
            <div className="cf-preview-body">
              <video
                src={stylePreview.video}
                poster={stylePreview.poster}
                controls
                autoPlay
                playsInline
              />
              <button
                disabled={!!importingStyle || !session.ready}
                onClick={() => void chooseStyle(stylePreview)}
              >
                {importingStyle === stylePreview.id ? 'Loading reference…' : 'Use as reference'}
              </button>
            </div>
          ) : (
            <div className="cf-capability">
              <Icon name="info" size={24} />
              <p>{message}</p>
              <p>
                Your source media and brief stay in this app. An unavailable operation is never
                replaced with a generic video render.
              </p>
            </div>
          )}
          {message && dialog !== 'capability' && (
            <p className="cf-dialog-error" role="alert">
              {message}
            </p>
          )}
        </dialog>
      )}
    </main>
  );
}
