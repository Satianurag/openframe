import { useEffect, useRef, useState } from 'react';
import { Icon } from '../Icon';
import { api, post, upload } from '../api';
import type { PlannerInfo } from './plannerStatus';
import { AnchoredPopover } from '../Popovers';
import type { AppDocument } from './registry';
import type { Catalog, Settings } from '../types';
import { SequencePlanner } from './SequencePlanner';
import { useAppDocument } from './useAppDocument';
import { AppSwitcher } from './AppSwitcher';
import './supercomputer.css';

type AgentState = {
  kind: 'chat' | 'project' | 'skill';
  title: string;
  instructions: string;
  prompt: string;
  attachment_asset_ids: string[];
  project_id: string | null;
  skill_ids: string[];
  connector_ids: string[];
  agent_mode: 'ask' | 'auto';
  model_id: string;
  category: string;
  messages: { role: string; text: string }[];
};
type Showcase = {
  id: string;
  title: string;
  prompt: string;
  category: string;
  video?: string;
  poster?: string;
  source_url?: string;
};
const initial: AgentState = {
  kind: 'chat',
  title: '',
  instructions: '',
  prompt: '',
  attachment_asset_ids: [],
  project_id: null,
  skill_ids: [],
  connector_ids: [],
  agent_mode: 'ask',
  model_id: 'auto',
  category: 'All',
  messages: [],
};
const assetIds = (state: AgentState) => state.attachment_asset_ids;
export function Supercomputer({
  catalog,
  settings,
  onSettings,
}: {
  catalog: Catalog;
  settings: Settings;
  onSettings: () => void;
}) {
  const session = useAppDocument('supercomputer', initial, assetIds);
  const { state, update } = session;
  const [planDocument, setPlanDocument] = useState<AppDocument<Record<string, unknown>> | null>(
    null,
  );
  const [collapsed, setCollapsed] = useState(false);
  const [showLearn, setShowLearn] = useState(true);
  const [showChats, setShowChats] = useState(true);
  const [showcase, setShowcase] = useState<Showcase[]>([]);
  const [selectedShowcase, setSelectedShowcase] = useState<Showcase | null>(null);
  const [menu, setMenu] = useState<{ name: string; anchor: HTMLElement } | null>(null);
  const [search, setSearch] = useState('');
  const [projectName, setProjectName] = useState('');
  const [skillInstructions, setSkillInstructions] = useState('');
  const [showSkills, setShowSkills] = useState(false);
  const composer = useRef<HTMLTextAreaElement>(null);
  const [panel, setPanel] = useState<string | null>(null);
  const [feedback, setFeedback] = useState('');
  const [plannerInfo, setPlannerInfo] = useState<PlannerInfo | null>(null);
  const [uploading, setUploading] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    void api<PlannerInfo>('/planner')
      .then(setPlannerInfo)
      .catch(() => {});
    fetch('/reference-media/components.json')
      .then((response) => (response.ok ? response.json() : null))
      .then((manifest) => setShowcase(manifest?.supercomputer?.showcases || []))
      .catch(() => {});
  }, []);
  useEffect(() => {
    const current = dialog.current;
    if (panel || selectedShowcase) current?.showModal();
    return () => current?.close();
  }, [panel, selectedShowcase]);
  const projects = session.documents.filter((doc) => doc.state.kind === 'project');
  const chats = session.documents.filter((doc) => !doc.state.kind || doc.state.kind === 'chat');
  const skills = session.documents.filter((doc) => doc.state.kind === 'skill');
  const openMenu = (name: string, anchor: HTMLElement) => {
    setSearch('');
    setShowSkills(false);
    setMenu(menu?.name === name ? null : { name, anchor });
  };
  const openSkills = () => {
    setShowSkills(!showSkills);
    setMenu(null);
    if (!showSkills) {
      update({ prompt: state.prompt || '/' });
      composer.current?.focus();
    }
  };
  async function createDocument(kind: 'project' | 'skill') {
    if (!projectName.trim()) return;
    try {
      const doc = await post<AppDocument<AgentState>>('/apps/supercomputer/documents', {
        title: projectName.trim(),
        schema_version: 1,
        state: {
          ...initial,
          kind,
          title: projectName.trim(),
          instructions: kind === 'skill' ? skillInstructions : '',
        },
        asset_ids: [],
      });
      await session.refreshDocuments();
      if (kind === 'project') update({ project_id: doc.id });
      setPanel(null);
      setProjectName('');
      setSkillInstructions('');
    } catch (reason) {
      setFeedback((reason as Error).message);
    }
  }
  const unavailable = (title: string, detail?: string) => {
    setFeedback(
      detail ||
        session.application?.operations.find((item) => item.id === 'agent-run')?.reason ||
        'The agent execution service is not connected. This action has not started a generation.',
    );
    setPanel(title);
  };
  async function send() {
    const doc = await session.save(true);
    if (!doc) {
      unavailable('Save failed', session.error || 'The brief could not be saved.');
      return;
    }
    setShowSkills(false);
    setPlanDocument(doc);
  }
  async function attach(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    try {
      const ids: string[] = [];
      for (const file of Array.from(files)) ids.push((await upload(file)).id);
      update({ attachment_asset_ids: [...new Set([...state.attachment_asset_ids, ...ids])] });
    } catch (reason) {
      unavailable('Upload failed', (reason as Error).message);
    } finally {
      setUploading(false);
      if (input.current) input.current.value = '';
    }
  }
  return (
    <main className={`supercomputer ${collapsed ? 'sc-collapsed' : ''}`}>
      {planDocument && (
        <SequencePlanner
          appId="supercomputer"
          document={planDocument}
          initialPrompt={state.prompt.replace(/^\//, '')}
          targetDuration={30}
          episodeCount={1}
          catalog={catalog}
          settings={settings}
          onClose={() => setPlanDocument(null)}
          onPrepareDocument={async (ids) => {
            const doc = await session.updateAndSave({
              attachment_asset_ids: [...new Set([...state.attachment_asset_ids, ...ids])],
            });
            if (!doc) throw new Error('Could not save the attached media.');
            setPlanDocument(doc);
            return doc;
          }}
          onCreated={() => {
            void session.refreshJobs();
          }}
        />
      )}
      <aside className="sc-rail">
        <div className="sc-rail-top">
          <AppSwitcher name="Supercomputer" />
          <button aria-label="Search" onClick={() => setPanel('Search chats')}>
            <Icon name="search" size={15} />
          </button>
          <button aria-label="Collapse sidebar" onClick={() => setCollapsed(!collapsed)}>
            <Icon name="split" size={15} />
          </button>
        </div>
        <nav aria-label="Supercomputer">
          <button className="active" onClick={() => void session.newDocument()}>
            <span>
              <Icon name="plus" />
            </span>
            New chat
          </button>
          <button onClick={() => setPanel('Projects')}>
            <span>
              <Icon name="folder" />
            </span>
            Projects
          </button>
          <button onClick={openSkills}>
            <span>
              <Icon name="bolt" />
            </span>
            Skills
          </button>
          <button onClick={(event) => openMenu('Connectors', event.currentTarget)}>
            <span>
              <Icon name="grid" />
            </span>
            Connectors
          </button>
          <button onClick={() => unavailable('More tools')}>
            <span>···</span>See more
          </button>
        </nav>
        <button
          className="sc-chats-label"
          aria-expanded={showChats}
          onClick={() => setShowChats(!showChats)}
        >
          Chats
          <Icon name="down" size={12} />
        </button>
        {showChats && (
          <div className="sc-chats">
            {chats.length ? (
              chats.map((document) => (
                <button key={document.id} onClick={() => void session.openDocument(document)}>
                  {document.title}
                </button>
              ))
            ) : (
              <div className="sc-no-chats">
                <div>
                  <Icon name="folder" size={68} />
                  <i>
                    <Icon name="plus" size={20} />
                  </i>
                </div>
                <strong>No chats yet</strong>
                <p>Create one to get started</p>
              </div>
            )}
          </div>
        )}
        <div className="sc-rail-bottom">
          {showLearn && (
            <aside className="sc-learn">
              <button aria-label="Close learning card" onClick={() => setShowLearn(false)}>
                <Icon name="close" size={12} />
              </button>
              <small>Learn to make movies</small>
              <p>Practical workflows from working AI filmmakers</p>
              <a href="https://higgsfield.ai/academy" target="_blank" rel="noreferrer">
                Learn more
                <Icon name="external" size={12} />
              </a>
            </aside>
          )}
          <button className="sc-workspace" onClick={onSettings}>
            <Icon name="settings" size={16} />
            Local workspace
          </button>
        </div>
      </aside>
      <section className="sc-main">
        <button
          className="sc-incognito"
          aria-label="Session privacy"
          onClick={() =>
            unavailable(
              'Local workspace',
              'Documents and media are saved in your configured OpenFrame workspace. This is not an incognito session.',
            )
          }
        >
          <Icon name="info" size={15} />
        </button>
        <div className="sc-start">
          <h1>
            <span className="app-mark">
              <Icon name="spark" size={24} />
            </span>
            What are we creating today?
          </h1>
          <div className="sc-composer">
            <textarea
              ref={composer}
              aria-label="Describe what to create"
              placeholder="Generate an explainer video…"
              value={state.prompt}
              onChange={(event) => {
                update({ prompt: event.target.value });
                setShowSkills(event.target.value.startsWith('/'));
              }}
            />
            <div className="sc-composer-row">
              <button
                aria-label="Add attachments"
                onClick={() => input.current?.click()}
                disabled={uploading}
              >
                <Icon name="plus" />
              </button>
              <button
                className="sc-model"
                aria-label="Model settings"
                onClick={(event) => openMenu('Models', event.currentTarget)}
              >
                <Icon name="code" size={14} />
                {state.model_id === 'auto' ? 'Auto' : plannerInfo?.name || 'Configured CPU planner'}
                <Icon name="down" size={12} />
              </button>
              <button
                className="sc-agent-mode"
                aria-label="Agent mode"
                onClick={() =>
                  unavailable(
                    'Agent mode',
                    'Ask-before-generating is saved in this brief. A connected agent executor is required to propose and approve plans.',
                  )
                }
              >
                <Icon name="mask" size={14} />
                Ask before generating
              </button>
              <button
                aria-label="Voice input"
                onClick={() =>
                  unavailable(
                    'Voice input',
                    'Voice transcription is not configured. You can attach a recording to the brief.',
                  )
                }
              >
                <Icon name="sound" />
              </button>
              <button
                className="sc-send"
                aria-label="Send message"
                disabled={!state.prompt.trim() || !session.ready}
                onClick={() => void send()}
              >
                <Icon name="arrow" size={18} />
              </button>
            </div>
          </div>
          <div className="sc-context-row">
            <button onClick={(event) => openMenu('Project', event.currentTarget)}>
              <Icon name="folder" size={13} />
              {projects.find((doc) => doc.id === state.project_id)?.title || 'No project'}
            </button>
            <button onClick={openSkills}>
              <Icon name="bolt" size={13} />
              Skills
            </button>
            <button onClick={(event) => openMenu('Connectors', event.currentTarget)}>
              <Icon name="grid" size={13} />
              Connectors
            </button>
            <button className="sc-mcp" onClick={() => unavailable('MCP connection')}>
              <Icon name="code" size={13} />
              Try MCP
            </button>
          </div>
          {showSkills && (
            <div className="sc-skills-panel">
              <h3>
                <Icon name="bolt" size={16} />
                Workspace skills
              </h3>
              {[
                [
                  'Shot planner',
                  'Plan an editable sequence of shots with the local language model.',
                ],
                ['Narration', 'Generate speech from text or animate a portrait with a recording.'],
                ['VFX editing', 'Remove, replace, or restyle objects in your video.'],
              ].map(([name, description]) => (
                <button
                  key={name}
                  onClick={() => {
                    setShowSkills(false);
                    if (name === 'Shot planner')
                      update({ prompt: state.prompt.replace(/^\//, '') });
                    else
                      void session.save().then(() => {
                        location.href = name === 'Narration' ? '/speak' : '/studio/vfx';
                      });
                  }}
                >
                  <span>
                    <Icon name="bolt" size={26} />
                  </span>
                  <div>
                    <strong>{name}</strong>
                    <p>{description}</p>
                  </div>
                </button>
              ))}
              <h3>
                <Icon name="user" size={16} />
                My skills
              </h3>
              {skills.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => {
                    update({ prompt: doc.state.instructions, skill_ids: [doc.id] });
                    setShowSkills(false);
                  }}
                >
                  <span>
                    <Icon name="bolt" size={26} />
                  </span>
                  <div>
                    <strong>{doc.title}</strong>
                    <p>{doc.state.instructions}</p>
                  </div>
                </button>
              ))}
              <button
                onClick={() => {
                  setPanel('New skill');
                  setProjectName('');
                  setSkillInstructions('');
                  setShowSkills(false);
                }}
              >
                <span>
                  <Icon name="plus" size={26} />
                </span>
                <div>
                  <strong>Create new skill</strong>
                  <p>Save reusable prompt instructions</p>
                </div>
              </button>
            </div>
          )}
          {state.attachment_asset_ids.length > 0 && (
            <div className="sc-attachments">
              {state.attachment_asset_ids.map((id, index) => (
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
                  Attachment {index + 1}
                  <Icon name="close" size={12} />
                </button>
              ))}
            </div>
          )}
          {session.error && (
            <p role="alert" className="sc-error">
              {session.error}
            </p>
          )}
        </div>
        <section className="sc-showcases">
          <div className="sc-categories">
            {['All', 'Marketing', 'Explainer videos', 'Apps', 'Games'].map((category) => (
              <button
                key={category}
                className={state.category === category ? 'active' : ''}
                onClick={() => update({ category })}
              >
                <Icon
                  name={
                    category === 'All'
                      ? 'grid'
                      : category === 'Explainer videos'
                        ? 'video'
                        : 'spark'
                  }
                  size={13}
                />
                {category}
              </button>
            ))}
          </div>
          <div className="sc-showcase-grid">
            {showcase
              .filter((item) => state.category === 'All' || item.category === state.category)
              .map((item) => (
                <figure key={item.id}>
                  <button
                    className="sc-showcase-media"
                    onClick={() => setSelectedShowcase(item)}
                    aria-label={`Open ${item.title} showcase`}
                  >
                    {item.video ? (
                      <video
                        src={item.video}
                        poster={item.poster}
                        muted
                        loop
                        playsInline
                        preload="metadata"
                        onMouseEnter={(event) => void event.currentTarget.play().catch(() => {})}
                        onMouseLeave={(event) => event.currentTarget.pause()}
                      />
                    ) : item.poster ? (
                      <img src={item.poster} alt="" />
                    ) : null}
                  </button>
                  <figcaption>
                    <Icon name="film" size={18} />
                    {item.title}
                  </figcaption>
                  <div className="sc-showcase-overlay">
                    <p>{item.prompt}</p>
                    <button
                      onClick={() => {
                        update({ prompt: item.prompt });
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                      }}
                    >
                      Recreate
                    </button>
                  </div>
                </figure>
              ))}
          </div>
        </section>
      </section>
      <input
        ref={input}
        type="file"
        hidden
        multiple
        accept="image/*,video/*,audio/*"
        onChange={(event) => void attach(event.target.files)}
      />
      {menu && (
        <AnchoredPopover
          anchor={menu.anchor}
          onClose={() => setMenu(null)}
          label={menu.name}
          width={menu.name === 'Models' ? 444 : 300}
          placement="bottom-start"
          className={`sc-picker sc-picker-${menu.name.toLowerCase()}`}
        >
          <label className="sc-picker-search">
            <Icon name="search" size={16} />
            <input
              aria-label={`Search ${menu.name}`}
              placeholder={menu.name === 'Connectors' ? 'Search Connectors' : 'Search'}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          {menu.name === 'Models' ? (
            <>
              <h3>Available planning models</h3>
              {[
                ['auto', 'Auto', 'Uses the configured shot-planning model.'],
                [
                  plannerInfo?.model_id || 'configured',
                  plannerInfo?.name || 'Configured CPU planner',
                  'CPU shot planning · editable proposals before generation.',
                ],
              ]
                .filter((item) => item.join(' ').toLowerCase().includes(search.toLowerCase()))
                .map(([id, name, description]) => (
                  <button
                    className="sc-model-option"
                    key={id}
                    onClick={() => {
                      update({ model_id: id });
                      setMenu(null);
                    }}
                  >
                    <span>
                      <Icon name="spark" size={24} />
                    </span>
                    <div>
                      <strong>{name}</strong>
                      <p>{description}</p>
                    </div>
                    {state.model_id === id && <Icon name="check" size={18} />}
                  </button>
                ))}
            </>
          ) : menu.name === 'Project' ? (
            <>
              <button
                onClick={() => {
                  update({ project_id: null });
                  setMenu(null);
                }}
              >
                <Icon name="folder" size={16} />
                No project
              </button>
              {projects
                .filter((doc) => doc.title.toLowerCase().includes(search.toLowerCase()))
                .map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => {
                      update({ project_id: doc.id });
                      setMenu(null);
                    }}
                  >
                    <Icon name="folder" size={16} />
                    {doc.title}
                  </button>
                ))}
              <button
                onClick={() => {
                  setPanel('New project');
                  setProjectName('');
                  setMenu(null);
                }}
              >
                <Icon name="plus" size={16} />
                New project
              </button>
            </>
          ) : (
            <>
              <p className="sc-no-connectors">No connected connectors</p>
              <button
                onClick={() => {
                  setMenu(null);
                  unavailable(
                    'Manage connectors',
                    'No external connector service is configured. Local uploads and compute providers remain available.',
                  );
                }}
              >
                Manage Connectors
                <Icon name="external" size={14} />
              </button>
            </>
          )}
        </AnchoredPopover>
      )}
      {(panel || selectedShowcase) && (
        <dialog
          ref={dialog}
          className={`sc-dialog ${panel === 'New project' || panel === 'New skill' ? 'sc-new-document' : ''}`}
          onCancel={() => {
            setPanel(null);
            setSelectedShowcase(null);
          }}
          aria-label={panel || selectedShowcase?.title}
        >
          <header>
            <h2>{panel || selectedShowcase?.title}</h2>
            <button
              aria-label="Close dialog"
              onClick={() => {
                setPanel(null);
                setSelectedShowcase(null);
              }}
            >
              <Icon name="close" />
            </button>
          </header>
          {selectedShowcase ? (
            <div className="sc-showcase-detail">
              {selectedShowcase.video ? (
                <video
                  src={selectedShowcase.video}
                  poster={selectedShowcase.poster}
                  controls
                  autoPlay
                />
              ) : (
                selectedShowcase.poster && <img src={selectedShowcase.poster} alt="" />
              )}
              <p>{selectedShowcase.prompt}</p>
              <button
                onClick={() => {
                  update({ prompt: selectedShowcase.prompt });
                  setSelectedShowcase(null);
                }}
              >
                Recreate
              </button>
            </div>
          ) : panel === 'New project' || panel === 'New skill' ? (
            <div className="sc-new-document-form">
              <input
                aria-label={panel === 'New project' ? 'Project name' : 'Skill name'}
                autoFocus
                placeholder={panel === 'New project' ? 'My project' : 'My skill'}
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
              />
              {panel === 'New skill' ? (
                <textarea
                  aria-label="Skill instructions"
                  placeholder="Describe the reusable instructions"
                  value={skillInstructions}
                  onChange={(event) => setSkillInstructions(event.target.value)}
                />
              ) : (
                <span>
                  <Icon name="folder" size={16} />
                  Local project
                </span>
              )}
              <button
                disabled={
                  !projectName.trim() || (panel === 'New skill' && !skillInstructions.trim())
                }
                onClick={() => void createDocument(panel === 'New project' ? 'project' : 'skill')}
              >
                Create
              </button>
            </div>
          ) : panel === 'Projects' || panel === 'Search chats' ? (
            <div className="sc-document-list">
              <input
                aria-label="Search saved documents"
                placeholder="Search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              {panel === 'Projects' && (
                <button
                  onClick={() => {
                    setPanel('New project');
                    setProjectName('');
                  }}
                >
                  + New project
                </button>
              )}
              {(panel === 'Projects' ? projects : chats).length ? (
                (panel === 'Projects' ? projects : chats)
                  .filter((doc) => doc.title.toLowerCase().includes(search.toLowerCase()))
                  .map((document) => (
                    <button
                      key={document.id}
                      onClick={() => {
                        if (document.state.kind === 'project') update({ project_id: document.id });
                        else void session.openDocument(document);
                        setPanel(null);
                      }}
                    >
                      {document.title}
                    </button>
                  ))
              ) : (
                <p>No saved briefs yet.</p>
              )}
            </div>
          ) : (
            <p>{feedback}</p>
          )}
        </dialog>
      )}
    </main>
  );
}
