/**
 * Configuration du serveur Python
 */
export const SERVER_CONFIG = {
  // Hôte du serveur Python WebSocket
  // Par défaut: localhost (pour développement local)
  // Peut être changé pour une IP distante ou un nom d'hôte
  host: import.meta.env.VITE_PYTHON_SERVER_HOST || 'localhost',
  
  // Port du serveur Python WebSocket
  port: import.meta.env.VITE_PYTHON_SERVER_PORT || '8765',
  
  // URL complète du serveur WebSocket
  get websocketUrl(): string {
    return `ws://${this.host}:${this.port}`;
  },
};


