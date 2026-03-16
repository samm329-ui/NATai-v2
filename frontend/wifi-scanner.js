/**
 * WiFi Scanner - Omarchy Terminal Style
 * Real-time WiFi scanning data visualization with Linux terminal UI
 */

class WiFiScanner {
    constructor() {
        this.isScanning = false;
        this.isAuto = false;
        this.scanInterval = null;
        this.autoInterval = null;
        this.packetCount = 0;
        this.startTime = Date.now();
        this.rssiHistory = [];
        this.maxHistory = 60;
        
        // Demo networks for simulation
        this.demoNetworks = [
            { ssid: 'Home_Network_5G', bssid: 'AA:BB:CC:DD:EE:01', channel: 36, freq: 5180, encryption: 'WPA3', rssi: -45 },
            { ssid: 'Home_Network_2G', bssid: 'AA:BB:CC:DD:EE:02', channel: 6, freq: 2437, encryption: 'WPA2', rssi: -52 },
            { ssid: 'Guest_WiFi', bssid: 'AA:BB:CC:DD:EE:03', channel: 11, freq: 2462, encryption: 'WPA2', rssi: -58 },
            { ssid: 'Office_5G', bssid: '11:22:33:44:55:01', channel: 149, freq: 5745, encryption: 'WPA2', rssi: -62 },
            { ssid: 'Office_2G', bssid: '11:22:33:44:55:02', channel: 1, freq: 2412, encryption: 'WPA2', rssi: -68 },
            { ssid: 'IoT_Devices', bssid: '11:22:33:44:55:03', channel: 3, freq: 2422, encryption: 'WPA2', rssi: -72 },
            { ssid: 'Neighborhood_5G', bssid: '22:33:44:55:66:01', channel: 44, freq: 5220, encryption: 'WPA2', rssi: -75 },
            { ssid: 'Neighborhood_2G', bssid: '22:33:44:55:66:02', channel: 9, freq: 2452, encryption: 'WPA2', rssi: -78 },
            { ssid: 'Cafe_WiFi', bssid: '33:44:55:66:77:01', channel: 48, freq: 5240, encryption: 'OPEN', rssi: -82 },
            { ssid: 'Hidden_Network', bssid: '44:55:66:77:88:01', channel: 40, freq: 5200, encryption: 'WPA2', rssi: -85 },
        ];
        
        this.networks = [];
        this.init();
    }

    init() {
        this.bindElements();
        this.bindEvents();
        this.initSparkline();
        this.updateUptime();
        this.startClock();
    }

    bindElements() {
        // Buttons
        this.btnScan = document.getElementById('btn-scan');
        this.btnAuto = document.getElementById('btn-auto');
        this.btnStop = document.getElementById('btn-stop');
        this.btnClear = document.getElementById('btn-clear');
        
        // Terminal
        this.terminalOutput = document.getElementById('terminal-output');
        this.terminalStatus = document.getElementById('terminal-status');
        
        // RSSI
        this.rssiValue = document.getElementById('rssi-value');
        this.rssiNeedle = document.getElementById('rssi-needle');
        this.rssiStatus = document.getElementById('rssi-status');
        
        // Stats
        this.statVariance = document.getElementById('stat-variance');
        this.statMotion = document.getElementById('stat-motion');
        this.statBreath = document.getElementById('stat-breath');
        this.statConfidence = document.getElementById('stat-confidence');
        
        // Networks
        this.networkList = document.getElementById('network-list');
        this.networkCount = document.getElementById('network-count');
        
        // Raw data
        this.rawData = document.getElementById('raw-data');
        this.dataStatus = document.getElementById('data-status');
        
        // Footer
        this.footerNetworks = document.getElementById('footer-networks');
        this.footerPackets = document.getElementById('footer-packets');
        this.footerUptime = document.getElementById('footer-uptime');
        this.connectionDot = document.getElementById('connection-dot');
        this.connectionText = document.getElementById('connection-text');
        
        // Sparkline
        this.sparklineCanvas = document.getElementById('rssi-sparkline');
        this.sparklineCtx = this.sparklineCanvas.getContext('2d');
    }

