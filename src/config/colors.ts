import { CarClass } from '../types/radar';

export const CAR_CLASS_COLORS: Record<CarClass, string> = {
  LMDh: '#FF0000', // Rouge
  LMP2: '#0080FF', // Bleu
  LMGT3: '#00FF00', // Vert
  SafetyCar: '#FFFF00', // Jaune
  Unknown: '#FFFFFF', // Blanc
};

export const RADAR_COLORS = {
  background: '#0A0A0A',
  border: '#333333',
  player: '#FFFFFF',
  grid: '#1A1A1A',
  text: '#CCCCCC',
} as const;

