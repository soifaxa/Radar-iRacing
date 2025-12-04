const { app, BrowserWindow, screen } = require('electron');
const path = require('path');
const fs = require('fs');

// Garder une référence globale de la fenêtre
let overlayWindow = null;

// Chemin du fichier de configuration
const configPath = path.join(app.getPath('userData'), 'overlay-config.json');

// Charger la configuration sauvegardée
function loadConfig() {
  try {
    if (fs.existsSync(configPath)) {
      const data = fs.readFileSync(configPath, 'utf8');
      return JSON.parse(data);
    }
  } catch (error) {
    console.error('Erreur lors du chargement de la config:', error);
  }
  return null;
}

// Sauvegarder la configuration
function saveConfig(config) {
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
  } catch (error) {
    console.error('Erreur lors de la sauvegarde de la config:', error);
  }
}

function createOverlayWindow() {
  // Obtenir les dimensions de l'écran principal
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;

  // Charger la configuration sauvegardée ou utiliser les valeurs par défaut
  const savedConfig = loadConfig();
  const defaultWidth = 350;
  const defaultHeight = 350;
  const defaultX = (width - defaultWidth) / 2; // Centré en largeur
  const defaultY = (height - defaultHeight) / 2 - 200; // Bien plus haut que le centre pour éviter le pare-brise

  // Créer la fenêtre overlay
  overlayWindow = new BrowserWindow({
    width: savedConfig?.width || defaultWidth,
    height: savedConfig?.height || defaultHeight,
    x: savedConfig?.x ?? defaultX, // Position X (utilise ?? pour gérer 0)
    y: savedConfig?.y ?? defaultY, // Position Y
    frame: false, // Pas de barre de titre
    transparent: true, // Fond transparent
    alwaysOnTop: true, // Toujours au-dessus
    skipTaskbar: true, // Ne pas afficher dans la barre des tâches
    resizable: true, // Permettre le redimensionnement
    movable: true, // Permettre le déplacement
    focusable: false, // Ne pas prendre le focus (pour ne pas interférer avec le jeu)
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  });

  // Charger l'application overlay
  // En développement, charger depuis le serveur Vite
  // En production, charger depuis les fichiers buildés
  const isDev = !app.isPackaged;
  
  if (isDev) {
    overlayWindow.loadURL('http://localhost:5173/overlay.html');
    // Ouvrir les DevTools en développement (optionnel)
    // overlayWindow.webContents.openDevTools();
  } else {
    overlayWindow.loadFile(path.join(__dirname, '../dist/overlay.html'));
  }

  // Permettre de cliquer à travers la fenêtre sauf sur le radar
  overlayWindow.setIgnoreMouseEvents(false, { forward: true });

  // Sauvegarder la position et la taille quand la fenêtre est déplacée ou redimensionnée
  overlayWindow.on('moved', () => {
    if (overlayWindow) {
      const bounds = overlayWindow.getBounds();
      saveConfig({
        x: bounds.x,
        y: bounds.y,
        width: bounds.width,
        height: bounds.height,
      });
    }
  });

  overlayWindow.on('resized', () => {
    if (overlayWindow) {
      const bounds = overlayWindow.getBounds();
      saveConfig({
        x: bounds.x,
        y: bounds.y,
        width: bounds.width,
        height: bounds.height,
      });
    }
  });

  overlayWindow.on('closed', () => {
    overlayWindow = null;
  });

  // Permettre de fermer avec Ctrl+Shift+Q (ou autre raccourci)
  overlayWindow.webContents.on('before-input-event', (event, input) => {
    if (input.control && input.shift && input.key.toLowerCase() === 'q') {
      overlayWindow?.close();
    }
    // Réinitialiser la position avec Ctrl+Shift+R
    if (input.control && input.shift && input.key.toLowerCase() === 'r') {
      if (fs.existsSync(configPath)) {
        fs.unlinkSync(configPath);
      }
      overlayWindow?.reload();
    }
  });
}

// Cette méthode sera appelée quand Electron aura fini de s'initialiser
app.whenReady().then(() => {
  createOverlayWindow();

  app.on('activate', () => {
    // Sur macOS, recréer la fenêtre quand l'icône du dock est cliquée
    if (BrowserWindow.getAllWindows().length === 0) {
      createOverlayWindow();
    }
  });
});

// Quitter quand toutes les fenêtres sont fermées
app.on('window-all-closed', () => {
  // Sur macOS, les applications restent actives même sans fenêtres
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

