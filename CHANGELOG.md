# Changelog

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère à [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.2] - 2025-12-04

### Ajouté
- **Sauvegarde automatique de la position et de la taille de l'overlay**
  - La position et la taille de la fenêtre overlay sont sauvegardées automatiquement
  - Restauration automatique de la position au prochain lancement
  - Raccourci `Ctrl+Shift+R` pour réinitialiser la position sauvegardée

### Modifié
- **Position par défaut de l'overlay** : centré horizontalement et positionné au-dessus du pare-brise
- Amélioration de la détection du mode développement pour Electron

## [0.0.1] - 2025-12-04

### Ajouté
- Radar en temps réel style LMU pour iRacing
- Affichage des voitures autour du joueur dans un rayon configurable
- Support des classes de voitures (LMDh, LMP2, LMGT3, SafetyCar)
- Rotation dynamique du radar selon l'orientation du joueur
- Système de logging côté client et serveur
- Détection et correction des discontinuités à la ligne médiane
- Utilisation de `CarIdxLapDistPct` pour la continuité des positions
- Filtrage des voitures par distance
- Interface utilisateur avec grille et lignes cardinales
- **Mode overlay Electron** : fenêtre transparente toujours au-dessus du jeu
  - Affichage uniquement du radar (sans contrôles)
  - Fenêtre redimensionnable et déplaçable
  - Fond transparent pour ne pas masquer le jeu
  - Indicateur de connexion visuel
  - Fermeture avec `Ctrl+Shift+Q`

### Technique
- Connexion WebSocket entre le client React et le serveur Python
- Intégration avec l'API iRacing SDK (pyirsdk)
- Transformation des coordonnées iRacing vers le référentiel du radar
- Système d'angle "unwrapping" pour éviter les discontinuités
- Gestion des positions relatives avec le joueur à l'origine

