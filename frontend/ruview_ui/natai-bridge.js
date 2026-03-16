/**
 * RuView-NATai Bridge Adapter
 * 
 * This script bridges the RuView UI with NATai's WiFi sensing backend.
 * It intercepts RuView's API calls and redirects them to NATai's endpoints.
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        nataiApi: window.location.origin,
        ruviewApi: window.location.origin + '/ruview-api',
        wsEndpoint: (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + window.location.host + '/wifi/ws',
        debug: true
    };

    // Logger
    const log = {
        debug: (...args) => CONFIG.debug && console.log('[RuView-Bridge]', ...args),
        info: (...args) => console.info('[RuView-Bridge]', ...args),
        warn: (...args) => console.warn('[RuView-Bridge]', ...args),
        error: (...args) => console.error('[RuView-Bridge]', ...args)
    };

    /**
     * API Adapter - Translates between RuView API format and NATai format
     */
    class APIAdapter {
        constructor() {
            this.websocket = null;
            this.reconnectAttempts = 0;
            this.maxReconnectAttempts = 5;
            this.callbacks = new Map();
        }

        /**
         * Initialize WebSocket connection to NATai backend
         */
        connectWebSocket() {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                log.debug('WebSocket already connected');
                return Promise.resolve();
            }

            return new Promise((resolve, reject) => {
                try {
                    log.info('Connecting to NATai WiFi sensing WebSocket:', CONFIG.wsEndpoint);
                    this.websocket = new WebSocket(CONFIG.wsEndpoint);

                    this.websocket.onopen = () => {
                        log.info('WebSocket connected successfully');
                        this.reconnectAttempts = 0;
                        this.triggerCallback('connected', { status: 'connected' });
                        resolve();
                    };

                    this.websocket.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);
                            log.debug('Received WebSocket message:', data.type);
                            this.handleMessage(data);
                        } catch (error) {
                            log.error('Failed to parse WebSocket message:', error);
                        }
                    };

                    this.websocket.onerror = (error) => {
                        log.error('WebSocket error:', error);
                        this.triggerCallback('error', { error: error.message });
                        reject(error);
                    };

                    this.websocket.onclose = () => {
                        log.warn('WebSocket disconnected');
                        this.triggerCallback('disconnected', {});
                        
                        // Auto-reconnect
                        if (this.reconnectAttempts < this.maxReconnectAttempts) {
                            this.reconnectAttempts++;
                            log.info(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
                            setTimeout(() => this.connectWebSocket(), 3000);
                        }
                    };

                } catch (error) {
                    log.error('Failed to create WebSocket:', error);
                    reject(error);
                }
            });
        }

        /**
         * Handle incoming WebSocket messages
         */
        handleMessage(data) {
            switch (data.type) {
                case 'connected':
                    this.triggerCallback('connected', data);
                    break;
                
                case 'status':
                    this.triggerCallback('status', data);
                    break;
                
                case 'pose_update':
                    // Transform NATai format to RuView format
                    const ruviewData = this.transformPoseData(data);
                    this.triggerCallback('pose_update', ruviewData);
                    break;
                
                default:
                    log.debug('Unknown message type:', data.type);
            }
        }

        /**
         * Transform NATai pose data format to RuView expected format
         */
        transformPoseData(nataiData) {
            // RuView expects: { people: [...], timestamp: ..., zone: ... }
            return {
                people: nataiData.detections || [],
                num_people: nataiData.num_people || 0,
                timestamp: nataiData.timestamp,
                zone: 'zone_1', // Default zone
                confidence: 0.85,
                source: 'wifi_csi'
            };
        }

        /**
         * Register callback for specific event type
         */
        on(eventType, callback) {
            if (!this.callbacks.has(eventType)) {
                this.callbacks.set(eventType, []);
            }
            this.callbacks.get(eventType).push(callback);
        }

        /**
         * Trigger callbacks for event type
         */
        triggerCallback(eventType, data) {
            const callbacks = this.callbacks.get(eventType);
            if (callbacks) {
                callbacks.forEach(cb => {
                    try {
                        cb(data);
                    } catch (error) {
                        log.error(`Callback error for ${eventType}:`, error);
                    }
                });
            }
        }

        /**
         * Send command to backend
         */
        sendCommand(command, data = {}) {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({ command, ...data }));
            } else {
                log.warn('WebSocket not connected, cannot send command:', command);
            }
        }

        /**
         * Fetch API endpoint
         */
        async fetch(endpoint, options = {}) {
            try {
                const url = `${CONFIG.nataiApi}${endpoint}`;
                log.debug('Fetching:', url);
                
                const response = await fetch(url, {
                    ...options,
                    headers: {
                        'Content-Type': 'application/json',
                        ...options.headers
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                return await response.json();
            } catch (error) {
                log.error('Fetch error:', error);
                throw error;
            }
        }
    }

    // Create global adapter instance
    const adapter = new APIAdapter();

    // Expose adapter to RuView components
    window.nataiAdapter = adapter;

    /**
     * Override RuView's WebSocket service if it exists
     */
    if (typeof window.wsService !== 'undefined') {
        log.info('Overriding RuView wsService with NATai adapter');
        
        const originalConnect = window.wsService.connect;
        window.wsService.connect = function(zone) {
            log.info('Intercepted wsService.connect for zone:', zone);
            return adapter.connectWebSocket();
        };
    }

    /**
     * Override RuView's API service if it exists
     */
    if (typeof window.apiService !== 'undefined') {
        log.info('Overriding RuView apiService with NATai adapter');
        
        const originalGet = window.apiService.get;
        window.apiService.get = function(endpoint) {
            log.info('Intercepted apiService.get:', endpoint);
            
            // Map RuView endpoints to NATai endpoints
            const endpointMap = {
                '/health': '/wifi/status',
                '/status': '/wifi/status',
                '/stream/status': '/wifi/status',
                '/detections': '/wifi/detections'
            };

            const nataiEndpoint = endpointMap[endpoint] || endpoint;
            return adapter.fetch(nataiEndpoint);
        };

        const originalPost = window.apiService.post;
        window.apiService.post = function(endpoint, data) {
            log.info('Intercepted apiService.post:', endpoint, data);
            
            // Map commands
            if (endpoint === '/stream/start') {
                return adapter.fetch('/wifi/start', { method: 'POST', body: JSON.stringify(data) });
            } else if (endpoint === '/stream/stop') {
                return adapter.fetch('/wifi/stop', { method: 'POST', body: JSON.stringify(data) });
            }

            return adapter.fetch(endpoint, { method: 'POST', body: JSON.stringify(data) });
        };
    }

    /**
     * Listen for messages from parent (NATai) window
     */
    window.addEventListener('message', (event) => {
        // Only accept messages from same origin
        if (event.origin !== window.location.origin) {
            return;
        }

        if (event.data.type === 'wifi_data') {
            log.debug('Received WiFi data from parent:', event.data);
            adapter.handleMessage(event.data.data);
        }
    });

    /**
     * Auto-connect on page load
     */
    window.addEventListener('load', () => {
        log.info('RuView-NATai Bridge initialized');
        
        // Auto-connect after short delay to let RuView initialize
        setTimeout(() => {
            adapter.connectWebSocket().catch(error => {
                log.error('Failed to auto-connect:', error);
            });
        }, 1000);
    });

    log.info('RuView-NATai Bridge loaded');

})();
