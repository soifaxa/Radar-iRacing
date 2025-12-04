export interface Position {
  x: number;
  y: number;
  z: number;
}

export interface Player {
  position: Position;
  yaw: number; // Orientation en radians
}

export type CarClass = 'LMDh' | 'LMP2' | 'LMGT3' | 'SafetyCar' | 'Unknown';

export interface Car {
  position: Position;
  class: CarClass;
  speed?: number;
  yaw?: number;
  distance?: number; // Distance au joueur (calculée)
}

export interface RadarProps {
  player: Player;
  cars: Car[];
  radius?: number; // Rayon du radar en mètres (défaut: 20)
  pixelRadius?: number; // Rayon du radar en pixels (défaut: 150)
  showLabels?: boolean;
  rotationEnabled?: boolean;
}

export interface RadarConfig {
  radius: number;
  pixelRadius: number;
  showLabels: boolean;
  rotationEnabled: boolean;
  opacity: number;
  darkMode: boolean;
}

