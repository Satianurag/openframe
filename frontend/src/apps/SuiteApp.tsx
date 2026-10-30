import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '../api';
import type { Catalog, Settings } from '../types';
import { SettingsPanel } from '../SettingsPanel';
import { Icon } from '../Icon';
import { applications } from './registry';
import { ContentFactory } from './ContentFactory';
import { CinemaStudio } from './CinemaStudio';
import { AIInfluencer } from './AIInfluencer';
import { MarketingAds } from './MarketingAds';
import { Katana } from './Katana';
import { MiniApps } from './MiniApps';
import { TrimVideo, ReframeVideo } from './VideoUtilities';
import { Transitions } from './Transitions';
import { ExpandImage } from './ExpandImage';
import { ImageLayers } from './ImageLayers';
import { FPSBoost, DepthMap } from './FrameTools';
import { NativeVideoTool, nativeVideoRoutes } from './NativeVideoTools';
import { SoulImage } from './SoulImage';
import { SoulIdentity } from './SoulIdentity';
import { Genjutsu } from './Genjutsu';
import { Popcorn } from './Popcorn';
import './suite.css';

export function SuiteApp() {
  const current =
    applications.find(
      (app) =>
        app.path === location.pathname ||
        (app.id === 'mini-apps' && location.pathname.startsWith('/apps/')),
    ) || applications[0];
  const [settings, setSettings] = useState<Settings>({});
  const [catalog, setCatalog] = useState<Catalog>({ models: [], effects: [], providers: [] });
  const [showSettings, setShowSettings] = useState(false);
  const [showApps, setShowApps] = useState(false);
  useEffect(() => {
    Promise.all([api<Settings>('/settings'), api<Catalog>('/catalog')])
      .then(([s, c]) => {
        setSettings(s);
        setCatalog(c);
      })
      .catch(() => {
        /* The app document panel displays connection failures. */
      });
  }, []);
  let screen: ReactNode;
  if (current.id === 'content-factory')
    screen = <ContentFactory catalog={catalog} settings={settings} />;
  else if (current.id === 'cinema-studio')
    screen = (
      <CinemaStudio
        catalog={catalog}
        settings={settings}
        onSettings={() => setShowSettings(true)}
      />
    );
  else if (current.id === 'ai-influencer')
    screen = (
      <AIInfluencer
        catalog={catalog}
        settings={settings}
        onSettings={() => setShowSettings(true)}
      />
    );
  else if (current.id === 'marketing-ads')
    screen = (
      <MarketingAds
        catalog={catalog}
        settings={settings}
        onSettings={() => setShowSettings(true)}
      />
    );
  else if (current.id === 'katana')
    screen = (
      <Katana catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    );
  else if (current.id === 'mini-apps')
    screen = nativeVideoRoutes[location.pathname] ? (
      <NativeVideoTool
        key={location.pathname}
        operation={nativeVideoRoutes[location.pathname]}
        catalog={catalog}
        settings={settings}
        onSettings={() => setShowSettings(true)}
      />
    ) : location.pathname === '/apps/fps-boost' ? (
      <FPSBoost catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    ) : location.pathname === '/apps/video-depth' ? (
      <DepthMap catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    ) : location.pathname === '/apps/image-layers' ? (
      <ImageLayers catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    ) : location.pathname === '/apps/expand-image' ? (
      <ExpandImage catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    ) : location.pathname === '/apps/trim-video' ? (
      <TrimVideo catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    ) : location.pathname === '/apps/video-reframe' ? (
      <ReframeVideo
        catalog={catalog}
        settings={settings}
        onSettings={() => setShowSettings(true)}
      />
    ) : location.pathname === '/apps/transitions' ? (
      <Transitions catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    ) : (
      <MiniApps catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    );
  else if (current.id === 'soul-image')
    screen = (
      <SoulImage catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    );
  else if (current.id === 'soul-id-cast')
    screen = (
      <SoulIdentity
        catalog={catalog}
        settings={settings}
        onSettings={() => setShowSettings(true)}
      />
    );
  else if (current.id === 'genjutsu')
    screen = (
      <Genjutsu catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    );
  else if (current.id === 'popcorn')
    screen = (
      <Popcorn catalog={catalog} settings={settings} onSettings={() => setShowSettings(true)} />
    );
  else
    screen = (
      <section className="suite-pending">
        <h1>{current.name}</h1>
        <p>This separate screen is being implemented from its captured reference.</p>
        <a href="/studio/vfx">Open the working VFX editor</a>
      </section>
    );
  return (
    <div className={`suite-root suite-${current.id}`}>
      {current.id !== 'cinema-studio' && current.id !== 'marketing-ads' && (
        <header className="suite-header">
          <button
            className="suite-app-switch"
            aria-label="Open apps"
            onClick={() => setShowApps(!showApps)}
          >
            <svg viewBox="0 0 32 32" width="23" height="23" fill="none" aria-hidden="true">
              <path
                d="M6 12V5h12M26 20v7H14M6 21 26 7M6 29 26 15"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <nav aria-label="Apps">
            <a href="/soul">Image</a>
            <a href="/studio/vfx">Video</a>
            <a href="/docs" target="_blank" rel="noreferrer">
              API
            </a>
            <span className="suite-nav-divider" />
            <a className={current.id === 'genjutsu' ? 'active' : ''} href="/genjutsu">
              Genjutsu <small>New</small>
            </a>
            <a className={current.id === 'content-factory' ? 'active' : ''} href="/content-factory">
              Content Factory <small>New</small>
            </a>
            <a
              className={current.id === 'ai-influencer' ? 'active' : ''}
              href="/ai-influencer-studio"
            >
              AI Influencer
            </a>
            <a href="/katana">Katana</a>
            <a href="/marketing-studio">Ads Studio</a>
            <a href="/apps">Effects</a>
            <a href="/generate">Cinema Studio</a>
            <a href="/apps/image-layers">Edit</a>
          </nav>
          <div className="suite-header-actions">
            <button onClick={() => setShowSettings(true)}>
              <Icon name="cloud" size={14} />
              Compute
            </button>
            <span>Local workspace</span>
            <button className="suite-settings-button" onClick={() => setShowSettings(true)}>
              Settings
            </button>
          </div>
        </header>
      )}
      {showApps && (
        <div className="suite-app-menu" role="dialog" aria-label="Choose an app">
          <button aria-label="Close apps" onClick={() => setShowApps(false)}>
            <Icon name="close" />
          </button>
          {applications.map((app) => (
            <a key={app.id} className={app.id === current.id ? 'active' : ''} href={app.path}>
              {app.name}
              <Icon name="chevron" size={14} />
            </a>
          ))}
          <a href="/studio/vfx">
            VFX editor
            <Icon name="external" size={14} />
          </a>
        </div>
      )}
      {screen}
      {showSettings && (
        <SettingsPanel
          settings={settings}
          providers={catalog.providers}
          onSaved={setSettings}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  );
}
