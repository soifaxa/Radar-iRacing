/**
 * Utilitaire de logging pour écrire dans un fichier app.log
 * Fonctionne dans le navigateur (télécharge le fichier) et Node.js (écrit directement)
 */

let logBuffer: string[] = [];
const MAX_BUFFER_SIZE = 1000; // Nombre max de logs avant flush automatique
let flushInterval: number | null = null;

function formatTimestamp(): string {
  const now = new Date();
  return now.toISOString();
}

function formatLog(level: string, message: string): string {
  return `${formatTimestamp()} - ${level} - ${message}\n`;
}

function writeToFileNode(content: string): void {
  try {
    // Vérifier si on est dans Node.js
    if (typeof process !== 'undefined' && process.versions && process.versions.node) {
      const fs = require('fs');
      const path = require('path');
      const logPath = path.join(process.cwd(), 'app.log');
      fs.appendFileSync(logPath, content, 'utf8');
      return true;
    }
  } catch (e) {
    // Ignorer les erreurs
  }
  return false;
}

function flushLogs(): void {
  if (logBuffer.length === 0) return;

  const logs = logBuffer.join('');
  logBuffer = [];

  // Essayer d'écrire dans Node.js d'abord
  if (!writeToFileNode(logs)) {
    // Si on est dans le navigateur, stocker dans localStorage et télécharger périodiquement
    try {
      const existingLogs = localStorage.getItem('app_logs') || '';
      const allLogs = existingLogs + logs;
      // Limiter la taille pour éviter de saturer localStorage (max ~5MB)
      if (allLogs.length > 4 * 1024 * 1024) {
        // Garder seulement les 2 derniers MB
        const truncated = allLogs.slice(-2 * 1024 * 1024);
        localStorage.setItem('app_logs', truncated);
      } else {
        localStorage.setItem('app_logs', allLogs);
      }
    } catch (e) {
      // Si localStorage est plein, télécharger immédiatement
      downloadLog(logs);
    }
  }
}

function downloadLog(content: string): void {
  try {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `app_${Date.now()}.log`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (e) {
    // Ignorer les erreurs de téléchargement
  }
}

// Télécharger les logs stockés dans localStorage
export function downloadStoredLogs(): void {
  try {
    const storedLogs = localStorage.getItem('app_logs');
    if (storedLogs) {
      downloadLog(storedLogs);
      localStorage.removeItem('app_logs');
    }
  } catch (e) {
    // Ignorer les erreurs
  }
}

// Envoyer les logs au serveur via WebSocket (si disponible)
let wsForLogs: WebSocket | null = null;

export function setWebSocketForLogs(ws: WebSocket | null): void {
  wsForLogs = ws;
}

function sendLogToServer(formatted: string): void {
  if (wsForLogs && wsForLogs.readyState === WebSocket.OPEN) {
    try {
      wsForLogs.send(JSON.stringify({
        type: 'log',
        message: formatted.trim()
      }));
    } catch (e) {
      // Ignorer les erreurs d'envoi
    }
  }
}

export function log(level: string, message: string): void {
  const formatted = formatLog(level, message);
  
  // Afficher dans la console aussi
  if (level === 'ERROR') {
    console.error(message);
  } else if (level === 'WARN') {
    console.warn(message);
  } else {
    console.log(message);
  }

  // Ajouter au buffer
  logBuffer.push(formatted);

  // Écrire directement si on est dans Node.js
  if (typeof process !== 'undefined' && process.versions && process.versions.node) {
    writeToFileNode(formatted);
  } else {
    // Dans le navigateur, essayer d'envoyer au serveur
    sendLogToServer(formatted);
    
    // Flush périodiquement ou quand le buffer est plein
    if (logBuffer.length >= MAX_BUFFER_SIZE) {
      flushLogs();
    } else if (flushInterval === null && typeof window !== 'undefined') {
      flushInterval = window.setInterval(() => {
        if (logBuffer.length > 0) {
          flushLogs();
        }
      }, 5000); // Flush toutes les 5 secondes
    }
  }
}

export function logInfo(message: string): void {
  log('INFO', message);
}

export function logWarn(message: string): void {
  log('WARN', message);
}

export function logError(message: string): void {
  log('ERROR', message);
}

export function logDebug(message: string): void {
  log('DEBUG', message);
}

// Flush les logs avant de quitter
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    if (flushInterval !== null) {
      clearInterval(flushInterval);
    }
    flushLogs();
  });
  
  // Exposer une fonction globale pour télécharger les logs manuellement
  (window as any).downloadAppLogs = downloadStoredLogs;
}

