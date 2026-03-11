/* ================================================================
   N.A.T. (Natasha) Frontend — Main Application Logic
   ================================================================ */

/*
 * API — The base URL for all backend requests.
 */
const API = (typeof window !== 'undefined' && window.location.origin && window.location.origin !== 'null' && !window.location.origin.includes('file://'))
    ? window.location.origin
    : 'http://localhost:8000';

/* ================================================================
   APPLICATION STATE
   ================================================================ */
let sessionId = null;
let currentMode = 'general';
let isStreaming = false;
let isListening = false;
let orb = null;
let ttsPlayer = null;
let recognitionTimeout = null;
window.hasInteracted = false;

const $ = id => document.getElementById(id);

const chatMessages = $('chat-messages');
const messageInput = $('message-input');
const sendBtn = $('send-btn');
const micBtn = $('mic-btn');
const ttsBtn = $('tts-btn');
const newChatBtn = $('new-chat-btn');
const modeLabel = $('mode-label');
const charCount = $('char-count');
const welcomeTitle = $('welcome-title');
const modeSlider = $('mode-slider');
const btnGeneral = $('btn-general');
const btnRealtime = $('btn-realtime');
const statusDot = document.querySelector('.status-dot');
const statusText = document.querySelector('.status-text');
const orbContainer = $('orb-container');
const searchResultsToggle = $('search-results-toggle');
const searchResultsWidget = $('search-results-widget');
const searchResultsClose = $('search-results-close');
const searchResultsQuery = $('search-results-query');
const searchResultsAnswer = $('search-results-answer');
const searchResultsList = $('search-results-list');
const pauseBtn = $('pause-btn');

let currentController = null;
let wasListeningBeforeSend = false;

// Confirm Bar Elements
const confirmBar = $('confirm-bar');
const confirmText = $('confirm-text');
const confirmSendBtn = $('confirm-send-btn');
const confirmKeepTalkingBtn = $('confirm-keep-talking-btn');
let confirmCountdownInterval = null;
let silenceTimeoutMode = 'none'; // 'short' or 'long'

/* ================================================================
   EDGE TTS AUDIO PLAYER (from backend) - SIMPLE STREAMING
   ================================================================ */
let audioContext = null;
let currentSource = null;

function getAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContext;
}

let ttsAudioQueue = [];
let isTTSPlaying = false;

async function playEdgeTTSAudio(base64Audio) {
    if (ttsPlayer && !ttsPlayer.enabled) return;

    // Add audio to queue rather than playing immediately
    ttsAudioQueue.push(base64Audio);

    // If not currently playing something, start processing the queue
    if (!isTTSPlaying) {
        processTTSQueue();
    }
}

async function processTTSQueue() {
    if (ttsAudioQueue.length === 0) {
        isTTSPlaying = false;
        if (ttsBtn) ttsBtn.classList.remove('tts-speaking');
        if (orbContainer) orbContainer.classList.remove('speaking');
        if (orb) orb.setActive(false);
        return;
    }

    isTTSPlaying = true;
    const base64Audio = ttsAudioQueue.shift();

    // BUG 13 FIX: Prevent 'The AudioContext was not allowed to start' uncatchable constructor warning.
    // If the user hasn't physically clicked the page yet, silently skip playing this audio chunk entirely.
    if (!window.hasInteracted) {
        console.log("[Edge TTS] Suppressed audio chunk because user hasn't interacted with the page yet.");
        processTTSQueue();
        return;
    }

    try {
        const ctx = getAudioContext();

        if (ctx.state === 'suspended') {
            try {
                await ctx.resume();
            } catch (e) {
                console.warn("[Edge TTS] AudioContext blocked by browser autoplay policy. Waiting for user interaction.");
            }
        }

        const binaryString = atob(base64Audio);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        const audioBuffer = await ctx.decodeAudioData(bytes.buffer);

        // No longer call currentSource.stop() here as we play sequentially
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        currentSource = source;

        if (ttsBtn) ttsBtn.classList.add('tts-speaking');
        if (orbContainer) orbContainer.classList.add('speaking');
        if (orb) orb.setActive(true);

        source.onended = () => {
            currentSource = null;
            // Play the next chunk in the queue
            processTTSQueue();
        };

        try {
            source.start(0);
            console.log("[Edge TTS] Playing audio chunk");
        } catch (e) {
            console.warn("[Edge TTS] Autoplay blocked playback. User interaction required.");
        }

    } catch (e) {
        console.error("[Edge TTS] Error playing audio:", e);
        // Process next even on error
        processTTSQueue();
    }
}

