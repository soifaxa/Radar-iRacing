import { useState, useEffect, useCallback, useRef } from 'react';
import { Player, Car } from '../types/radar';
import { filterCarsInRange, unwrapAngle } from '../utils/math';
import { SERVER_CONFIG } from '../config/server';
import { logInfo, logWarn, logError, setWebSocketForLogs } from '../utils/logger';

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
  // Suivi du yaw précédent pour éviter les discontinuités à la ligne médiane
  const previousYawRef = useRef<number | null>(null);
  // Suivi des positions précédentes des voitures pour détecter les sauts discontinus
  const previousCarPositionsRef = useRef<Map<number, Position>>(new Map());
  // Suivi des angles relatifs précédents pour éviter les discontinuités
  const previousRelativeAnglesRef = useRef<Map<number, number>>(new Map());
  const previousPlayerPositionRef = useRef<Position | null>(null);

  const updateRadar = useCallback(
    (newPlayer: Player, newCars: Car[]) => {
      // "Unwrapp" le yaw pour éviter les discontinuités à la ligne médiane
      let unwrappedYaw = newPlayer.yaw;
      if (previousYawRef.current !== null) {
        unwrappedYaw = unwrapAngle(newPlayer.yaw, previousYawRef.current);
      }
      previousYawRef.current = unwrappedYaw;
      
      // Détecter et corriger les sauts discontinus dans les positions
      // Si la position du joueur a un saut discontinu, ajuster les positions des voitures
      let adjustedPlayerPosition = newPlayer.position;
      if (previousPlayerPositionRef.current !== null) {
        const prevPos = previousPlayerPositionRef.current;
        const dx = newPlayer.position.x - prevPos.x;
        const dy = newPlayer.position.y - prevPos.y;
        const dz = newPlayer.position.z - prevPos.z;
        const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        
        // Si le saut est très grand (> 100m), c'est probablement une discontinuité à la ligne médiane
        // Dans ce cas, on garde la position telle quelle (iRacing gère peut-être déjà le saut)
        // Mais on va ajuster les positions des voitures relativement
      }
      previousPlayerPositionRef.current = adjustedPlayerPosition;
      
      // Ajuster les positions des voitures pour éviter les sauts discontinus
      const adjustedCars = newCars.map((car, index) => {
        const carKey = index; // Utiliser l'index comme clé (on pourrait utiliser un ID si disponible)
        const previousPos = previousCarPositionsRef.current.get(carKey);
        
        if (previousPos) {
          const dx = car.position.x - previousPos.x;
          const dy = car.position.y - previousPos.y;
          const dz = car.position.z - previousPos.z;
          const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
          
          // Si le saut est très grand (> 100m), c'est probablement une discontinuité
          // On garde la position telle quelle pour l'instant
          // (Le problème pourrait être dans la transformation, pas dans les positions)
        }
        
        // Mettre à jour la position précédente
        previousCarPositionsRef.current.set(carKey, car.position);
        
        return car;
      });
      
      // Créer un joueur avec le yaw "unwrapped"
      const playerWithUnwrappedYaw: Player = {
        position: adjustedPlayerPosition,
        yaw: unwrappedYaw,
      };
      
      const filteredCars = filterCarsInRange(adjustedCars, playerWithUnwrappedYaw, radius);
      
      // Log uniquement des voitures affichées dans le radar (filtrées)
      const logMessage = `🔍 Filtrage: ${newCars.length} voitures reçues, ${filteredCars.length} voiture(s) dans le rayon (${radius}m)`;
      console.log(logMessage);
      logInfo(logMessage);
      
      if (filteredCars.length > 0) {
        filteredCars.forEach((car, index) => {
          const dx = car.position.x - adjustedPlayerPosition.x;
          const dy = car.position.y - adjustedPlayerPosition.y;
          const dz = car.position.z - adjustedPlayerPosition.z;
          const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
          const carLog = `  Voiture ${index + 1}: distance=${distance.toFixed(2)}m, pos=(${car.position.x.toFixed(2)}, ${car.position.y.toFixed(2)}, ${car.position.z.toFixed(2)})`;
          console.log(carLog);
          logInfo(carLog);
        });
      }
      
      if (filteredCars.length === 0 && newCars.length > 0) {
        const warnMessage = `⚠️ Toutes les voitures sont en dehors du rayon de ${radius}m. Essayez d'augmenter le rayon.`;
        console.warn(warnMessage);
        logWarn(warnMessage);
      }
      
      setPlayer(playerWithUnwrappedYaw);
      setCars(filteredCars);
      onUpdate?.(playerWithUnwrappedYaw, filteredCars);
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
        ws = new WebSocket(SERVER_CONFIG.websocketUrl);

        ws.onopen = () => {
          if (isMounted) {
            setIsConnected(true);
            setWebSocketForLogs(ws); // Configurer le WebSocket pour les logs
            const msg = '✅ WebSocket connecté au serveur iRacing';
            console.log(msg);
            logInfo(msg);
          }
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            if (data.player && data.cars) {
              updateRadar(data.player, data.cars);
            } else {
              const msg = `⚠️ Données incomplètes reçues: ${JSON.stringify(data)}`;
              console.warn(msg);
              logWarn(msg);
            }
          } catch (error) {
            const msg = `Erreur parsing WebSocket: ${error}`;
            console.error(msg);
            logError(msg);
          }
        };

        ws.onerror = (error) => {
          if (isMounted) {
            const msg = '⚠️ Erreur WebSocket (serveur peut-être non démarré)';
            console.warn(msg);
            logWarn(msg);
            setIsConnected(false);
          }
        };

        ws.onclose = () => {
          if (isMounted) {
            setIsConnected(false);
            const msg = 'WebSocket déconnecté - tentative de reconnexion dans 3 secondes...';
            console.log(msg);
            logWarn(msg);
            
            // Reconnexion automatique après 3 secondes
            reconnectTimeout = setTimeout(() => {
              if (isMounted) {
                connectWebSocket();
              }
            }, 3000);
          }
        };
      } catch (error) {
        const msg = `WebSocket non disponible: ${error}`;
        console.warn(msg);
        logWarn(msg);
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

