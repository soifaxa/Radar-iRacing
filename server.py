"""
Serveur WebSocket pour diffuser les données de télémétrie iRacing
Lit la mémoire partagée iRacing et envoie les positions/angles via WebSocket
"""

import asyncio
import json
import math
import time
import logging
from typing import Dict, List, Optional
import websockets
from datetime import datetime

try:
    import irsdk
    IRSDK_AVAILABLE = True
except ImportError:
    try:
        import pyirsdk
        irsdk = pyirsdk
        IRSDK_AVAILABLE = True
    except ImportError:
        logger.warning("Bibliothèque irsdk/pyirsdk non trouvée.")
        logger.warning("   Installation recommandée: pip install pyirsdk")
        logger.warning("   Ou: pip install irsdk")
        IRSDK_AVAILABLE = False
        import ctypes
        from ctypes import wintypes
        import mmap

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log', encoding='utf-8', mode='a'),
        logging.StreamHandler()  # Aussi afficher dans la console
    ]
)
logger = logging.getLogger(__name__)

# Configuration
WEBSOCKET_PORT = 8765
UPDATE_RATE = 20  # Hz (mises à jour par seconde)
IRACING_SHARED_MEMORY_NAME = "Local\\IRSDKMemMapFileName"

# Mapping des classes de voitures iRacing vers les classes du radar
CAR_CLASS_MAPPING = {
    # LMDh
    "HPD ARX-01c": "LMDh",
    "HPD ARX-01g": "LMDh",
    "Acura ARX-06": "LMDh",
    "BMW M Hybrid V8": "LMDh",
    "Cadillac V-Series.R": "LMDh",
    "Porsche 963": "LMDh",
    # LMP2
    "Dallara P217": "LMP2",
    "Ligier JS P217": "LMP2",
    "Oreca 07": "LMP2",
    # LMGT3
    "Aston Martin Vantage GT3": "LMGT3",
    "BMW M4 GT3": "LMGT3",
    "Corvette C8.R GT3": "LMGT3",
    "Ferrari 296 GT3": "LMGT3",
    "Ford Mustang GT3": "LMGT3",
    "Lamborghini Huracán GT3 EVO2": "LMGT3",
    "McLaren 720S GT3": "LMGT3",
    "Mercedes-AMG GT3": "LMGT3",
    "Porsche 911 GT3 R": "LMGT3",
    # Safety Car
    "Safety Car": "SafetyCar",
}


def unwrap_angle(current_angle: float, previous_angle: float) -> float:
    """
    "Unwrapp" un angle pour maintenir la continuité en évitant les discontinuités de ±π.
    Ajuste l'angle actuel pour qu'il soit le plus proche possible de l'angle précédent.
    """
    # Normaliser l'angle actuel dans [-π, π]
    while current_angle > math.pi:
        current_angle -= 2 * math.pi
    while current_angle < -math.pi:
        current_angle += 2 * math.pi
    
    # Calculer la différence
    diff = current_angle - previous_angle
    
    # Si la différence est supérieure à π, ajuster pour maintenir la continuité
    if diff > math.pi:
        current_angle -= 2 * math.pi
    elif diff < -math.pi:
        current_angle += 2 * math.pi
    
    return current_angle


