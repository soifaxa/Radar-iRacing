# Serveur WebSocket iRacing

Serveur Python pour lire la mémoire partagée iRacing et diffuser les données de télémétrie via WebSocket.

## 📋 Prérequis

- Python 3.8 ou supérieur
- iRacing installé et en cours d'exécution
- Bibliothèques Python (voir installation)

## 🚀 Installation

1. Installer les dépendances Python :

```bash
pip install -r requirements.txt
```

## 🎮 Utilisation

1. **Démarrer iRacing** et entrer dans une session (pratique, qualification, course)

2. **Démarrer le serveur** :

```bash
python server.py
```

Le serveur va :
- Se connecter à la mémoire partagée iRacing
- Démarrer un serveur WebSocket sur `ws://localhost:8765`
- Diffuser les données de télémétrie à 20 Hz

3. **Dans l'application radar**, activer la connexion WebSocket (décommenter dans `useRadarUpdate.ts`)

## 📡 Format des données

Le serveur envoie des messages JSON au format suivant :

```json
{
  "player": {
    "position": { "x": 0, "y": 0, "z": 0 },
    "yaw": 0.785
  },
  "cars": [
    {
      "position": { "x": 5, "y": 5, "z": 0 },
      "class": "LMDh",
      "speed": 120,
      "yaw": 0.5
    }
  ]
}
```

## ⚙️ Configuration

Vous pouvez modifier les paramètres dans `server.py` :

- `WEBSOCKET_PORT` : Port du serveur WebSocket (défaut: 8765)
- `UPDATE_RATE` : Fréquence de mise à jour en Hz (défaut: 20)

## 🔧 Dépannage

### iRacing non détecté

- Assurez-vous qu'iRacing est **en cours d'exécution**
- Vous devez être dans une **session active** (pas seulement au menu)
- Vérifiez que le SDK iRacing est activé (activé par défaut)

### Erreur d'importation `irsdk`

Si la bibliothèque `irsdk` n'est pas disponible, installez-la :

```bash
pip install irsdk
```

Ou utilisez une alternative comme `pyirsdk` :

```bash
pip install pyirsdk
```

### Port déjà utilisé

Si le port 8765 est déjà utilisé, modifiez `WEBSOCKET_PORT` dans `server.py`.

## 📝 Notes

- Le serveur doit être démarré **avant** d'ouvrir l'application radar
- Les données sont envoyées en continu tant qu'un client est connecté
- Le serveur gère automatiquement les déconnexions/reconnexions



