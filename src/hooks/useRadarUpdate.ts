import { useState, useEffect, useCallback } from 'react';
import { Player, Car } from '../types/radar';
import { filterCarsInRange } from '../utils/math';

interface UseRadarUpdateOptions {
  updateRate?: number; // Hz (défaut: 20)
  radius?: number; // Rayon en mètres
  onUpdate?: (player: Player, cars: Car[]) => void;
}

/**
 * Hook pour gérer les mises à jour du radar
 * Peut être connecté à WebSocket, UDP, ou API locale
 */
export function useRadarUpdate({
  updateRate = 20,
  radius = 20,
  onUpdate,
}: UseRadarUpdateOptions = {}) {
  const [player, setPlayer] = useState<Player>({
    position: { x: 0, y: 0, z: 0 },
    yaw: 0,
  });
  const [cars, setCars] = useState<Car[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  const updateRadar = useCallback(
    (newPlayer: Player, newCars: Car[]) => {
      console.log(`🔍 Filtrage: ${newCars.length} voitures reçues, rayon = ${radius}m`);
      
      // Log détaillé des distances avant filtrage
      if (newCars.length > 0) {
        newCars.forEach((car, index) => {
          const dx = car.position.x - newPlayer.position.x;
          const dy = car.position.y - newPlayer.position.y;
          const dz = car.position.z - newPlayer.position.z;
          const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
          console.log(`  Voiture ${index + 1}: distance=${distance.toFixed(2)}m, pos=(${car.position.x.toFixed(2)}, ${car.position.y.toFixed(2)}, ${car.position.z.toFixed(2)})`);
        });
      }
      
      const filteredCars = filterCarsInRange(newCars, newPlayer, radius);
      
      console.log(`✅ Résultat: ${filteredCars.length} voiture(s) dans le rayon (${radius}m)`);
      
      if (filteredCars.length === 0 && newCars.length > 0) {
        console.warn(`⚠️ Toutes les voitures sont en dehors du rayon de ${radius}m. Essayez d'augmenter le rayon.`);
      }
      
      setPlayer(newPlayer);
      setCars(filteredCars);
      onUpdate?.(newPlayer, filteredCars);
    },
    [radius, onUpdate]
  );

  // Boucle de mise à jour avec requestAnimationFrame
  useEffect(() => {
    let animationFrameId: number;
    let lastTime = 0;
    const interval = 1000 / updateRate;

    const update = (currentTime: number) => {
      if (currentTime - lastTime >= interval) {
        // Ici, vous pouvez récupérer les données depuis WebSocket/UDP
        // Pour l'instant, on laisse la mise à jour externe
        lastTime = currentTime;
      }
      animationFrameId = requestAnimationFrame(update);
    };

    animationFrameId = requestAnimationFrame(update);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [updateRate]);

  // Connexion WebSocket avec reconnexion automatique
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;
    let isMounted = true;

    const connectWebSocket = () => {
      if (!isMounted) return;

      try {
        ws = new WebSocket('ws://localhost:8765');

        ws.onopen = () => {
          if (isMounted) {
            setIsConnected(true);
            console.log('✅ WebSocket connecté au serveur iRacing');
          }
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            if (data.player && data.cars) {
              // Log de débogage détaillé
              console.log(`📡 Données reçues: ${data.cars.length} voiture(s) du serveur`);
              console.log('Joueur:', {
                x: data.player.position.x,
                y: data.player.position.y,
                z: data.player.position.z,
                yaw: data.player.yaw
              });
              
              if (data.cars.length > 0) {
                console.log('Première voiture:', {
                  x: data.cars[0].position.x,
                  y: data.cars[0].position.y,
                  z: data.cars[0].position.z,
                  class: data.cars[0].class
                });
              } else {
                console.warn('⚠️ Aucune voiture reçue du serveur');
              }
              
              updateRadar(data.player, data.cars);
            } else {
              console.warn('⚠️ Données incomplètes reçues:', data);
            }
          } catch (error) {
            console.error('Erreur parsing WebSocket:', error);
          }
        };

        ws.onerror = (error) => {
          if (isMounted) {
            console.warn('⚠️ Erreur WebSocket (serveur peut-être non démarré)');
            setIsConnected(false);
          }
        };

        ws.onclose = () => {
          if (isMounted) {
            setIsConnected(false);
            console.log('WebSocket déconnecté - tentative de reconnexion dans 3 secondes...');
            
            // Reconnexion automatique après 3 secondes
            reconnectTimeout = setTimeout(() => {
              if (isMounted) {
                connectWebSocket();
              }
            }, 3000);
          }
        };
      } catch (error) {
        console.warn('WebSocket non disponible:', error);
        if (isMounted) {
          setIsConnected(false);
          // Tentative de reconnexion
          reconnectTimeout = setTimeout(() => {
            if (isMounted) {
              connectWebSocket();
            }
          }, 3000);
        }
      }
    };

    // Connexion initiale
    connectWebSocket();

    // Nettoyage
    return () => {
      isMounted = false;
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (ws) {
        ws.close();
      }
    };
  }, [updateRadar]);

  return {
    player,
    cars,
    isConnected,
    updateRadar,
  };
}

