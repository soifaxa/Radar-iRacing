# Radar iRacing - Style LMU

Radar en temps réel style Le Mans Ultimate (LMU) pour iRacing, affichant les positions relatives des voitures autour du joueur.

## 🚀 Installation

```bash
npm install
```

## 🎮 Utilisation

### Mode développement

```bash
npm run dev
```

### Mode overlay (fenêtre transparente au-dessus du jeu)

Pour afficher uniquement le radar en tant qu'overlay transparent par-dessus le jeu :

```bash
# En développement (démarre Vite + Electron)
npm run electron:dev

# En production (après build)
npm run build
npm run electron
```

L'overlay s'affichera dans une fenêtre transparente :
- **Toujours au-dessus** des autres applications
- **Transparent** (fond invisible)
- **Positionné** en haut à droite de l'écran
- **Redimensionnable et déplaçable**
- **Fermeture** : `Ctrl+Shift+Q`

### Build de production

```bash
npm run build
```

## 📋 Fonctionnalités

- ✅ Radar circulaire avec rotation dynamique
- ✅ Affichage des voitures par classe (LMDh, LMP2, LMGT3, Safety Car)
- ✅ Couleurs distinctes par classe de voiture
- ✅ Filtrage automatique des voitures dans le rayon
- ✅ Interface sombre et minimaliste style LMU
- ✅ Contrôles configurables (rayon, taille, labels)
- ✅ Prêt pour connexion WebSocket avec serveur iRacing

## 🔌 Intégration iRacing

Le radar est conçu pour recevoir les données depuis la **Mémoire Partagée iRacing (SDK)** via un serveur WebSocket local.

### Format de données attendu

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

### Activation WebSocket

Pour activer la connexion WebSocket, décommentez les lignes dans `src/hooks/useRadarUpdate.ts` :

```typescript
// Décommenter pour activer la connexion WebSocket
const cleanup = connectWebSocket();
return cleanup;
```

### Configuration du serveur Python

Par défaut, le serveur WebSocket est attendu sur `ws://localhost:8765`.

Vous pouvez configurer l'hôte et le port du serveur Python via des variables d'environnement :

1. Créez un fichier `.env` à la racine du projet :
```bash
# Hôte du serveur Python (par défaut: localhost)
VITE_PYTHON_SERVER_HOST=localhost

# Port du serveur Python (par défaut: 8765)
VITE_PYTHON_SERVER_PORT=8765
```

2. Pour utiliser un serveur distant, modifiez `VITE_PYTHON_SERVER_HOST` :
```bash
# Exemple: serveur sur une autre machine
VITE_PYTHON_SERVER_HOST=192.168.1.100

# Ou avec un nom d'hôte
VITE_PYTHON_SERVER_HOST=iracing-server.local
```

3. Redémarrez le serveur de développement pour appliquer les changements.

La configuration est définie dans `src/config/server.ts` et peut être modifiée directement si nécessaire.

## 🎨 Personnalisation

Les couleurs et paramètres peuvent être modifiés dans :
- `src/config/colors.ts` - Couleurs des classes de voitures
- `src/components/Radar.tsx` - Rendu et style du radar
- `src/App.tsx` - Interface et contrôles

## 📝 TODO

- [ ] Intégration complète avec SDK iRacing
- [ ] Détection de contacts imminents
- [ ] Animation de pulsation pour les voitures proches
- [x] Mode overlay (toujours au-dessus)
- [ ] Thèmes supplémentaires (iRacing, ACC)

## 📄 Licence

MIT