/* ================================================================
   TTS PLAYER STUB (Tracks enabled state without breaking Edge TTS)
   ================================================================ */
class TTSPlayer {
    constructor() { this.enabled = true; }
    stop() { stopAllTTS(); }
}

function stopAllTTS() {
    window.speechSynthesis.cancel();

    // Clear audio queue
    ttsAudioQueue = [];
    isTTSPlaying = false;

    if (currentSource) {
        try {
            currentSource.stop();
            currentSource = null;
        } catch (e) { }
    }
    if (ttsBtn) ttsBtn.classList.remove('tts-speaking');
    if (orbContainer) orbContainer.classList.remove('speaking');
    if (orb) orb.setActive(false);
}

/* ================================================================
   INITIALIZATION
   ================================================================ */
function init() {
    ttsPlayer = new TTSPlayer();
    // Ensure button reflects actual TTS state
    if (ttsBtn) {
        ttsBtn.classList.add('tts-active');
        console.log("[TTS] Initialized, enabled:", ttsPlayer.enabled);
    }
    setGreeting();
    initOrb();
    initSpeech();
    checkHealth();
    bindEvents();
    autoResizeInput();
    initConfirmBarEvents();

    function _setInteracted() {
        window.hasInteracted = true;
        ['click', 'keydown', 'touchstart'].forEach(evt => document.removeEventListener(evt, _setInteracted));
    }
    ['click', 'keydown', 'touchstart'].forEach(evt => document.addEventListener(evt, _setInteracted, { once: true }));

    // The user requested the greeting to speak instantly on load, bypassing autoplay policies.
    setTimeout(_speakWelcome, 1200);
}

let hasSpokenWelcome = false;

function _speakWelcome() {
    if (!hasSpokenWelcome) {
        hasSpokenWelcome = true;
        const greeting = _getGreetingText();
        // Since we're trying to guarantee the first voice plays, call the backend TTS or native synth
        if (ttsPlayer.enabled) {
            // Wait slightly so the visual greeting aligns with the audio trigger
            setTimeout(() => {
                const welcomePayload = {
                    text: greeting
                };
                fetch('/tts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(welcomePayload)
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.audio) {
                            playEdgeTTSAudio(data.audio);
                        }
                    })
                    .catch(err => console.error("Could not fetch welcome greeting audio:", err));
            }, 300);
        }
    }
}

function initConfirmBarEvents() {
    if (confirmSendBtn) {
        confirmSendBtn.addEventListener('click', () => {
            hideConfirmBar(true);
            sendMessage(messageInput.value);
        });
    }
    if (confirmKeepTalkingBtn) {
        confirmKeepTalkingBtn.addEventListener('click', () => {
            hideConfirmBar();
            startListening();
        });
    }
}

function _getGreetingText() {
    const h = new Date().getHours();
    if (h < 5) return 'Working late, Boss?';
    if (h < 12) return 'Good morning, Boss.';
    if (h < 17) return 'Good afternoon, Boss.';
    if (h < 22) return 'Good evening, Boss.';
    return 'Late night, Boss?';
}

function setGreeting() {
    if (welcomeTitle) {
        welcomeTitle.textContent = _getGreetingText();
    }
}

function initOrb() {
    if (typeof OrbRenderer === 'undefined') return;
    try {
        orb = new OrbRenderer(orbContainer, {
            hue: 280,
            hoverIntensity: 0.3,
            backgroundColor: [0.02, 0.02, 0.06]
        });
    } catch (e) { console.warn('Orb init failed:', e); }
}

