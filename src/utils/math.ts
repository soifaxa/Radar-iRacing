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
 * Transforme les coordonnées d'une voiture en coordonnées relatives au joueur
 * avec rotation inverse selon l'orientation du joueur
 */
export function transformToRadarCoordinates(
  car: Car,
  player: Player
): { x: number; y: number; distance: number } {
  // Vecteur relatif
  const dx = car.position.x - player.position.x;
  const dy = car.position.y - player.position.y;
  const dz = car.position.z - player.position.z;

  // Distance 3D
  const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);

  // Rotation inverse selon l'orientation du joueur (yaw)
  // Pour centrer le radar sur la direction du joueur
  const cosYaw = Math.cos(-player.yaw);
  const sinYaw = Math.sin(-player.yaw);

  const x = dx * cosYaw - dy * sinYaw;
  const y = dx * sinYaw + dy * cosYaw;

  return { x, y, distance };
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