    bindEvents() {
        this.btnScan.addEventListener('click', () => this.startScan());
        this.btnAuto.addEventListener('click', () => this.toggleAuto());
        this.btnStop.addEventListener('click', () => this.stopScan());
        this.btnClear.addEventListener('click', () => this.clearTerminal());
        
        // Raw data buttons
        document.getElementById('btn-copy').addEventListener('click', () => this.copyRawData());
        document.getElementById('btn-expand').addEventListener('click', () => this.toggleExpand());
        document.getElementById('btn-filter').addEventListener('click', () => this.toggleFilter());
    }

    initSparkline() {
        const canvas = this.sparklineCanvas;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * 2;
        canvas.height = rect.height * 2;
        this.sparklineCtx.scale(2, 2);
        this.drawSparkline();
    }

    drawSparkline() {
        const ctx = this.sparklineCtx;
        const canvas = this.sparklineCanvas;
        const width = canvas.width / 2;
        const height = canvas.height / 2;
        
        ctx.clearRect(0, 0, width, height);
        
        // Draw grid
        ctx.strokeStyle = '#1a1a1a';
        ctx.lineWidth = 0.5;
        for (let i = 0; i < 5; i++) {
            const y = (height / 4) * i;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }
        
        if (this.rssiHistory.length < 2) return;
        
        // Draw line
        const minRssi = -100;
        const maxRssi = -30;
        const range = maxRssi - minRssi;
        
        ctx.beginPath();
        ctx.strokeStyle = '#00ff41';
        ctx.lineWidth = 1.5;
        
        this.rssiHistory.forEach((rssi, i) => {
            const x = (i / (this.maxHistory - 1)) * width;
            const y = height - ((rssi - minRssi) / range) * height;
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        
        ctx.stroke();
        
        // Draw gradient fill
        if (this.rssiHistory.length > 1) {
            const lastX = ((this.rssiHistory.length - 1) / (this.maxHistory - 1)) * width;
            ctx.lineTo(lastX, height);
            ctx.lineTo(0, height);
            ctx.closePath();
            
            const gradient = ctx.createLinearGradient(0, 0, 0, height);
            gradient.addColorStop(0, 'rgba(0, 255, 65, 0.3)');
            gradient.addColorStop(1, 'rgba(0, 255, 65, 0)');
            ctx.fillStyle = gradient;
            ctx.fill();
        }
    }

    startScan() {
        if (this.isScanning) return;
        
        this.isScanning = true;
        this.btnScan.classList.add('active');
        this.btnStop.classList.remove('active');
        
        this.log('info', 'Starting WiFi scan...');
        this.log('cmd', 'sudo airodump-ng wlan0mon --band abg');
        this.log('success', '[OK] Scanning initiated');
        
        this.terminalStatus.classList.add('live');
        this.terminalStatus.innerHTML = `
            <span class="scanning-indicator">
                <span class="scanning-dots">
                    <span class="scanning-dot"></span>
                    <span class="scanning-dot"></span>
                    <span class="scanning-dot"></span>
                </span>
                SCANNING
            </span>
        `;
        
        this.scanInterval = setInterval(() => {
            this.performScan();
        }, 1500);
        
        this.performScan();
    }

    stopScan() {
        this.isScanning = false;
        this.isAuto = false;
        
        if (this.scanInterval) {
            clearInterval(this.scanInterval);
            this.scanInterval = null;
        }
        if (this.autoInterval) {
            clearInterval(this.autoInterval);
            this.autoInterval = null;
        }
        
        this.btnScan.classList.remove('active');
        this.btnAuto.classList.remove('active');
        this.btnStop.classList.add('active');
        
        this.log('warning', '[STOP] Scan stopped by user');
        
        this.terminalStatus.classList.remove('live');
        this.terminalStatus.textContent = 'STOPPED';
    }

    toggleAuto() {
        this.isAuto = !this.isAuto;
        this.btnAuto.classList.toggle('active', this.isAuto);
        
        if (this.isAuto) {
            this.log('info', 'Auto-scan mode enabled');
            this.startScan();
        } else {
            this.log('info', 'Auto-scan mode disabled');
        }
    }

    performScan() {
        const t = Date.now() / 1000;
        
        // Generate simulated RSSI with variation
        const baseRssi = -50;
        const rssi = baseRssi + Math.sin(t * 0.5) * 8 + Math.random() * 4;
        
        // Add to history
        this.rssiHistory.push(rssi);
        if (this.rssiHistory.length > this.maxHistory) {
            this.rssiHistory.shift();
        }
        
        // Update demo networks with current RSSI
        this.networks = this.demoNetworks.map(net => ({
            ...net,
            rssi: net.rssi + Math.sin(t * 0.3 + net.channel * 0.1) * 5 + Math.random() * 3
        })).sort((a, b) => a.rssi - b.rssi);
        
        // Update RSSI gauge
        this.updateRSSI(rssi);
        
        // Update stats
        const variance = 1.5 + Math.sin(t * 0.1) * 1.0;
        const motionBand = 0.05 + Math.abs(Math.sin(t * 0.3)) * 0.15;
        const breathBand = 0.03 + Math.abs(Math.sin(t * 0.05)) * 0.08;
        const confidence = variance > 0.8 ? 0.75 + Math.random() * 0.2 : 0.5 + Math.random() * 0.3;
        
        this.statVariance.textContent = variance.toFixed(2);
        this.statMotion.textContent = (motionBand * 100).toFixed(1);
        this.statBreath.textContent = (breathBand * 100).toFixed(1);
        this.statConfidence.textContent = (confidence * 100).toFixed(0) + '%';
        
        // Update network list
        this.updateNetworkList();
        
        // Update sparkline
        this.drawSparkline();
        
        // Update raw data
        this.updateRawData({
            timestamp: Date.now(),
            source: 'simulated',
            nodes: [{
                node_id: 1,
                rssi_dbm: rssi,
                position: [2, 0, 1.5],
            }],
            features: {
                mean_rssi: rssi,
                variance: variance,
                motion_band_power: motionBand,
                breathing_band_power: breathBand,
                spectral_power: motionBand + breathBand,
            },
            classification: {
                presence: variance > 0.8,
                confidence: confidence,
                motion_level: motionBand > 0.12 ? 'active' : (variance > 0.8 ? 'present_still' : 'absent'),
            }
        });
        
        // Log some network info
        this.packetCount += Math.floor(Math.random() * 50) + 10;
        this.footerPackets.textContent = this.packetCount.toLocaleString();
        
        // Random terminal output
        if (Math.random() > 0.7) {
            const net = this.networks[Math.floor(Math.random() * Math.min(3, this.networks.length))];
            if (net) {
                this.log('info', `[BSSID] ${net.bssid} - RSSI: ${net.rssi.toFixed(0)} dBm (${this.getSignalQuality(net.rssi)})`);
            }
        }
    }

    updateRSSI(rssi) {
        const rounded = Math.round(rssi);
        this.rssiValue.textContent = rounded;
        this.rssiStatus.textContent = `${rounded} dBm`;
        
        // Calculate needle rotation (-90 to 90 degrees)
        // Map -100dBm to -90deg, -30dBm to 90deg
        const minRssi = -100;
        const maxRssi = -30;
        const range = maxRssi - minRssi;
        const percent = (rssi - minRssi) / range;
        const rotation = -90 + (percent * 180);
        
        this.rssiNeedle.style.transform = `translateX(-50%) rotate(${rotation}deg)`;
        
        // Color based on signal strength
        if (rssi > -50) {
            this.rssiValue.style.color = '#00ff41';
        } else if (rssi > -70) {
            this.rssiValue.style.color = '#ffaa00';
        } else {
            this.rssiValue.style.color = '#ff3333';
        }
    }

    updateNetworkList() {
        const html = this.networks.map(net => {
            const quality = this.getSignalQuality(net.rssi);
            const barClass = this.getSignalBarClass(net.rssi);
            const signalPercent = Math.max(0, Math.min(100, (net.rssi + 100) * 1.43));
            
            return `
                <div class="network-item">
                    <div class="network-info">
                        <div class="network-ssid">${net.ssid}</div>
                        <div class="network-details">
                            <span class="network-bssid">${net.bssid}</span>
                            <span class="network-channel">CH: ${net.channel}</span>
                            <span class="network-freq">${net.freq} MHz</span>
                        </div>
                    </div>
                    <div class="network-signal">
                        <span class="encryption-badge ${net.encryption.toLowerCase()}">${net.encryption}</span>
                        <div class="signal-bar-container">
                            <div class="signal-bar ${barClass}" style="width: ${signalPercent}%"></div>
                        </div>
                        <span class="signal-dbm">${net.rssi.toFixed(0)} dBm</span>
                        <span class="signal-quality">${quality}</span>
                    </div>
                </div>
            `;
        }).join('');
        
        this.networkList.innerHTML = html;
        this.networkCount.textContent = `${this.networks.length} networks found`;
        this.footerNetworks.textContent = this.networks.length;
    }

    getSignalQuality(rssi) {
        if (rssi > -50) return 'Excellent';
        if (rssi > -60) return 'Good';
        if (rssi > -70) return 'Fair';
        return 'Weak';
    }

    getSignalBarClass(rssi) {
        if (rssi > -50) return 'excellent';
        if (rssi > -60) return 'good';
        if (rssi > -70) return 'fair';
        return 'weak';
    }

    updateRawData(data) {
        const formatted = this.formatJSON(data);
        this.rawData.innerHTML = formatted;
        this.dataStatus.textContent = 'live';
        
        // Update footer timestamp
        const now = new Date();
        this.dataStatus.textContent = now.toLocaleTimeString();
    }

    formatJSON(data) {
        const json = JSON.stringify(data, null, 2);
        return json.replace(
            /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
            (match) => {
                let cls = 'json-number';
                if (/^"/.test(match)) {
                    if (/:$/.test(match)) {
                        cls = 'json-key';
                        match = match.slice(0, -1) + '</span>:';
                        return '<span class="' + cls + '">' + match;
                    } else {
                        cls = 'json-string';
                    }
                } else if (/true|false/.test(match)) {
                    cls = 'json-boolean';
                } else if (/null/.test(match)) {
                    cls = 'json-null';
                }
                return '<span class="' + cls + '">' + match + '</span>';
            }
        );
    }

    log(type, message) {
        const time = new Date().toLocaleTimeString();
        const line = document.createElement('div');
        line.className = 'term-line';
        
        let content = `<span class="term-timestamp">[${time}]</span> `;
        
        switch (type) {
            case 'cmd':
                content += `<span class="term-prompt">user@omarchy</span>:<span class="term-cmd">~</span>$ <span class="term-cmd">${message}</span>`;
                break;
            case 'success':
                content += `<span class="term-success">${message}</span>`;
                break;
            case 'error':
                content += `<span class="term-error">${message}</span>`;
                break;
            case 'warning':
                content += `<span class="term-warning">${message}</span>`;
                break;
            case 'info':
            default:
                content += `<span class="term-info">${message}</span>`;
        }
        
        line.innerHTML = content;
        this.terminalOutput.appendChild(line);
        this.terminalOutput.scrollTop = this.terminalOutput.scrollHeight;
        
        // Keep only last 100 lines
        while (this.terminalOutput.children.length > 100) {
            this.terminalOutput.removeChild(this.terminalOutput.firstChild);
        }
    }

    clearTerminal() {
        this.terminalOutput.innerHTML = '';
        this.log('info', 'Terminal cleared');
    }

    copyRawData() {
        const text = this.rawData.textContent;
        navigator.clipboard.writeText(text).then(() => {
            this.log('success', 'Raw data copied to clipboard');
        });
    }

    toggleExpand() {
        const rawDataContainer = document.querySelector('.raw-data-container');
        rawDataContainer.classList.toggle('expanded');
        this.log('info', rawDataContainer.classList.contains('expanded') ? 'Expanded view' : 'Collapsed view');
    }

    toggleFilter() {
        this.log('info', 'Filter options: [ALL] [BSSID] [SSID] [CHANNEL]');
    }

    updateUptime() {
        const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
        const hours = Math.floor(elapsed / 3600).toString().padStart(2, '0');
        const minutes = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
        const seconds = (elapsed % 60).toString().padStart(2, '0');
        this.footerUptime.textContent = `${hours}:${minutes}:${seconds}`;
    }

    startClock() {
        setInterval(() => this.updateUptime(), 1000);
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    window.wifiScanner = new WiFiScanner();
});