/* ================================================================
   SPEECH RECOGNITION
   ================================================================ */

let recognition = null;
let silenceTimeout = null;

function _isCompleteSentence(text) {
    if (!text) return false;
    const trimmed = text.trim();
    if (trimmed.length < 3) return false;

    // Ends with punctuation
    if (/[.!?]$/.test(trimmed)) return true;

    // Common command patterns that are usually complete
    const lower = trimmed.toLowerCase();
    if (lower.startsWith("open ") || lower.startsWith("play ") ||
        lower.startsWith("run ") || lower.startsWith("search ")) {
        if (trimmed.split(/\s+/).length >= 2) return true;
    }

    // Seems like a reasonable length question
    if (lower.startsWith("what ") || lower.startsWith("how ") ||
        lower.startsWith("who ") || lower.startsWith("where ") ||
        lower.startsWith("why ")) {
        if (trimmed.split(/\s+/).length >= 4) return true;
    }

    return false;
}

function showConfirmBar() {
    if (!confirmBar) return;

    // Don't show if already sending
    if (isStreaming) return;

    confirmBar.classList.remove('hidden');
    stopListening(); // Pause listening while confirming

    let timeRemaining = 3;
    if (confirmText) confirmText.textContent = `Auto-sending in ${timeRemaining}s...`;

    clearInterval(confirmCountdownInterval);
    confirmCountdownInterval = setInterval(() => {
        timeRemaining--;
        if (timeRemaining > 0) {
            if (confirmText) confirmText.textContent = `Auto-sending in ${timeRemaining}s...`;
        } else {
            hideConfirmBar(true);
            sendMessage(messageInput.value);
        }
    }, 1000);
}

function hideConfirmBar(clearText = false) {
    if (!confirmBar) return;
    confirmBar.classList.add('hidden');
    clearInterval(confirmCountdownInterval);
    silenceTimeoutMode = 'none';
    if (clearText && confirmText) confirmText.textContent = "";
}

function initSpeech() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            isListening = true;
            micBtn.classList.add('listening');
            messageInput.placeholder = "Listening...";
        };

        recognition.onresult = (event) => {
            // Echo Lock
            if (isStreaming || window.speechSynthesis.speaking || isTTSPlaying) return;

            clearTimeout(silenceTimeout);

            // If they started speaking again, hide the confirm bar and cancel countdown
            hideConfirmBar();

            const transcript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');

            messageInput.value = transcript;

            const isComplete = _isCompleteSentence(transcript);
            const timeoutDuration = isComplete ? 1200 : 2500;
            silenceTimeoutMode = isComplete ? 'short' : 'long';

            silenceTimeout = setTimeout(() => {
                const finalTranscript = messageInput.value.trim();
                if (finalTranscript && !isStreaming) {
                    showConfirmBar();
                }
            }, timeoutDuration);
        };

        recognition.onerror = (e) => {
            console.error('STT error', e);
            stopListening();
        };

        recognition.onend = () => {
            isListening = false;
            micBtn.classList.remove('listening');
            if (!messageInput.value) messageInput.placeholder = "Type your message...";
        };
    } else {
        micBtn.title = 'Voice input not supported in this browser';
    }
}

async function startListening() {
    if (isStreaming) return;
    if (recognition) {
        try {
            recognition.start();
        } catch (e) { }
    }
}

function stopListening() {
    if (recognition) recognition.stop();
    clearTimeout(silenceTimeout);
    isListening = false;
    micBtn.classList.remove('listening');
    messageInput.placeholder = "Type your message...";
}

async function checkHealth() {
    try {
        const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(5000) });
        const d = await r.json();
        const ok = d.status === 'healthy';
        statusDot.classList.toggle('offline', !ok);
        statusText.textContent = ok ? 'Online' : 'Offline';
    } catch {
        statusDot.classList.add('offline');
        statusText.textContent = 'Offline';
    }
}

