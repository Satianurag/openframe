import { useState } from 'react';
import { Icon } from '../Icon';
import { applications } from './registry';
export function AppSwitcher({ name }: { name: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="app-switcher">
      <button aria-label={name} aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="app-mark">
          <Icon name="spark" size={18} />
        </span>
        {name}
        <Icon name="down" size={12} />
      </button>
      {open && (
        <div role="menu" className="app-switcher-menu">
          {applications.map((app) => (
            <a role="menuitem" key={app.id} href={app.path}>
              {app.name}
            </a>
          ))}
          <a role="menuitem" href="/studio/vfx">
            VFX editor
          </a>
        </div>
      )}
    </div>
  );
}
