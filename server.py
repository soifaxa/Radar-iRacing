"""
Serveur WebSocket pour diffuser les données de télémétrie iRacing
Lit la mémoire partagée iRacing et envoie les positions/angles via WebSocket
"""

import asyncio
import json
import math
import time
from typing import Dict, List, Optional
import websockets

try:
    import irsdk
    IRSDK_AVAILABLE = True
except ImportError:
    try:
        import pyirsdk
        irsdk = pyirsdk
        IRSDK_AVAILABLE = True
    except ImportError:
        print("⚠️  Bibliothèque irsdk/pyirsdk non trouvée.")
        print("   Installation recommandée: pip install pyirsdk")
        print("   Ou: pip install irsdk")
        IRSDK_AVAILABLE = False
        import ctypes
        from ctypes import wintypes
        import mmap

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
            print(f"Erreur lors de la liste des variables: {e}")
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
                print("✅ Connecté à iRacing")
                # Lister quelques variables clés pour débogage
                try:
                    available_vars = self.list_available_variables()
                    if available_vars:
                        car_vars = [v for v in available_vars if 'Car' in v or 'Pos' in v or 'Lap' in v][:15]
                        if car_vars:
                            print(f"📋 Variables disponibles (échantillon): {', '.join(car_vars)}")
                except:
                    pass
            else:
                print("⚠️  iRacing non détecté (assurez-vous qu'iRacing est en cours d'exécution)")
        except Exception as e:
            print(f"❌ Erreur lors de la connexion à iRacing: {e}")
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
                    # Positions X, Y, Z du joueur (en mètres)
                    # iRacing stocke les positions dans des tableaux CarIdxPosX, CarIdxPosY, CarIdxPosZ
                    pos_x = self._get_value('CarIdxPosX', None)
                    pos_y = self._get_value('CarIdxPosY', None)
                    pos_z = self._get_value('CarIdxPosZ', None)
                    
                    # Si les tableaux sont disponibles
                    if isinstance(pos_x, list) and len(pos_x) > player_car_idx:
                        x = float(pos_x[player_car_idx])
                        y = float(pos_y[player_car_idx] if isinstance(pos_y, list) and len(pos_y) > player_car_idx else 0)
                        z = float(pos_z[player_car_idx] if isinstance(pos_z, list) and len(pos_z) > player_car_idx else 0)
                    else:
                        # Fallback: utiliser CarIdxLapDistPct pour calculer une position approximative
                        lap_dist_pct = self._get_value('CarIdxLapDistPct', [])
                        track_length = self._get_value('TrackLength', 4000.0) or 4000.0
                        
                        if isinstance(lap_dist_pct, list) and len(lap_dist_pct) > player_car_idx:
                            lap_dist = float(lap_dist_pct[player_car_idx] or 0)
                            x = lap_dist * track_length  # Position sur la piste
                            y = 0.0
                            z = 0.0
                        else:
                            # Dernier recours: utiliser Speed comme approximation très basique
                            x = float(self._get_value('Speed', 0) or 0) * 0.1  # Approximation très basique
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
                    print(f"⚠️  Erreur lecture données joueur (fallback): {e}")
                    return {
                        "position": {"x": 0, "y": 0, "z": 0},
                        "yaw": 0.0
                    }
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des données joueur: {e}")
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
                
                player_x = player_pos["position"]["x"]
                player_y = player_pos["position"]["y"]
                player_z = player_pos["position"]["z"]
                
                # Récupérer les données disponibles
                # iRacing peut ne pas avoir CarIdxPosX/Y/Z directement
                # Utilisons CarIdxLapDistPct et d'autres variables disponibles
                lap_dist_pct = self._get_value('CarIdxLapDistPct', [])
                speed_array = self._get_value('CarIdxSpeed', [])
                heading = self._get_value('CarIdxHeading', [])
                track_surface = self._get_value('CarIdxTrackSurface', [])
                
                # Essayer d'obtenir les positions absolues si disponibles
                pos_x = self._get_value('CarIdxPosX', None)
                pos_y = self._get_value('CarIdxPosY', None)
                pos_z = self._get_value('CarIdxPosZ', None)
                
                # Si les positions absolues ne sont pas disponibles, utiliser une approximation
                # basée sur la distance de tour et la position du joueur
                use_lap_dist_approx = (pos_x is None or not isinstance(pos_x, list))
                
                # Afficher un message une seule fois
                if use_lap_dist_approx and not hasattr(self, '_lap_dist_warning_shown'):
                    print("⚠️  CarIdxPosX/Y/Z non disponibles, utilisation de CarIdxLapDistPct comme approximation")
                    self._lap_dist_warning_shown = True
                
                if use_lap_dist_approx:
                    # Utiliser CarIdxLapDistPct pour calculer des positions approximatives
                    if not isinstance(lap_dist_pct, list):
                        lap_dist_pct = []
                    
                    # Obtenir la distance de tour du joueur
                    player_lap_dist = 0.0
                    if isinstance(lap_dist_pct, list) and len(lap_dist_pct) > player_car_idx:
                        player_lap_dist = float(lap_dist_pct[player_car_idx] or 0)
                    
                    # Obtenir la longueur de la piste (approximation)
                    track_length = self._get_value('TrackLength', 4000.0)  # 4km par défaut
                    if track_length is None:
                        track_length = 4000.0
                
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
                        
                        # Position de la voiture
                        if use_lap_dist_approx:
                            # Utiliser CarIdxLapDistPct pour calculer une position approximative
                            if isinstance(lap_dist_pct, list) and len(lap_dist_pct) > i:
                                car_lap_dist = float(lap_dist_pct[i] or 0)
                                
                                # Calculer la position approximative basée sur la distance de tour
                                # Approximation: utiliser la distance de tour comme coordonnée X
                                # et une petite variation en Y basée sur l'index de la voiture
                                car_x = car_lap_dist * track_length  # Position sur la piste
                                car_y = (i - player_car_idx) * 5.0  # Espacement latéral approximatif (5m entre voitures)
                                car_z = 0.0  # Hauteur (approximation)
                            else:
                                continue
                        elif isinstance(pos_x, list) and len(pos_x) > i:
                            car_x = float(pos_x[i])
                            car_y = float(pos_y[i] if isinstance(pos_y, list) and len(pos_y) > i else 0)
                            car_z = float(pos_z[i] if isinstance(pos_z, list) and len(pos_z) > i else 0)
                            
                            # Vérifier que la position est valide (pas tous à zéro ou NaN)
                            if math.isnan(car_x) or math.isnan(car_y) or math.isnan(car_z):
                                continue
                        else:
                            # Pas de données de position disponibles
                            continue
                        
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
                        # Ignorer les erreurs pour cette voiture
                        continue
                
                # Log pour débogage (seulement si pas de voitures trouvées)
                if cars_added == 0 and cars_checked > 0:
                    print(f"⚠️  Aucune voiture ajoutée sur {cars_checked} vérifiées (num_cars={num_cars}, player_idx={player_car_idx})")
                    print(f"   pos_x type: {type(pos_x)}, len: {len(pos_x) if isinstance(pos_x, list) else 'N/A'}")
                
                return cars
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des données voitures: {e}")
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
            print(f"⚠️  Erreur dans get_telemetry_data: {e}")
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
    print(f"✅ Client connecté: {client_addr}")
    
    try:
        # Envoi périodique des données
        interval = 1.0 / UPDATE_RATE
        last_update = time.time()
        message_count = 0
        
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
                            print(f"📤 Message #{message_count}: {num_cars} voiture(s), joueur pos=({player_pos.get('x', 0):.2f}, {player_pos.get('y', 0):.2f}, {player_pos.get('z', 0):.2f})")
                        await websocket.send(json_data)
                    else:
                        # Envoyer des données par défaut si pas de données disponibles
                        if message_count <= 5:
                            print(f"⚠️  Pas de données iRacing disponibles (message #{message_count})")
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
                    print(f"❌ Client déconnecté: {client_addr}")
                    break
                except (ValueError, TypeError) as e:
                    print(f"⚠️  Erreur sérialisation JSON pour {client_addr}: {e}")
                    # Continuer même en cas d'erreur de sérialisation
                except Exception as e:
                    # Vérifier si c'est une erreur de connexion fermée
                    error_type = type(e).__name__
                    error_str = str(e).lower()
                    if ("ConnectionClosed" in error_type or 
                        "closed" in error_str or 
                        "going away" in error_str):
                        print(f"❌ Client déconnecté: {client_addr}")
                        break
                    print(f"⚠️  Erreur lors de l'envoi des données à {client_addr}: {e}")
                    # Continuer la boucle pour les autres erreurs
            
            # Petit délai pour éviter de surcharger le CPU
            await asyncio.sleep(0.01)
            
    except websockets.exceptions.ConnectionClosed:
        print(f"❌ Client déconnecté: {client_addr}")
    except Exception as e:
        print(f"❌ Erreur avec client {client_addr}: {e}")
        import traceback
        traceback.print_exc()


