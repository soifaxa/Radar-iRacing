// Preload script pour Electron
// Permet d'exposer des APIs sécurisées au renderer

const { contextBridge } = require('electron');

// Exposer des APIs sécurisées si nécessaire
contextBridge.exposeInMainWorld('electronAPI', {
  // Ajouter des APIs ici si nécessaire
});

