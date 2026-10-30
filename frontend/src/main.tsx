import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { SuiteApp } from './apps/SuiteApp';
import './styles.css';
import './reference.css';
if (['/supercomputer', '/canvas', '/speak'].includes(location.pathname)) {
  history.replaceState(null, '', '/content-factory');
}
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {location.pathname === '/studio/vfx' ||
    (location.pathname === '/' && location.search.includes('view=')) ? (
      <App />
    ) : (
      <SuiteApp />
    )}
  </React.StrictMode>,
);
