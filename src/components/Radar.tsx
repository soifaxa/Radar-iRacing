import { useEffect, useRef } from 'react';
import { RadarProps } from '../types/radar';
import { transformToRadarCoordinates, worldToPixel } from '../utils/math';
import { CAR_CLASS_COLORS, RADAR_COLORS } from '../config/colors';

/**
 * Dessine un rectangle arrondi (compatible avec tous les navigateurs)
 */
function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  if (ctx.roundRect) {
    ctx.roundRect(x, y, width, height, radius);
  } else {
    // Fallback pour navigateurs plus anciens
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
  }
}

export function Radar({
  player,
  cars,
  radius = 20,
  pixelRadius = 150,
  showLabels = false,
  rotationEnabled = true,
}: RadarProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Taille du canvas
    const size = pixelRadius * 2;
    canvas.width = size;
    canvas.height = size;
    const centerX = pixelRadius;
    const centerY = pixelRadius;

    // Effacement du canvas
    ctx.clearRect(0, 0, size, size);

    // Fond du radar (cercle semi-transparent)
    ctx.fillStyle = RADAR_COLORS.background;
    ctx.globalAlpha = 0.9;
    ctx.beginPath();
    ctx.arc(centerX, centerY, pixelRadius, 0, Math.PI * 2);
    ctx.fill();

    // Bordure
    ctx.strokeStyle = RADAR_COLORS.border;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 1;
    ctx.stroke();

    // Grille (cercles concentriques)
    ctx.strokeStyle = RADAR_COLORS.grid;
    ctx.lineWidth = 1;
    for (let i = 1; i <= 3; i++) {
      const r = (pixelRadius * i) / 4;
      ctx.beginPath();
      ctx.arc(centerX, centerY, r, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Lignes cardinales (Nord, Sud, Est, Ouest)
    ctx.strokeStyle = RADAR_COLORS.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    // Nord
    ctx.moveTo(centerX, centerY - pixelRadius);
    ctx.lineTo(centerX, centerY + pixelRadius);
    // Est
    ctx.moveTo(centerX - pixelRadius, centerY);
    ctx.lineTo(centerX + pixelRadius, centerY);
    ctx.stroke();

    // Transformation des voitures et rendu
    cars.forEach((car) => {
      const { x, y, distance } = transformToRadarCoordinates(car, player);

      // Conversion en pixels
      const pixel = worldToPixel(x, y, radius, pixelRadius);
      const screenX = centerX + pixel.x;
      const screenY = centerY - pixel.y; // Inversion Y pour l'affichage

      // Vérifier si la voiture est dans le cercle visible
      const distFromCenter = Math.sqrt(pixel.x * pixel.x + pixel.y * pixel.y);
      if (distFromCenter > pixelRadius) return;

      // Taille du point selon la distance (plus proche = plus grand)
      const baseSize = 4;
      const sizeMultiplier = Math.max(0.5, 1 - (distance || 0) / radius);
      const pointSize = baseSize * (1 + sizeMultiplier);

      // Couleur selon la classe
      const color = CAR_CLASS_COLORS[car.class] || CAR_CLASS_COLORS.Unknown;

      // Dessin de la voiture (rectangle arrondi)
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.9;
      drawRoundedRect(
        ctx,
        screenX - pointSize,
        screenY - pointSize,
        pointSize * 2,
        pointSize * 2,
        2
      );
      ctx.fill();

      // Bordure du point
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 1;
      ctx.stroke();

      // Label (optionnel)
      if (showLabels && distance && distance < radius * 0.7) {
        ctx.fillStyle = RADAR_COLORS.text;
        ctx.font = '10px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(
          `${Math.round(distance)}m`,
          screenX,
          screenY - pointSize - 5
        );
      }
    });

    // Joueur au centre (triangle/flèche)
    ctx.fillStyle = RADAR_COLORS.player;
    ctx.globalAlpha = 1;
    ctx.beginPath();
    const playerSize = 8;
    ctx.moveTo(centerX, centerY - playerSize);
    ctx.lineTo(centerX - playerSize * 0.6, centerY + playerSize * 0.6);
    ctx.lineTo(centerX + playerSize * 0.6, centerY + playerSize * 0.6);
    ctx.closePath();
    ctx.fill();

    // Bordure du joueur
    ctx.strokeStyle = RADAR_COLORS.player;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }, [player, cars, radius, pixelRadius, showLabels, rotationEnabled]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        display: 'block',
        borderRadius: '50%',
        boxShadow: '0 0 20px rgba(0, 0, 0, 0.5)',
      }}
    />
  );
}

