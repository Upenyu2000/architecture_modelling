import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { RoomEditorDoubleClick } from './components/RoomEditorDoubleClick';
import './styles.css';
import './room-editor.css';
import './production.css';
import './interior.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RoomEditorDoubleClick>
      <App />
    </RoomEditorDoubleClick>
  </React.StrictMode>,
);
