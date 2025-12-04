# Spécifications pour créer un radar style LMU

## Objectif

Créer un radar en temps réel similaire à celui de **Le Mans Ultimate (LMU)**, destiné à une application web (ou overlay) permettant d'afficher les voitures autour du joueur, avec un rendu propre, sombre et minimaliste.

---

## 1. Fonctionnement général du radar

* Le radar affiche **la position relative** des voitures autour du joueur dans un rayon défini (ex : 15 à 30 mètres).
* Le joueur est toujours **au centre du radar**.
* Le radar pivote dynamiquement en fonction de l'orientation du joueur (yaw).
* Les autres voitures apparaissent comme des **points, rectangles ou silhouettes simplifiées**.
* Le radar peut être rond (style LMU) ou carré (optionnel).

---

## 2. Données nécessaires

Pour chaque mise à jour (idéalement 20 Hz ou plus) :

* Position du joueur : `x`, `y`, `z`
* Orientation du joueur : `yaw`
* Pour chaque voiture autour :

  * `x`, `y`, `z`
  * Vitesse (optionnel)
  * Orientation (optionnel)
  * Classe (LMDh, GTE, LMGT3...) pour la couleur
  * Distance au joueur

---

## 3. Calcul des positions relatives

1. Calcul du vecteur relatif :

   ```text
   dx = car.x - player.x
   dy = car.y - player.y
   dz = car.z - player.z
   ```
2. Rotation inverse selon l’orientation du joueur (pour centrer le radar) :

   ```text
   x' = dx * cos(-yaw) - dy * sin(-yaw)
   y' = dx * sin(-yaw) + dy * cos(-yaw)
   ```
3. Normalisation dans la zone du radar (ex : rayon 100px = 20m cercle réel).

---

## 4. Design UI (style LMU)

* Fond : cercle semi‑transparent, noir (#0A0A0A) avec bord fin.
* Joueur : triangle blanc ou flèche minimaliste.
* Autres voitures :

  * Forme : rectangle ou point arrondi.
  * Couleur selon la classe :

    * LMDh : cyan
    * LMP2 : bleu
    * LMGT3 : vert
    * Safety car : jaune
* Éléments dynamiques :

  * Points qui deviennent plus grands si la voiture est proche.
  * Ligne de contact si voiture dangereusement proche (optionnel).

---

## 5. Options configurables

* **Mode clair / sombre**
* Rayon du radar (zoom)
* Affichage des labels (numéro voiture, classe)
* Transparence du radar
* Rotation activée / désactivée
* Animation des points (pulsation, fade‑in/out)

---

## 6. Architecture frontend

Radar en React :

* Composant `<Radar />`
* Props :

  ```ts
  interface RadarProps {
    player: { x: number; y: number; yaw: number };
    cars: Array<{ x: number; y: number; class: string }>;
    radius?: number;
  }
  ```
* Canvas HTML5 **ou** SVG pour le rendu :

  * Canvas = performance optimale
  * SVG = plus simple pour animations

---

## 7. Boucle de mise à jour

* Hook dédié : `useRadarUpdate()`
* Rafraîchissement via requestAnimationFrame pour fluidité.
* Peut recevoir les données depuis :

  * WebSocket
  * API locale
  * Plugin jeu → UDP (style iRacing/ACC)

---

## 8. Exemple de workflow computationnel

1. Réception des données brutes (UDP ou WebSocket)
2. Transformation des coordonnées
3. Filtrage : ne garder que les voitures < 30m
4. Conversion coordonnées → pixels
5. Rendu du radar
6. Boucle

---

## 9. Extensions possibles

* Détection de contacts imminents
* Highlight des voitures en dépassement
* Animation "danger" quand la distance < 2m
* Mode "espion" : zoom auto quand beaucoup de trafic
* Thèmes LMU / iRacing / ACC

---

## 10. TODO techniques

* Définir le format JSON d'entrée des données
* Définir le mapping des couleurs par classe
* Choisir Canvas ou SVG (à décider dans Cursor)
* Faire un prototype statique avant la version dynamique

## Compatibilité

* Ce radar doit impérativement fonctionner avec **iRacing**.
* La source de données principale provient de la **Mémoire Partagée iRacing** (SDK), relayée via un serveur WebSocket local.
* Toutes les positions, orientations et vitesses doivent être converties au format interne attendu par le radar.