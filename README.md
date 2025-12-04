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

Par défaut, le serveur WebSocket est attendu sur `ws://localhost:8765`.

## 🎨 Personnalisation

Les couleurs et paramètres peuvent être modifiés dans :
- `src/config/colors.ts` - Couleurs des classes de voitures
- `src/components/Radar.tsx` - Rendu et style du radar
- `src/App.tsx` - Interface et contrôles

## 📝 TODO

- [ ] Intégration complète avec SDK iRacing
- [ ] Détection de contacts imminents
- [ ] Animation de pulsation pour les voitures proches
- [ ] Mode overlay (toujours au-dessus)
- [ ] Thèmes supplémentaires (iRacing, ACC)

## 📄 Licence

MIT