class IRacingTelemetry:
    """Classe pour lire les données de télémétrie iRacing"""
    
    def __init__(self):
        self.ir = None
        self.connected = False
    
    def _get_value(self, var_name, default=None):
        """Helper pour récupérer une valeur de télémétrie (compatible avec différentes APIs)"""
        if not self.ir:
            return default
        
        try:
            # Méthode 1: pyirsdk utilise var_buffer avec accès par nom
            if hasattr(self.ir, 'var_buffer'):
                var_buffer = self.ir.var_buffer
                # pyirsdk: var_buffer est un dictionnaire ou objet avec accès par clé
                if hasattr(var_buffer, 'get'):
                    value = var_buffer.get(var_name)
                    if value is not None:
                        # pyirsdk retourne un objet Var avec .value
                        if hasattr(value, 'value'):
                            return value.value
                        return value
                # Essayer accès direct
                if hasattr(var_buffer, '__getitem__'):
                    try:
                        value = var_buffer[var_name]
                        if hasattr(value, 'value'):
                            return value.value
                        return value
                    except (KeyError, TypeError):
                        pass
                # Essayer getattr sur var_buffer
                if hasattr(var_buffer, var_name):
                    value = getattr(var_buffer, var_name)
                    if hasattr(value, 'value'):
                        return value.value
                    return value
            
            # Méthode 2: Accès direct sur l'objet ir
            if hasattr(self.ir, var_name):
                value = getattr(self.ir, var_name)
                if hasattr(value, 'value'):
                    return value.value
                if value is not None:
                    return value
            
            # Méthode 3: Accès par dictionnaire
            if hasattr(self.ir, '__getitem__'):
                try:
                    value = self.ir[var_name]
                    if hasattr(value, 'value'):
                        return value.value
                    return value
                except (KeyError, TypeError):
                    pass
            
            # Méthode 4: Méthode get() si disponible
            if hasattr(self.ir, 'get'):
                try:
                    value = self.ir.get(var_name, default)
                    if hasattr(value, 'value'):
                        return value.value
                    return value
                except Exception:
                    pass
            
            return default
        except Exception as e:
            # Ne pas afficher d'erreur pour chaque tentative
            return default
    
    def list_available_variables(self):
        """Liste toutes les variables disponibles (pour débogage)"""
        if not self.ir:
            return []
        
        variables = []
        try:
            # Essayer différentes méthodes pour lister les variables
            if hasattr(self.ir, 'var_buffer'):
                var_buffer = self.ir.var_buffer
                if hasattr(var_buffer, 'keys'):
                    variables.extend(list(var_buffer.keys()))
                elif hasattr(var_buffer, '__dict__'):
                    variables.extend(list(var_buffer.__dict__.keys()))
                elif hasattr(var_buffer, '__iter__'):
                    try:
                        variables.extend([k for k in var_buffer])
                    except:
                        pass
            
            # Essayer dir() sur l'objet ir
            if hasattr(self.ir, '__dict__'):
                variables.extend([k for k in self.ir.__dict__.keys() if not k.startswith('_')])
            
            return sorted(set(variables))
        except Exception as e:
            logger.error(f"Erreur lors de la liste des variables: {e}")
            return []
        
    def start(self):
        """Démarre la connexion à iRacing"""
        try:
            if IRSDK_AVAILABLE:
                self.ir = irsdk.IRSDK()
                self.ir.startup()
                # Vérifier la connexion périodiquement
                self.connected = self.ir.is_connected
            else:
                # Fallback avec ctypes (implémentation basique)
                self.connected = self._connect_with_ctypes()
                
            if self.connected:
                logger.info("✅ Connecté à iRacing")
                # Lister quelques variables clés pour débogage
                try:
                    available_vars = self.list_available_variables()
                    if available_vars:
                        car_vars = [v for v in available_vars if 'Car' in v or 'Pos' in v or 'Lap' in v][:15]
                        if car_vars:
                            logger.info(f"📋 Variables disponibles (échantillon): {', '.join(car_vars)}")
                except:
                    pass
            else:
                logger.warning("⚠️  iRacing non détecté (assurez-vous qu'iRacing est en cours d'exécution)")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la connexion à iRacing: {e}")
            self.connected = False
    
    def _connect_with_ctypes(self) -> bool:
        """Tentative de connexion avec ctypes (fallback)"""
        # Cette méthode nécessiterait une implémentation complète du protocole iRacing SDK
        # Pour l'instant, on retourne False et on utilise irsdk
        return False
    
    def is_connected(self) -> bool:
        """Vérifie si iRacing est connecté"""
        if self.ir and IRSDK_AVAILABLE:
            try:
                # Vérifier périodiquement la connexion
                self.connected = self.ir.is_connected
                return self.connected
            except:
                self.connected = False
                return False
        return self.connected
    
    def get_player_data(self) -> Optional[Dict]:
        """Récupère les données du joueur"""
        if not self.is_connected():
            return None
        
        try:
            if IRSDK_AVAILABLE and self.ir:
                # Index de la voiture du joueur
                player_car_idx = self._get_value('PlayerCarIdx', 0)
                if player_car_idx is None:
                    player_car_idx = 0  # Utiliser 0 par défaut
                
                try:
                    # Récupérer la position absolue du joueur pour calculer les positions relatives
                    # Les positions absolues peuvent avoir des discontinuités à la ligne médiane,
                    # mais en rendant toutes les positions relatives au joueur, les discontinuités s'annulent
                    # IMPORTANT: Toujours placer le joueur à l'origine (0,0,0) pour simplifier
                    # Toutes les positions des voitures seront relatives au joueur
                    x = 0.0
                    y = 0.0
                    z = 0.0
                    
                    # Yaw (orientation) en radians
                    # iRacing stocke le yaw dans CarIdxHeading
                    heading = self._get_value('CarIdxHeading', [])
                    if isinstance(heading, list) and len(heading) > player_car_idx:
                        yaw = float(heading[player_car_idx])
                    else:
                        # Fallback: utiliser Yaw direct
                        yaw = float(self._get_value('Yaw', 0) or 0)
                    
                    # Convertir le heading de degrés à radians si nécessaire
                    # (iRacing peut utiliser degrés ou radians selon la version)
                    if abs(yaw) > 2 * math.pi:
                        yaw = math.radians(yaw)
                    
                    return {
                        "position": {
                            "x": x,
                            "y": y,
                            "z": z
                        },
                        "yaw": yaw
                    }
                except Exception as e:
                    # Données de fallback si certaines valeurs ne sont pas disponibles
                    logger.warning(f"⚠️  Erreur lecture données joueur (fallback): {e}")
                    return {
                        "position": {"x": 0, "y": 0, "z": 0},
                        "yaw": 0.0
                    }
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des données joueur: {e}")
            # Retourner des données par défaut au lieu de None
            return {
                "position": {"x": 0, "y": 0, "z": 0},
                "yaw": 0.0
            }
    
    def get_cars_data(self) -> List[Dict]:
        """Récupère les données de toutes les voitures"""
        if not self.is_connected():
            return []
        
        try:
            if IRSDK_AVAILABLE and self.ir:
                cars = []
                num_cars = self._get_value('CarIdxCount', 64)
                if num_cars is None or num_cars == 0:
                    num_cars = 64  # Maximum par défaut
                
                player_car_idx = self._get_value('PlayerCarIdx', 0)
                if player_car_idx is None:
                    player_car_idx = 0
                
                # Position du joueur pour calculer les positions relatives
                player_pos = self.get_player_data()
                if not player_pos:
                    return []
                
                # Position absolue du joueur (pour rendre les positions des voitures relatives)
                # Le joueur est toujours à l'origine (0,0,0)
                player_x = 0.0
                player_y = 0.0
                player_z = 0.0
                
                # Récupérer les données disponibles
                # iRacing peut ne pas avoir CarIdxPosX/Y/Z directement
                # Utilisons CarIdxLapDistPct et d'autres variables disponibles
                lap_dist_pct = self._get_value('CarIdxLapDistPct', [])
                speed_array = self._get_value('CarIdxSpeed', [])
                heading = self._get_value('CarIdxHeading', [])
                track_surface = self._get_value('CarIdxTrackSurface', [])
                
                # Obtenir la longueur de la piste (nécessaire pour les approximations)
                track_length = self._get_value('TrackLength', 4000.0)  # 4km par défaut
                if track_length is None:
                    track_length = 4000.0
                
                # Essayer d'obtenir les positions absolues si disponibles
                # iRacing peut utiliser différents noms de variables selon la version
                pos_x = self._get_value('CarIdxPosX', None)
                pos_y = self._get_value('CarIdxPosY', None)
                pos_z = self._get_value('CarIdxPosZ', None)
                
                # Essayer aussi d'autres noms possibles
                if pos_x is None or not isinstance(pos_x, list):
                    pos_x = self._get_value('CarPosX', None)
                if pos_y is None or not isinstance(pos_y, list):
                    pos_y = self._get_value('CarPosY', None)
                if pos_z is None or not isinstance(pos_z, list):
                    pos_z = self._get_value('CarPosZ', None)
                
                # Vérifier si les positions sont valides (pas toutes à zéro)
                # Si les positions sont disponibles mais toutes à zéro, elles ne sont pas valides
                # IMPORTANT: On force l'utilisation des positions absolues même si elles semblent invalides
                # car on peut corriger les discontinuités avec CarIdxLapDistPct
                pos_valid = False
                if isinstance(pos_x, list) and len(pos_x) > 0:
                    # Vérifier si au moins une position n'est pas zéro
                    # On assouplit le critère : si on a des valeurs (même petites), on les utilise
                    for px in pos_x[:min(10, len(pos_x))]:  # Vérifier les 10 premières
                        if px is not None:
                            px_val = float(px or 0)
                            # Accepter même de très petites valeurs (peut être une piste proche de l'origine)
                            if abs(px_val) > 0.001:  # Seuil très bas
                                pos_valid = True
                                break
                    # Si aucune position n'est > 0.001, vérifier si on a au moins des valeurs non-null
                    if not pos_valid:
                        non_null_count = sum(1 for px in pos_x[:min(10, len(pos_x))] if px is not None)
                        if non_null_count > 0:
                            # On a des valeurs, même si elles sont proches de zéro, on les utilise
                            pos_valid = True
                            logger.warning("⚠️  Positions absolues proches de zéro, utilisation quand même avec correction des discontinuités")
                    
                    # DEBUG: Logger quelques valeurs pour comprendre pourquoi elles ne sont pas utilisées
                    if not pos_valid and len(pos_x) > 0:
                        sample_values = [float(px or 0) for px in pos_x[:min(5, len(pos_x))] if px is not None]
                        logger.debug(f"🔍 DEBUG positions: sample_values={sample_values}, pos_valid={pos_valid}")
                
                # Utiliser les positions absolues si disponibles, mais les rendre relatives au joueur
                # et détecter/corriger les discontinuités à la ligne médiane en utilisant CarIdxLapDistPct
                # IMPORTANT: On force l'utilisation des positions absolues si elles existent, même si elles semblent invalides
                # car on peut corriger les discontinuités avec CarIdxLapDistPct
                use_absolute_positions = isinstance(pos_x, list) and isinstance(pos_y, list) and isinstance(pos_z, list) and len(pos_x) > 0
                
                # Afficher un message une seule fois
                if not hasattr(self, '_position_method_shown'):
                    if use_absolute_positions:
                        logger.info("✅ Utilisation des positions absolues CarIdxPosX/Y/Z (corrigées pour éviter les discontinuités)")
                    else:
                        logger.warning("⚠️  Positions absolues non disponibles, utilisation de CarIdxLapDistPct (approximation)")
                    logger.info("✅ Le joueur est placé à l'origine (0, 0, 0) comme référence")
                    self._position_method_shown = True
                
                # Utiliser CarIdxLapDistPct pour détecter les discontinuités
                if not isinstance(lap_dist_pct, list):
                    lap_dist_pct = []
                
                # Stocker les distances précédentes pour détecter les discontinuités
                if not hasattr(self, '_previous_lap_dist'):
                    self._previous_lap_dist = {}
                # Stocker les positions précédentes pour détecter les sauts discontinus
                if not hasattr(self, '_previous_car_positions'):
                    self._previous_car_positions = {}
                
                # Classe de voiture du joueur (pour déterminer les autres)
                player_car_class = self._get_value('CarClass', 'Unknown')
                
                cars_checked = 0
                cars_added = 0
                
                for i in range(min(num_cars, 64)):  # Maximum 64 voitures
                    if i == player_car_idx:
                        continue  # Ignorer le joueur
                    
                    cars_checked += 1
                    
                    try:
                        # Vérifier si la voiture est valide et sur la piste
                        # NOTE: On assouplit cette vérification car elle peut être trop restrictive
                        if isinstance(track_surface, list) and len(track_surface) > i:
                            surface = track_surface[i]
                            # Ignorer seulement si surface est explicitement invalide (None ou très négatif)
                            if surface is None or (isinstance(surface, (int, float)) and surface < -10):
                                continue
                        
                        # NOUVELLE APPROCHE : Utiliser les positions absolues pour l'angle, CarIdxLapDistPct pour valider
                        # Initialiser les variables par défaut
                        car_x = 0.0
                        car_y = 0.0
                        car_z = 0.0
                        current_relative_angle = 0.0
                        distance_from_abs = 0.0
                        # Calculer l'angle relatif à partir des positions absolues (avec unwrapping)
                        # Utiliser CarIdxLapDistPct pour valider la cohérence et détecter les discontinuités
                        
                        # Récupérer les positions absolues si disponibles
                        car_x_abs = 0.0
                        car_y_abs = 0.0
                        car_z_abs = 0.0
                        if use_absolute_positions and len(pos_x) > i and len(pos_y) > i and len(pos_z) > i:
                            car_x_abs = float(pos_x[i] or 0)
                            car_y_abs = float(pos_y[i] or 0)
                            car_z_abs = float(pos_z[i] or 0)
                        
                        # Calculer les positions relatives au joueur
                        car_x_relative = car_x_abs - player_x
                        car_y_relative = car_y_abs - player_y
                        car_z_relative = car_z_abs - player_z
                        
                        # Calculer la distance et l'angle à partir des positions absolues
                        distance_from_abs = math.sqrt(car_x_relative * car_x_relative + car_y_relative * car_y_relative)
                        angle_from_abs = math.atan2(car_y_relative, car_x_relative) if distance_from_abs > 0.001 else 0.0
                        
                        # Récupérer CarIdxLapDistPct pour validation
                        current_lap_dist = float(lap_dist_pct[i] or 0) if isinstance(lap_dist_pct, list) and len(lap_dist_pct) > i else 0.0
                        player_lap_dist = float(lap_dist_pct[player_car_idx] or 0) if isinstance(lap_dist_pct, list) and len(lap_dist_pct) > player_car_idx else 0.0
                        
                        # Calculer la distance le long de la piste
                        lap_dist_diff = current_lap_dist - player_lap_dist
                        if lap_dist_diff > 0.5:
                            lap_dist_diff -= 1.0
                        elif lap_dist_diff < -0.5:
                            lap_dist_diff += 1.0
                        distance_along_track = lap_dist_diff * track_length
                        
                        # Initialiser current_relative_angle par défaut
                        current_relative_angle = angle_from_abs if use_absolute_positions and distance_from_abs > 0.001 else 0.0
                        
                        # Obtenir les données précédentes
                        previous_pos = self._previous_car_positions.get(i)
                        previous_lap_dist = self._previous_lap_dist.get(i)
                        
                        # Calculer l'angle relatif avec unwrapping pour éviter les discontinuités
                        if use_absolute_positions and distance_from_abs > 0.001:
                            # Utiliser les positions absolues si disponibles
                            if previous_pos is not None and isinstance(previous_pos, dict):
                                prev_relative_angle = previous_pos.get("relative_angle", angle_from_abs)
                                prev_distance_abs = previous_pos.get("distance_abs", distance_from_abs)
                                prev_x = previous_pos.get("x", 0.0)
                                prev_y = previous_pos.get("y", 0.0)
                                
                                # Détecter les discontinuités de manière plus robuste
                                # 1. Changement de distance absolue
                                distance_change_abs = abs(distance_from_abs - prev_distance_abs)
                                
                                # 2. Changement de lap_dist (normalisé)
                                lap_dist_change = abs(current_lap_dist - previous_lap_dist) if previous_lap_dist is not None else 0.0
                                if lap_dist_change > 0.5:
                                    lap_dist_change = 1.0 - lap_dist_change
                                
                                # 3. Changement de signe dans les positions (typique des discontinuités à la ligne médiane)
                                sign_change_x = (prev_x > 0) != (car_x_relative > 0) if abs(prev_x) > 0.1 and abs(car_x_relative) > 0.1 else False
                                sign_change_y = (prev_y > 0) != (car_y_relative > 0) if abs(prev_y) > 0.1 and abs(car_y_relative) > 0.1 else False
                                has_sign_change = sign_change_x or sign_change_y
                                
                                # 4. Changement d'angle (normalisé)
                                angle_change = angle_from_abs - prev_relative_angle
                                while angle_change > math.pi:
                                    angle_change -= 2 * math.pi
                                while angle_change < -math.pi:
                                    angle_change += 2 * math.pi
                                angle_change_abs = abs(angle_change)
                                
                                # Détecter une discontinuité si :
                                # - La distance absolue change beaucoup (> 10m) ET la distance le long de la piste change peu (< 0.02)
                                # OU - Il y a un changement de signe ET la distance change beaucoup (> 5m)
                                # OU - L'angle change beaucoup (> π/3 = 60°) ET la distance absolue change beaucoup
                                is_discontinuity = (
                                    (distance_change_abs > 10.0 and lap_dist_change < 0.02) or
                                    (has_sign_change and distance_change_abs > 5.0) or
                                    (angle_change_abs > math.pi / 3 and distance_change_abs > 10.0)
                                )
                                
                                if is_discontinuity:
                                    # Discontinuité détectée : garder l'angle précédent et utiliser distance_along_track
                                    current_relative_angle = prev_relative_angle
                                    # Utiliser la distance le long de la piste (continue) pour la position
                                    car_x = distance_along_track * math.cos(current_relative_angle)
                                    car_y = distance_along_track * math.sin(current_relative_angle)
                                else:
                                    # Pas de discontinuité : unwrapp l'angle et utiliser les positions absolues
                                    current_relative_angle = unwrap_angle(angle_from_abs, prev_relative_angle)
                                    car_x = car_x_relative
                                    car_y = car_y_relative
                            else:
                                # Première frame : utiliser les positions absolues directement
                                current_relative_angle = angle_from_abs
                                car_x = car_x_relative
                                car_y = car_y_relative
                            
                            car_z = car_z_relative
                        else:
                            # Fallback : utiliser CarIdxLapDistPct si les positions absolues ne sont pas disponibles
                            # APPROCHE AMÉLIORÉE : Utiliser un angle relatif continu pour chaque voiture
                            # au lieu de supposer qu'elles sont alignées avec le joueur
                            player_heading = player_pos.get("yaw", 0.0)
                            
                            # Détecter les discontinuités dans lap_dist_diff
                            # Quand une voiture traverse la ligne médiane, lap_dist_diff peut sauter de ~0.5 à ~-0.5
                            lap_dist_discontinuity = False
                            prev_lap_dist_diff_normalized = None
                            prev_distance_along_track = None
                            if previous_lap_dist is not None:
                                prev_lap_dist_diff = previous_lap_dist - player_lap_dist
                                prev_lap_dist_diff_normalized = prev_lap_dist_diff
                                if prev_lap_dist_diff_normalized > 0.5:
                                    prev_lap_dist_diff_normalized -= 1.0
                                elif prev_lap_dist_diff_normalized < -0.5:
                                    prev_lap_dist_diff_normalized += 1.0
                                
                                # Calculer la distance précédente le long de la piste
                                prev_distance_along_track = prev_lap_dist_diff_normalized * track_length
                                
                                # Si le changement de lap_dist_diff est très grand (> 0.8), c'est une discontinuité
                                lap_dist_diff_change = abs(lap_dist_diff - prev_lap_dist_diff_normalized)
                                if lap_dist_diff_change > 0.8:
                                    lap_dist_discontinuity = True
                                
                                # Aussi détecter si distance_along_track change brutalement de signe ET de magnitude
                                # (saut de +30m à -30m par exemple)
                                if prev_distance_along_track is not None:
                                    distance_change = abs(distance_along_track - prev_distance_along_track)
                                    # Si la distance change de plus de 50m en une frame, c'est probablement une discontinuité
                                    if distance_change > 50.0:
                                        lap_dist_discontinuity = True
                            
                            if previous_pos is not None and isinstance(previous_pos, dict):
                                prev_relative_angle = previous_pos.get("relative_angle", 0.0)
                                prev_x = previous_pos.get("x", 0.0)
                                prev_y = previous_pos.get("y", 0.0)
                                prev_distance_along_track = previous_pos.get("distance_along_track", distance_along_track)
                                
                                # Si discontinuité détectée, préserver l'angle précédent
                                if lap_dist_discontinuity:
                                    # Garder l'angle précédent pour éviter les sauts
                                    current_relative_angle = prev_relative_angle
                                    # Utiliser la distance le long de la piste (continue) pour la position
                                    car_x = distance_along_track * math.cos(current_relative_angle)
                                    car_y = distance_along_track * math.sin(current_relative_angle)
                                    # Logger la discontinuité pour debug
                                    if prev_lap_dist_diff_normalized is not None:
                                        logger.debug(f"⚠️ Discontinuité lap_dist détectée pour voiture {i}: lap_dist_diff={lap_dist_diff:.3f}, prev={prev_lap_dist_diff_normalized:.3f}, angle préservé={current_relative_angle:.3f}")
                                else:
                                    # Pas de discontinuité : MAINTAIN l'angle relatif précédent (unwrapped)
                                    # IMPORTANT: Ne pas ajuster l'angle vers player_heading car cela crée des trajectoires bizarres
                                    # L'angle relatif doit rester constant pour maintenir la continuité de la trajectoire
                                    
                                    # Utiliser directement l'angle précédent (qui est déjà unwrapped et continu)
                                    current_relative_angle = prev_relative_angle
                                    
                                    # Utiliser la distance précédente si elle existe pour éviter les sauts
                                    # Si prev_distance_along_track existe et est proche de distance_along_track,
                                    # utiliser une interpolation pour lisser la transition
                                    if prev_distance_along_track is not None:
                                        # Si le changement est petit (< 5m), utiliser la nouvelle distance
                                        # Sinon, interpoler pour éviter les sauts
                                        distance_change = abs(distance_along_track - prev_distance_along_track)
                                        if distance_change > 5.0:
                                            # Interpoler pour lisser le changement
                                            smoothing_factor = 0.3  # Utiliser 30% de la nouvelle valeur, 70% de l'ancienne
                                            smoothed_distance = prev_distance_along_track * (1 - smoothing_factor) + distance_along_track * smoothing_factor
                                            car_x = smoothed_distance * math.cos(current_relative_angle)
                                            car_y = smoothed_distance * math.sin(current_relative_angle)
                                        else:
                                            # Changement petit, utiliser directement
                                            car_x = distance_along_track * math.cos(current_relative_angle)
                                            car_y = distance_along_track * math.sin(current_relative_angle)
                                    else:
                                        # Première fois, utiliser directement
                                        car_x = distance_along_track * math.cos(current_relative_angle)
                                        car_y = distance_along_track * math.sin(current_relative_angle)
                            else:
                                # Première frame : utiliser la direction du joueur
                                if distance_along_track >= 0:
                                    current_relative_angle = player_heading
                                else:
                                    current_relative_angle = player_heading + math.pi
                                
                                car_x = distance_along_track * math.cos(current_relative_angle)
                                car_y = distance_along_track * math.sin(current_relative_angle)
                            
                            car_z = 0.0
                            distance_from_abs = abs(distance_along_track)
                        
                        # Mettre à jour les données précédentes
                        self._previous_lap_dist[i] = current_lap_dist
                        self._previous_car_positions[i] = {
                            "x": car_x,
                            "y": car_y,
                            "relative_angle": current_relative_angle,
                            "distance_abs": distance_from_abs,
                            "distance_along_track": distance_along_track  # Stocker aussi pour détecter les discontinuités
                        }
                        
                        # Position ABSOLUE de la voiture (pas relative)
                        # Le client calculera les positions relatives pour le radar
                        
                        # Yaw (orientation) en radians
                        if isinstance(heading, list) and len(heading) > i:
                            yaw = float(heading[i])
                            # Convertir de degrés à radians si nécessaire
                            if abs(yaw) > 2 * math.pi:
                                yaw = math.radians(yaw)
                        else:
                            yaw = 0.0
                        
                        # Vitesse en m/s
                        if isinstance(speed_array, list) and len(speed_array) > i:
                            speed_ms = float(speed_array[i] or 0)
                        else:
                            speed_ms = 0.0
                        
                        # Classe de voiture
                        # Note: iRacing peut avoir différentes classes par voiture
                        # Pour simplifier, on utilise la classe du joueur ou on essaie de la détecter
                        car_class = CAR_CLASS_MAPPING.get(player_car_class, "Unknown")
                        # TODO: Améliorer la détection de classe par voiture
                        
                        cars.append({
                            "position": {
                                "x": car_x,  # Position absolue
                                "y": car_y,  # Position absolue
                                "z": car_z   # Position absolue
                            },
                            "class": car_class,
                            "speed": float(speed_ms * 3.6),  # Conversion m/s vers km/h
                            "yaw": yaw
                        })
                        cars_added += 1
                    except Exception as e:
                        # Logger les erreurs pour débogage
                        if cars_added == 0 and cars_checked == 1:
                            logger.error(f"⚠️  Erreur lors du traitement de la première voiture: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                        continue
                
                # Log pour débogage (seulement si pas de voitures trouvées)
                if cars_added == 0 and cars_checked > 0:
                    logger.warning(f"⚠️  Aucune voiture ajoutée sur {cars_checked} vérifiées (num_cars={num_cars}, player_idx={player_car_idx})")
                    logger.warning(f"   pos_x type: {type(pos_x)}, len: {len(pos_x) if isinstance(pos_x, list) else 'N/A'}")
                
                return cars
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des données voitures: {e}")
            return []
        
        return []
    
    def get_telemetry_data(self) -> Optional[Dict]:
        """Récupère toutes les données de télémétrie formatées"""
        if not self.is_connected():
            # Retourner des données par défaut si pas connecté
            return {
                "player": {
                    "position": {"x": 0, "y": 0, "z": 0},
                    "yaw": 0.0
                },
                "cars": []
            }
        
        try:
            player = self.get_player_data()
            if not player:
                # Retourner des données par défaut si pas de données joueur
                return {
                    "player": {
                        "position": {"x": 0, "y": 0, "z": 0},
                        "yaw": 0.0
                    },
                    "cars": []
                }
            
            cars = self.get_cars_data()
            
            return {
                "player": player,
                "cars": cars
            }
        except Exception as e:
            logger.error(f"⚠️  Erreur dans get_telemetry_data: {e}")
            # Retourner des données par défaut en cas d'erreur
            return {
                "player": {
                    "position": {"x": 0, "y": 0, "z": 0},
                    "yaw": 0.0
                },
                "cars": []
            }
    
    def shutdown(self):
        """Ferme la connexion"""
        if self.ir and IRSDK_AVAILABLE:
            try:
                self.ir.shutdown()
            except:
                pass
        self.connected = False


# Instance globale de télémétrie
telemetry = IRacingTelemetry()


def clean_data_for_json(data):
    """Nettoie les données pour la sérialisation JSON (remplace NaN, inf, etc.)"""
    import math
    
    if isinstance(data, dict):
        return {k: clean_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data_for_json(item) for item in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return 0.0
        return data
    elif isinstance(data, (int, str, bool)) or data is None:
        return data
    else:
        # Convertir en string si c'est un type non sérialisable
        return str(data)


async def handle_client(websocket):
    """Gère les connexions WebSocket clients"""
    client_addr = websocket.remote_address
    logger.info(f"✅ Client connecté: {client_addr}")
    
    try:
        # Envoi périodique des données
        interval = 1.0 / UPDATE_RATE
        last_update = time.time()
        message_count = 0
        
        # Gérer les messages entrants (logs du client)
        async def receive_messages():
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if data.get('type') == 'log':
                            # Écrire le log du client dans app.log
                            log_message = data.get('message', '')
                            with open('app.log', 'a', encoding='utf-8') as f:
                                f.write(log_message + '\n')
                    except (json.JSONDecodeError, KeyError):
                        pass  # Ignorer les messages non valides
            except websockets.exceptions.ConnectionClosed:
                pass
        
        # Démarrer la réception des messages en arrière-plan
        receive_task = asyncio.create_task(receive_messages())
        
        while True:
            current_time = time.time()
            elapsed = current_time - last_update
            
            if elapsed >= interval:
                try:
                    data = telemetry.get_telemetry_data()
                    
                    if data:
                        # Nettoyer les données avant sérialisation
                        cleaned_data = clean_data_for_json(data)
                        # S'assurer que les données sont valides avant envoi
                        json_data = json.dumps(cleaned_data)
                        message_count += 1
                        # Log détaillé pour les 10 premiers messages
                        if message_count <= 10:
                            num_cars = len(cleaned_data.get('cars', []))
                            player_pos = cleaned_data.get('player', {}).get('position', {})
                            logger.debug(f"📤 Message #{message_count}: {num_cars} voiture(s), joueur pos=({player_pos.get('x', 0):.2f}, {player_pos.get('y', 0):.2f}, {player_pos.get('z', 0):.2f})")
                        await websocket.send(json_data)
                    else:
                        # Envoyer des données par défaut si pas de données disponibles
                        if message_count <= 5:
                            logger.warning(f"⚠️  Pas de données iRacing disponibles (message #{message_count})")
                        default_data = {
                            "player": {
                                "position": {"x": 0, "y": 0, "z": 0},
                                "yaw": 0.0
                            },
                            "cars": []
                        }
                        await websocket.send(json.dumps(default_data))
                    
                    last_update = current_time
                except (websockets.exceptions.ConnectionClosed, 
                        websockets.exceptions.ConnectionClosedOK,
                        websockets.exceptions.ConnectionClosedError) as e:
                    # Connexion fermée, sortir de la boucle
                    logger.info(f"❌ Client déconnecté: {client_addr}")
                    break
                except (ValueError, TypeError) as e:
                    logger.error(f"⚠️  Erreur sérialisation JSON pour {client_addr}: {e}")
                    # Continuer même en cas d'erreur de sérialisation
                except Exception as e:
                    # Vérifier si c'est une erreur de connexion fermée
                    error_type = type(e).__name__
                    error_str = str(e).lower()
                    if ("ConnectionClosed" in error_type or 
                        "closed" in error_str or 
                        "going away" in error_str):
                        logger.info(f"❌ Client déconnecté: {client_addr}")
                        break
                    logger.error(f"⚠️  Erreur lors de l'envoi des données à {client_addr}: {e}")
                    # Continuer la boucle pour les autres erreurs
            
            # Petit délai pour éviter de surcharger le CPU
            await asyncio.sleep(0.01)
            
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"❌ Client déconnecté: {client_addr}")
    except Exception as e:
        logger.error(f"❌ Erreur avec client {client_addr}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Annuler la tâche de réception si elle existe
        if 'receive_task' in locals():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass


async def check_connection_periodically():
    """Vérifie périodiquement la connexion iRacing"""
    while True:
        await asyncio.sleep(5)  # Vérifier toutes les 5 secondes
        if not telemetry.is_connected():
            # Tentative de reconnexion
            telemetry.start()


async def main():
    """Fonction principale"""
    logger.info("=" * 60)
    logger.info("🚗 Serveur WebSocket iRacing Télémétrie")
    logger.info("=" * 60)
    
    # Démarrage de la connexion iRacing
    telemetry.start()
    
    if not telemetry.is_connected():
        logger.warning("\n⚠️  ATTENTION: iRacing n'est pas connecté")
        logger.warning("   Le serveur démarrera mais enverra des données vides")
        logger.warning("   Assurez-vous qu'iRacing est en cours d'exécution")
        logger.warning("   Le serveur tentera de se reconnecter automatiquement\n")
    
    # Démarrage du serveur WebSocket
    logger.info(f"🌐 Démarrage du serveur WebSocket sur le port {WEBSOCKET_PORT}...")
    logger.info(f"📡 Fréquence de mise à jour: {UPDATE_RATE} Hz")
    logger.info(f"🔗 Connexion: ws://0.0.0.0:{WEBSOCKET_PORT} (accessible depuis toutes les interfaces réseau)")
    logger.info("\nAppuyez sur Ctrl+C pour arrêter le serveur\n")
    
    # Tâche de vérification de connexion
    connection_task = asyncio.create_task(check_connection_periodically())
    
    async with websockets.serve(handle_client, "0.0.0.0", WEBSOCKET_PORT):
        try:
            await asyncio.Future()  # Exécution infinie
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Arrêt du serveur...")
            connection_task.cancel()
            telemetry.shutdown()
            logger.info("✅ Serveur arrêté")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n✅ Arrêt propre du serveur")
        telemetry.shutdown()