async def check_connection_periodically():
    """Vérifie périodiquement la connexion iRacing"""
    while True:
        await asyncio.sleep(5)  # Vérifier toutes les 5 secondes
        if not telemetry.is_connected():
            # Tentative de reconnexion
            telemetry.start()


async def main():
    """Fonction principale"""
    print("=" * 60)
    print("🚗 Serveur WebSocket iRacing Télémétrie")
    print("=" * 60)
    
    # Démarrage de la connexion iRacing
    telemetry.start()
    
    if not telemetry.is_connected():
        print("\n⚠️  ATTENTION: iRacing n'est pas connecté")
        print("   Le serveur démarrera mais enverra des données vides")
        print("   Assurez-vous qu'iRacing est en cours d'exécution")
        print("   Le serveur tentera de se reconnecter automatiquement\n")
    
    # Démarrage du serveur WebSocket
    print(f"🌐 Démarrage du serveur WebSocket sur le port {WEBSOCKET_PORT}...")
    print(f"📡 Fréquence de mise à jour: {UPDATE_RATE} Hz")
    print(f"🔗 Connexion: ws://localhost:{WEBSOCKET_PORT}")
    print("\nAppuyez sur Ctrl+C pour arrêter le serveur\n")
    
    # Tâche de vérification de connexion
    connection_task = asyncio.create_task(check_connection_periodically())
    
    async with websockets.serve(handle_client, "localhost", WEBSOCKET_PORT):
        try:
            await asyncio.Future()  # Exécution infinie
        except KeyboardInterrupt:
            print("\n\n⏹️  Arrêt du serveur...")
            connection_task.cancel()
            telemetry.shutdown()
            print("✅ Serveur arrêté")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Arrêt propre du serveur")
        telemetry.shutdown()