function bindEvents() {
    sendBtn.addEventListener('click', () => { if (!isStreaming) sendMessage(); });
    messageInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!isStreaming) sendMessage(); }
    });
    messageInput.addEventListener('input', () => {
        autoResizeInput();
        const len = messageInput.value.length;
        charCount.textContent = len > 100 ? `${len.toLocaleString()} / 32,000` : '';
    });
    micBtn.addEventListener('click', () => {
        if (isListening) {
            stopListening();
        } else {
            startListening();
        }
    });
    ttsBtn.addEventListener('click', () => {
        if (ttsPlayer) {
            ttsPlayer.enabled = !ttsPlayer.enabled;
            ttsBtn.classList.toggle('tts-active', ttsPlayer.enabled);
            if (!ttsPlayer.enabled) ttsPlayer.stop();
        }
    });
    pauseBtn.addEventListener('click', stopStreaming);
    newChatBtn.addEventListener('click', newChat);
    btnGeneral.addEventListener('click', () => setMode('general'));
    btnRealtime.addEventListener('click', () => setMode('realtime'));
    document.querySelectorAll('.chip').forEach(c => {
        c.addEventListener('click', () => { if (!isStreaming) sendMessage(c.dataset.msg); });
    });
    if (searchResultsToggle) {
        searchResultsToggle.addEventListener('click', () => {
            if (searchResultsWidget) searchResultsWidget.classList.add('open');
        });
    }
    if (searchResultsClose && searchResultsWidget) {
        searchResultsClose.addEventListener('click', () => searchResultsWidget.classList.remove('open'));
    }
}

function autoResizeInput() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

function setMode(mode) {
    currentMode = mode;
    btnGeneral.classList.toggle('active', mode === 'general');
    btnRealtime.classList.toggle('active', mode === 'realtime');
    modeSlider.classList.toggle('right', mode === 'realtime');
    modeLabel.textContent = mode === 'general' ? 'General Mode' : 'Realtime Mode';
    if (searchResultsToggle) {
        searchResultsToggle.style.display = (mode === 'realtime') ? '' : 'none';
    }
    if (searchResultsWidget) {
        searchResultsWidget.classList.remove('open');
    }
}

function newChat() {
    stopAllTTS();
    sessionId = null;
    chatMessages.innerHTML = '';
    chatMessages.appendChild(createWelcome());
    messageInput.value = '';
    autoResizeInput();
    setGreeting();
    if (searchResultsWidget) searchResultsWidget.classList.remove('open');
    if (searchResultsToggle) searchResultsToggle.style.display = 'none';
}

function createWelcome() {
    const greetingText = _getGreetingText();

    const div = document.createElement('div');
    div.className = 'welcome-screen';
    div.id = 'welcome-screen';
    div.innerHTML = `
        <div class="welcome-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        </div>
        <h2 class="welcome-title">${greetingText}</h2>
        <p class="welcome-sub">I am Natasha. How may I assist you today?</p>
        <div class="welcome-chips">
            <button class="chip" data-msg="Who are you?">Who are you?</button>
            <button class="chip" data-msg="Check the latest tech news">Latest News</button>
            <button class="chip" data-msg="Tell me a fun fact">Fun fact</button>
            <button class="chip" data-msg="Analyze my business data">Business Intelligence</button>
        </div>`;

    div.querySelectorAll('.chip').forEach(c => {
        c.addEventListener('click', () => { if (!isStreaming) sendMessage(c.dataset.msg); });
    });
    return div;
}

/* ================================================================
   MESSAGE RENDERING
   ================================================================ */
