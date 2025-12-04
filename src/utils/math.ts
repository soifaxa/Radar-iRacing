import { Position, Car, Player } from '../types/radar';

/**
 * Calcule la distance entre deux positions
 */
export function calculateDistance(pos1: Position, pos2: Position): number {
  const dx = pos2.x - pos1.x;
  const dy = pos2.y - pos1.y;
  const dz = pos2.z - pos1.z;
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

/**
 * "Unwrapp" un angle pour éviter les discontinuités lors du passage de -π à +π
 * Utilise l'angle précédent pour déterminer la bonne "branche" de l'angle
 * Version améliorée pour gérer les sauts importants et les discontinuités à la ligne médiane
 */
export function unwrapAngle(currentAngle: number, previousAngle: number): number {
  // Si c'est la première fois, retourner l'angle tel quel
  if (previousAngle === null || isNaN(previousAngle)) {
    return currentAngle;
  }
  
  // Calculer la différence brute
  let delta = currentAngle - previousAngle;
  
  // Normaliser la différence dans [-π, π] pour trouver le chemin le plus court
  // Cela gère les cas où on passe de -π à +π ou vice versa
  while (delta > Math.PI) {
    delta -= 2 * Math.PI;
  }
  while (delta < -Math.PI) {
    delta += 2 * Math.PI;
  }
  
  // Si le delta est très grand (proche de ±π), c'est probablement un saut discontinu
  // Dans ce cas, on peut essayer de détecter si c'est vraiment un saut ou une rotation continue
  // Pour l'instant, on fait confiance au delta normalisé
  
  // Ajouter la différence à l'angle précédent pour obtenir un angle continu
  const unwrapped = previousAngle + delta;
  
  return unwrapped;
}

/**
 * Transforme les coordonnées d'une voiture en coordonnées relatives au joueur
 * avec rotation inverse selon l'orientation du joueur
 * 
 * Utilise atan2 pour calculer directement l'angle relatif, puis "unwrapp" cet angle
 * pour éviter les discontinuités à la ligne médiane.
 */
export function transformToRadarCoordinates(
  car: Car,
  player: Player,
  unwrappedYaw?: number,
  previousRelativeAngle?: number
): { x: number; y: number; distance: number; relativeAngle: number } {
  // Vecteur relatif
  const dx = car.position.x - player.position.x;
  const dy = car.position.y - player.position.y;
  const dz = car.position.z - player.position.z;

  // Distance 3D
  const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);

  // Distance horizontale (2D)
  const horizontalDistance = Math.sqrt(dx * dx + dy * dy);
  
  // Si la distance horizontale est nulle, la voiture est exactement au-dessus/en-dessous
  if (horizontalDistance < 0.001) {
    return { x: 0, y: 0, distance, relativeAngle: 0 };
  }

  // Utiliser le yaw "unwrapped" si fourni, sinon utiliser le yaw brut
  const yawToUse = unwrappedYaw !== undefined ? unwrappedYaw : player.yaw;
  
  // Calculer l'angle relatif de la voiture par rapport au joueur dans le référentiel iRacing
  // atan2(dy, dx) donne l'angle où 0° = Est (comme iRacing)
  let relativeAngle = Math.atan2(dy, dx);
  
  // "Unwrapp" l'angle relatif pour éviter les discontinuités
  if (previousRelativeAngle !== undefined) {
    relativeAngle = unwrapAngle(relativeAngle, previousRelativeAngle);
  }
  
  // Calculer l'angle dans le référentiel du radar (relatif à l'orientation du joueur)
  // iRacing yaw: 0° = Est, radar: 0° = Nord (haut)
  // Pour convertir: Est (0°) dans iRacing = 90° dans le référentiel Nord = π/2
  // On soustrait le yaw du joueur pour obtenir l'angle relatif, puis on ajoute π/2 pour aligner avec le Nord
  const radarAngle = relativeAngle - yawToUse;
  
  // Convertir en coordonnées cartésiennes dans le référentiel du radar
  // Le radar a Y vers le haut (nord), X vers la droite (est)
  // Pour que les voitures derrière (angle = π) apparaissent en bas :
  // - Pour angle = π: on veut y < 0 (négatif) pour qu'après inversion Y dans le rendu, screenY > centerY (en bas)
  // - Utiliser sin pour X et -cos pour Y pour corriger la direction
  // - Pour angle = π: sin(π) = 0, cos(π) = -1
  // - Donc x = 0 (centre), y = -(-1) * distance = distance (positif) - pas bon
  // - Essayons avec sin pour X et cos pour Y, mais inverser Y dans le rendu
  const x = horizontalDistance * Math.sin(radarAngle);
  const y = horizontalDistance * Math.cos(radarAngle);

  return { x, y, distance, relativeAngle };
}

/**
 * Convertit les coordonnées du monde en coordonnées pixels du radar
 */
export function worldToPixel(
  worldX: number,
  worldY: number,
  worldRadius: number,
  pixelRadius: number
): { x: number; y: number } {
  const scale = pixelRadius / worldRadius;
  return {
    x: worldX * scale,
    y: worldY * scale,
  };
}

/**
 * Filtre les voitures qui sont dans le rayon du radar
 */
export function filterCarsInRange(
  cars: Car[],
  player: Player,
  radius: number
): Car[] {
  return cars
    .map((car) => {
      const distance = calculateDistance(car.position, player.position);
      return { ...car, distance };
    })
    .filter((car) => car.distance <= radius)
    .sort((a, b) => (a.distance || 0) - (b.distance || 0));
}

