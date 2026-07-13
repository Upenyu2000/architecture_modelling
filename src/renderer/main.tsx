import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';
import './room-editor.css';
import './production.css';
import './interior.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