function isUrlLike(str) {
    if (!str || typeof str !== 'string') return false;
    const s = str.trim();
    return s.length > 40 && (/^https?:\/\//i.test(s) || /\%2f|\%3a|\.com\/|\.org\//i.test(s));
}

function friendlyUrlLabel(url) {
    if (!url || typeof url !== 'string') return 'View source';
    try {
        const u = new URL(url.startsWith('http') ? url : 'https://' + url);
        const host = u.hostname.replace(/^www\./, '');
        const path = u.pathname !== '/' ? u.pathname.slice(0, 20) + (u.pathname.length > 20 ? '…' : '') : '';
        return path ? host + path : host;
    } catch (_) {
        return url.length > 40 ? url.slice(0, 37) + '…' : url;
    }
}

function truncateSnippet(text, maxLen) {
    if (!text || typeof text !== 'string') return '';
    const t = text.trim();
    if (t.length <= maxLen) return t;
    return t.slice(0, maxLen).trim() + '…';
}

function renderSearchResults(payload) {
    if (!payload) return;
    if (searchResultsQuery) searchResultsQuery.textContent = (payload.query || '').trim() || 'Search';
    if (searchResultsAnswer) searchResultsAnswer.textContent = (payload.answer || '').trim() || '';
    if (!searchResultsList) return;
    searchResultsList.innerHTML = '';
    const results = payload.results || [];
    const maxContentLen = 220;
    for (const r of results) {
        let title = (r.title || '').trim();
        let content = (r.content || '').trim();
        const url = (r.url || '').trim();
        if (isUrlLike(title)) title = friendlyUrlLabel(url) || 'Source';
        if (!title) title = friendlyUrlLabel(url) || 'Source';
        if (isUrlLike(content)) content = '';
        content = truncateSnippet(content, maxContentLen);
        const score = r.score != null ? Math.round((r.score || 0) * 100) : null;
        const card = document.createElement('div');
        card.className = 'search-result-card';
        const urlDisplay = url ? escapeHtml(friendlyUrlLabel(url)) : '';
        const urlSafe = url ? url.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') : '';
        card.innerHTML = `
            <div class="card-title">${escapeHtml(title)}</div>
            ${content ? `<div class="card-content">${escapeHtml(content)}</div>` : ''}
            ${url ? `<a href="${urlSafe}" target="_blank" rel="noopener" class="card-url" title="${escapeAttr(url)}">${urlDisplay}</a>` : ''}
            ${score != null ? `<div class="card-score">Relevance: ${escapeHtml(String(score))}%</div>` : ''}`;
        searchResultsList.appendChild(card);
    }
}

function escapeAttr(str) {
    if (typeof str !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML.replace(/"/g, '&quot;');
}

function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function hideWelcome() {
    const w = document.getElementById('welcome-screen');
    if (w) w.remove();
}

const AVATAR_ICON_USER = '<svg class="msg-avatar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
const AVATAR_ICON_ASSISTANT = '<svg class="msg-avatar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><circle cx="9" cy="16" r="1" fill="currentColor"/><circle cx="15" cy="16" r="1" fill="currentColor"/></svg>';

function addMessage(role, text) {
    hideWelcome();
    const msg = document.createElement('div');
    msg.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerHTML = role === 'assistant' ? AVATAR_ICON_ASSISTANT : AVATAR_ICON_USER;

    const body = document.createElement('div');
    body.className = 'msg-body';

    const label = document.createElement('div');
    label.className = 'msg-label';
    label.textContent = role === 'assistant'
        ? `Natasha (${currentMode === 'realtime' ? 'Realtime' : 'General'})`
        : 'You';

    const content = document.createElement('div');
    content.className = 'msg-content';
    content.textContent = text;

    body.appendChild(label);
    body.appendChild(content);
    msg.appendChild(avatar);
    msg.appendChild(body);
    chatMessages.appendChild(msg);
    scrollToBottom();
    return content;
}

function addTypingIndicator() {
    hideWelcome();
    const msg = document.createElement('div');
    msg.className = 'message assistant';
    msg.id = 'typing-msg';

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerHTML = AVATAR_ICON_ASSISTANT;

    const body = document.createElement('div');
    body.className = 'msg-body';

    const label = document.createElement('div');
    label.className = 'msg-label';
    label.textContent = `Natasha (${currentMode === 'realtime' ? 'Realtime' : 'General'})`;

    const content = document.createElement('div');
    content.className = 'msg-content';
    content.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';

    body.appendChild(label);
    body.appendChild(content);
    msg.appendChild(avatar);
    msg.appendChild(body);
    chatMessages.appendChild(msg);
    scrollToBottom();
    return content;
}

function removeTypingIndicator() {
    const t = document.getElementById('typing-msg');
    if (t) t.remove();
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

/* ================================================================
   SEND MESSAGE + SSE STREAMING
   ================================================================ */
async function sendMessage(textOverride, isVoice = false) {
    const text = (textOverride || messageInput.value).trim();
    if (!text || isStreaming) return;

    if (currentSource) {
        try { currentSource.stop(); } catch (e) { }
        currentSource = null;
    }
    messageInput.value = '';
    autoResizeInput();
    charCount.textContent = '';

    addMessage('user', text);
    addTypingIndicator();

    isStreaming = true;
    sendBtn.disabled = true;
    pauseBtn.style.display = 'flex';

    wasListeningBeforeSend = isListening || !confirmBar.classList.contains('hidden');
    hideConfirmBar(true);
    stopListening();

    // Unlock audio context for Edge TTS
    try {
        const ctx = getAudioContext();
        if (ctx.state === 'suspended') {
            await ctx.resume();
        }
    } catch (e) { }

    const endpoint = currentMode === 'realtime' ? '/chat/realtime/stream' : '/chat/stream';
    currentController = new AbortController();

    try {
        const res = await fetch(`${API}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: sessionId,
                tts: !!(ttsPlayer && ttsPlayer.enabled)
            }),
            signal: currentController.signal
        });

        if (!res.ok) {
            const err = await res.json().catch(() => null);
            throw new Error(err?.detail || `HTTP ${res.status}`);
        }

        removeTypingIndicator();
        const contentEl = addMessage('assistant', '');
        const placeholder = currentMode === 'realtime' ? 'Searching...' : 'Thinking...';
        contentEl.innerHTML = `<span class="msg-stream-text">${placeholder}</span>`;
        scrollToBottom();

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = '';
        let fullResponse = '';
        let cursorEl = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                break;
            }

            sseBuffer += decoder.decode(value, { stream: true });
            const lines = sseBuffer.split('\n');
            sseBuffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));

                    if (data.session_id) sessionId = data.session_id;

                    if (data.search_results) {
                        renderSearchResults(data.search_results);
                        if (searchResultsToggle) searchResultsToggle.style.display = '';
                        if (searchResultsWidget) searchResultsWidget.classList.add('open');
                    }

                    if (data.tts_audio) {
                        playEdgeTTSAudio(data.tts_audio);
                    }

                    if (data.chunk) {
                        fullResponse += data.chunk;

                        const textSpan = contentEl.querySelector('.msg-stream-text');
                        if (textSpan) textSpan.textContent = fullResponse;

                        if (!cursorEl) {
                            cursorEl = document.createElement('span');
                            cursorEl.className = 'stream-cursor';
                            cursorEl.textContent = '|';
                            contentEl.appendChild(cursorEl);
                        }
                        scrollToBottom();
                    }

                    if (data.error) throw new Error(data.error);
                    if (data.done) break;
                } catch (parseErr) {
                    if (parseErr.message && !parseErr.message.includes('JSON'))
                        throw parseErr;
                }
            }
        }

        if (cursorEl) cursorEl.remove();
        const textSpan = contentEl.querySelector('.msg-stream-text');
        if (textSpan && !fullResponse) textSpan.textContent = '(No response)';

    } catch (err) {
        if (err.name === 'AbortError') {
            removeTypingIndicator();
            addMessage('assistant', 'Response paused.');
        } else {
            removeTypingIndicator();
            addMessage('assistant', `Something went wrong: ${err.message}`);
        }
    } finally {
        isStreaming = false;
        sendBtn.disabled = false;
        pauseBtn.style.display = 'none';
        currentController = null;

        if (wasListeningBeforeSend) {
            setTimeout(() => {
                startListening();
            }, 500);
        }
    }
}

function stopStreaming() {
    if (currentController) {
        currentController.abort();
    }

    stopAllTTS();
}

document.addEventListener('DOMContentLoaded', init);

/* ================================================================
   TERMINAL PANEL — UI Logic
   ================================================================ */

const terminalWidget = $('terminal-widget');
const terminalClose = $('terminal-close');
const terminalToggleBtn = $('terminal-toggle-btn');
const terminalInput = $('terminal-input');
const terminalRunBtn = $('terminal-run-btn');
const terminalOutput = $('terminal-output');
const terminalOsBadge = $('terminal-os-badge');
const terminalPwBadge = $('terminal-pw-badge');

// ── Open/Close ─────────────────────────────────────────────────

function openTerminalPanel() {
    terminalWidget.classList.add('open');
    terminalWidget.setAttribute('aria-hidden', 'false');
    terminalToggleBtn.classList.add('active');
    loadTerminalStatus();
}

function closeTerminalPanel() {
    terminalWidget.classList.remove('open');
    terminalWidget.setAttribute('aria-hidden', 'true');
    terminalToggleBtn.classList.remove('active');
}

if (terminalToggleBtn) terminalToggleBtn.addEventListener('click', () => {
    terminalWidget.classList.contains('open') ? closeTerminalPanel() : openTerminalPanel();
});

if (terminalClose) terminalClose.addEventListener('click', closeTerminalPanel);

// ── Status check ───────────────────────────────────────────────

async function loadTerminalStatus() {
    try {
        const res = await fetch(`${API}/terminal/status`);
        const data = await res.json();
        if (terminalOsBadge) terminalOsBadge.textContent = `OS: ${data.os} (Python ${data.python_version})`;
        if (terminalPwBadge) {
            terminalPwBadge.textContent = data.playwright_available ? '🌐 Playwright ✓' : '🌐 Playwright: not installed';
            terminalPwBadge.style.color = data.playwright_available ? '#6ee7b7' : '#f87171';
        }
    } catch (e) {
        if (terminalOsBadge) terminalOsBadge.textContent = 'Status unavailable';
    }
}

// ── Print a line to terminal output ────────────────────────────

function termPrint(text, cls = 'terminal-out') {
    const line = document.createElement('div');
    line.className = `terminal-line ${cls}`;
    line.textContent = text;
    terminalOutput.appendChild(line);
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
}

// ── Run command via API ────────────────────────────────────────

async function runTerminalCommand(command) {
    if (!command.trim()) return;
    termPrint(`$ ${command}`, 'terminal-cmd');

    try {
        const res = await fetch(`${API}/terminal/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        const data = await res.json();

        if (data.success) {
            if (data.output && data.output !== '(no output)') {
                data.output.split('\n').forEach(line => termPrint(line, 'terminal-out'));
            } else {
                termPrint('(completed, no output)', 'terminal-info');
            }
        } else {
            const err = data.error || 'Unknown error';
            err.split('\n').forEach(line => termPrint(line, 'terminal-err'));
        }
    } catch (e) {
        termPrint(`Network error: ${e.message}`, 'terminal-err');
    }
}

// ── Input handling ─────────────────────────────────────────────

if (terminalInput) {
    terminalInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            const cmd = terminalInput.value.trim();
            terminalInput.value = '';
            runTerminalCommand(cmd);
        }
    });
}

if (terminalRunBtn) {
    terminalRunBtn.addEventListener('click', () => {
        const cmd = terminalInput.value.trim();
        terminalInput.value = '';
        runTerminalCommand(cmd);
    });
}

// ── Auto-open terminal panel when Natasha executes a command ───

function _detectTerminalOutput(text) {
    if (!text) return false;
    const markers = ['Command executed:', 'Folder created:', 'File created:', 'Opening folder:', 'Opening file:', 'Launching **', 'Opening **'];
    return markers.some(m => text.includes(m));
}

// Lightweight post-message hook: show terminal panel & echo result
document.addEventListener('natasha:action-result', (e) => {
    openTerminalPanel();
    termPrint(e.detail.replace(/\*\*/g, '').replace(/`/g, ''), 'terminal-ok');
});
