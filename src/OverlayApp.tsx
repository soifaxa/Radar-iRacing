import React from 'react';
import ReactDOM from 'react-dom/client';
import { Radar } from './components/Radar';
import { useRadarUpdate } from './hooks/useRadarUpdate';
import './OverlayApp.css';

function OverlayApp() {
  // Configuration par défaut pour l'overlay
  const radius = 50; // Rayon par défaut
  const pixelRadius = 150;
  const showLabels = false;
  const rotationEnabled = true;

  const { player, cars, isConnected } = useRadarUpdate({
    updateRate: 20,
    radius,
  });

  return (
    <div className="overlay-container">
      <Radar
        player={player}
        cars={cars}
        radius={radius}
        pixelRadius={pixelRadius}
        showLabels={showLabels}
        rotationEnabled={rotationEnabled}
      />
      <div className="overlay-status">
        <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <OverlayApp />
  </React.StrictMode>
);

