import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { RoomEditorDoubleClick } from './components/RoomEditorDoubleClick';
import { WorkspaceScrollGuard } from './components/WorkspaceScrollGuard';
import './styles.css';
import './room-editor.css';
import './production.css';
import './interior.css';
import './stability-1.5.2.css';
import './viewport-1.5.3.css';
import './runtime-1.5.4.css';
import './standalone-layout-1.5.5.css';
import './fixed-workspace-1.5.6.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <WorkspaceScrollGuard>
      <RoomEditorDoubleClick>
        <App />
      </RoomEditorDoubleClick>
    </WorkspaceScrollGuard>
  </React.StrictMode>,
);
