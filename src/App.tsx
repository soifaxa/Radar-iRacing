import { useState } from 'react';
import { Radar } from './components/Radar';
import { useRadarUpdate } from './hooks/useRadarUpdate';
import { Player, Car } from './types/radar';
import './App.css';

function App() {
  const [radius, setRadius] = useState(50); // Rayon par défaut augmenté pour tester
  const [pixelRadius, setPixelRadius] = useState(150);
  const [showLabels, setShowLabels] = useState(false);
  const [rotationEnabled, setRotationEnabled] = useState(true);

  const { player, cars, isConnected, updateRadar } = useRadarUpdate({
    updateRate: 20,
    radius,
  });

  // Données de test (à remplacer par les vraies données iRacing)
  const handleTestData = () => {
    const testPlayer: Player = {
      position: { x: 0, y: 0, z: 0 },
      yaw: Math.PI / 4, // 45 degrés
    };

    const testCars: Car[] = [
      {
        position: { x: 5, y: 5, z: 0 },
        class: 'LMDh',
        distance: 7.07,
      },
      {
        position: { x: -8, y: 3, z: 0 },
        class: 'LMGT3',
        distance: 8.54,
      },
      {
        position: { x: 10, y: -10, z: 0 },
        class: 'LMP2',
        distance: 14.14,
      },
      {
        position: { x: -5, y: -12, z: 0 },
        class: 'SafetyCar',
        distance: 13,
      },
    ];

    updateRadar(testPlayer, testCars);
  };

  return (
    <div className="app">
      <div className="app-header">
        <h1>Radar iRacing - Style LMU</h1>
        <div className="status">
          <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '● Connecté' : '○ Déconnecté'}
          </span>
          {isConnected && (
            <span className="cars-count">
              {cars.length} voiture{cars.length > 1 ? 's' : ''} détectée{cars.length > 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      {!isConnected && (
        <div className="connection-info">
          <p>⚠️ Serveur WebSocket non connecté</p>
          <p className="connection-hint">
            Pour connecter le radar à iRacing, démarrez le serveur Python :
            <br />
            <code>python server.py</code>
          </p>
          <p className="connection-hint">
            Ou utilisez le bouton "Charger données de test" pour tester le radar.
          </p>
        </div>
      )}

      {isConnected && cars.length === 0 && (
        <div className="connection-info" style={{ borderColor: '#ffaa00' }}>
          <p>⚠️ Connecté mais aucune voiture détectée</p>
          <p className="connection-hint">
            Vérifiez la console du navigateur (F12) pour voir les logs de débogage.
            <br />
            Le rayon actuel est de <strong>{radius}m</strong>. Essayez d'augmenter le rayon.
            <br />
            Position du joueur: ({player.position.x.toFixed(2)}, {player.position.y.toFixed(2)}, {player.position.z.toFixed(2)})
          </p>
        </div>
      )}

      <div className="radar-container">
        <Radar
          player={player}
          cars={cars}
          radius={radius}
          pixelRadius={pixelRadius}
          showLabels={showLabels}
          rotationEnabled={rotationEnabled}
        />
      </div>

      <div className="controls">
        <div className="control-group">
          <label>
            Rayon (mètres):
            <input
              type="range"
              min="10"
              max="50"
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
            />
            <span>{radius}m</span>
          </label>
        </div>

        <div className="control-group">
          <label>
            Taille du radar (px):
            <input
              type="range"
              min="100"
              max="300"
              value={pixelRadius}
              onChange={(e) => setPixelRadius(Number(e.target.value))}
            />
            <span>{pixelRadius}px</span>
          </label>
        </div>

        <div className="control-group">
          <label>
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
            />
            Afficher les labels
          </label>
        </div>

        <div className="control-group">
          <label>
            <input
              type="checkbox"
              checked={rotationEnabled}
              onChange={(e) => setRotationEnabled(e.target.checked)}
            />
            Rotation activée
          </label>
        </div>

        <button onClick={handleTestData} className="test-button">
          Charger données de test
        </button>
      </div>

      <div className="legend">
        <h3>Légende:</h3>
        <div className="legend-items">
          <span style={{ color: '#00FFFF' }}>●</span> LMDh
          <span style={{ color: '#0080FF' }}>●</span> LMP2
          <span style={{ color: '#00FF00' }}>●</span> LMGT3
          <span style={{ color: '#FFFF00' }}>●</span> Safety Car
        </div>
      </div>
    </div>
  );
}

export default App;

