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


// ══════════════════════════════════════════════════════════════════════════
//  ACTIVITY OVERLAY  — Perplexity-style live action popup
//  Connects to /activity/stream SSE. Shows what Natasha is doing in real-time.
// ══════════════════════════════════════════════════════════════════════════

const activityOverlay = $('activity-overlay');
const activitySteps   = $('activity-steps');
const activityClose   = $('activity-close');

let _actSSE       = null;
let _actTimer     = null;
const MAX_STEPS   = 30;

function _connectActivityStream() {
    if (_actSSE) return;
    try {
        _actSSE = new EventSource(`${API}/activity/stream`);
        _actSSE.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.heartbeat) return;
                if (data.step) _showActivityStep(data.step);
            } catch (_) {}
        };
        _actSSE.onerror = () => {
            _actSSE?.close();
            _actSSE = null;
            setTimeout(_connectActivityStream, 3000);
        };
        console.log('[Activity] SSE connected');
    } catch (e) {
        console.warn('[Activity] connect failed:', e);
    }
}

function _showActivityStep(step) {
    if (!step || step.includes('heartbeat')) return;

    // Show overlay
    activityOverlay?.classList.remove('hidden');
    clearTimeout(_actTimer);

    // Remove 'latest' highlight from previous step
    activitySteps?.querySelectorAll('.activity-step.latest')
        .forEach(el => el.classList.remove('latest'));

    // Add new step
    const div = document.createElement('div');
    div.className = 'activity-step latest';
    div.textContent = step;
    activitySteps?.appendChild(div);

    // Trim old steps
    while (activitySteps && activitySteps.children.length > MAX_STEPS) {
        activitySteps.removeChild(activitySteps.firstChild);
    }
    if (activitySteps) activitySteps.scrollTop = activitySteps.scrollHeight;

    // Auto-hide 5s after last step
    _actTimer = setTimeout(() => {
        activityOverlay?.classList.add('hidden');
    }, 5000);
}

function _clearActivitySteps() {
    if (activitySteps) activitySteps.innerHTML = '';
}

activityClose?.addEventListener('click', () => {
    activityOverlay?.classList.add('hidden');
    _clearActivitySteps();
});

// Connect after page loads
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(_connectActivityStream, 1500);
});


// ══════════════════════════════════════════════════════════════════════════
//  DESKTOP CONTROL PANEL  — Keyboard + Mouse manual control
// ══════════════════════════════════════════════════════════════════════════

const desktopPanel      = $('desktop-panel');
const desktopPanelClose = $('desktop-panel-close');
const desktopStatusMsg  = $('desktop-status-msg');
const kbText            = $('kb-text');
const kbDelay           = $('kb-delay');
const kbTypeBtn         = $('kb-type-btn');
const mouseXInput       = $('mouse-x');
const mouseYInput       = $('mouse-y');
const mouseMoveBtn      = $('mouse-move-btn');
const mouseGetPosBtn    = $('mouse-get-pos-btn');
const mousePosDisplay   = $('mouse-pos-display');

// ── Tab switching ───────────────────────────────────────────────
document.querySelectorAll('.dtab').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.dtab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        document.querySelectorAll('.dtab-content').forEach(c => c.classList.add('hidden'));
        $(`dtab-${tab}`)?.classList.remove('hidden');
    });
});

// ── Panel open/close ────────────────────────────────────────────
function openDesktopPanel() {
    desktopPanel?.classList.remove('hidden');
    $('desktop-toggle-btn')?.classList.add('active');
}
function closeDesktopPanel() {
    desktopPanel?.classList.add('hidden');
    $('desktop-toggle-btn')?.classList.remove('active');
}

$('desktop-toggle-btn')?.addEventListener('click', () => {
    desktopPanel?.classList.contains('hidden') ? openDesktopPanel() : closeDesktopPanel();
});
desktopPanelClose?.addEventListener('click', closeDesktopPanel);

// ── Status display ──────────────────────────────────────────────
function _deskStatus(msg, isError = false) {
    if (!desktopStatusMsg) return;
    desktopStatusMsg.style.color = isError ? '#f87171' : '#4ade80';
    desktopStatusMsg.textContent = msg;
    setTimeout(() => { if (desktopStatusMsg) desktopStatusMsg.textContent = ''; }, 3500);
}

// ── API helpers ─────────────────────────────────────────────────
async function _apiPost(endpoint, body) {
    const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    return res.json();
}

async function _apiGet(endpoint) {
    const res = await fetch(`${API}${endpoint}`);
    return res.json();
}

// ── Keyboard: Type text ─────────────────────────────────────────
kbTypeBtn?.addEventListener('click', async () => {
    const text  = kbText?.value?.trim();
    const delay = parseFloat(kbDelay?.value || '2');
    if (!text) { _deskStatus('Enter some text first', true); return; }

    kbTypeBtn.disabled = true;
    kbTypeBtn.textContent = `⌨️ Starting in ${delay}s...`;
    _deskStatus(`Click your target window! Typing in ${delay}s...`);

    try {
        const data = await _apiPost('/keyboard/type', { text, delay, interval: 0.02 });
        if (data.success) {
            _deskStatus(`✓ Typed ${data.chars} characters`);
            if (kbText) kbText.value = '';
        } else {
            _deskStatus(data.message || 'Failed', true);
        }
    } catch (e) {
        _deskStatus('Network error', true);
    } finally {
        kbTypeBtn.disabled = false;
        kbTypeBtn.textContent = '⌨️ Type Now';
    }
});

// ── Keyboard: Shortcuts ─────────────────────────────────────────
document.querySelectorAll('.kb-sc').forEach(btn => {
    btn.addEventListener('click', async () => {
        const keys = btn.dataset.keys?.split(',');
        if (!keys) return;
        try {
            const data = await _apiPost('/keyboard/hotkey', { keys });
            _deskStatus(data.success ? `✓ ${btn.textContent}` : (data.message || 'Failed'), !data.success);
        } catch (e) {
            _deskStatus('Error', true);
        }
    });
});

// ── Keyboard: Single keys ───────────────────────────────────────
document.querySelectorAll('.kb-key').forEach(btn => {
    btn.addEventListener('click', async () => {
        const key = btn.dataset.key;
        if (!key) return;
        try {
            const data = await _apiPost('/keyboard/press', { key });
            _deskStatus(data.success ? `✓ ${btn.textContent}` : (data.message || 'Failed'), !data.success);
        } catch (e) {
            _deskStatus('Error', true);
        }
    });
});

// ── Mouse: Move ─────────────────────────────────────────────────
mouseMoveBtn?.addEventListener('click', async () => {
    const x = parseInt(mouseXInput?.value);
    const y = parseInt(mouseYInput?.value);
    if (isNaN(x) || isNaN(y)) { _deskStatus('Enter X and Y coordinates', true); return; }
    try {
        const data = await _apiPost('/mouse/move', { x, y });
        _deskStatus(data.success ? `✓ Mouse at (${x}, ${y})` : (data.message || 'Failed'), !data.success);
    } catch (e) {
        _deskStatus('Error', true);
    }
});

// ── Mouse: Click buttons ────────────────────────────────────────
document.querySelectorAll('.mouse-click-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        const button = btn.dataset.button || 'left';
        try {
            const data = await _apiPost('/mouse/click', { button, double: false });
            _deskStatus(data.success ? `✓ ${btn.textContent}` : (data.message || 'Failed'), !data.success);
        } catch (e) {
            _deskStatus('Error', true);
        }
    });
});

document.querySelector('.mouse-dbl-btn')?.addEventListener('click', async () => {
    try {
        const data = await _apiPost('/mouse/click', { button: 'left', double: true });
        _deskStatus(data.success ? '✓ Double clicked' : (data.message || 'Failed'), !data.success);
    } catch (e) {
        _deskStatus('Error', true);
    }
});

// ── Mouse: Scroll buttons ───────────────────────────────────────
document.querySelectorAll('.mouse-scroll-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        const amount = parseInt(btn.dataset.amount || '5');
        try {
            const data = await _apiPost('/mouse/scroll', { amount });
            _deskStatus(data.success ? `✓ ${btn.textContent}` : (data.message || 'Failed'), !data.success);
        } catch (e) {
            _deskStatus('Error', true);
        }
    });
});

// ── Mouse: Get position ─────────────────────────────────────────
mouseGetPosBtn?.addEventListener('click', async () => {
    try {
        const data = await _apiGet('/mouse/position');
        if (data.success && mousePosDisplay) {
            mousePosDisplay.textContent = `X: ${data.x}  Y: ${data.y}`;
            _deskStatus(`Position: (${data.x}, ${data.y})`);
        }
    } catch (e) {
        _deskStatus('Error getting position', true);
    }
});

// ── Auto-open desktop panel when Natasha uses keyboard/mouse ────
document.addEventListener('natasha:type-text', () => openDesktopPanel());


// ══════════════════════════════════════════════════════════════════════════
//  WIFI SENSING PANEL — Presence Detection Visualization
// ══════════════════════════════════════════════════════════════════════════

const wifiPanel        = $('wifi-panel');
const wifiPanelClose   = $('wifi-panel-close');
const wifiToggleBtn    = $('wifi-toggle-btn');
const wifiStatusBadge  = $('wifi-status-badge');
const wifiViz          = $('wifi-viz');
const wifiCalibrating = $('wifi-calibrating');
const wifiMetrics     = $('wifi-metrics');
const wifiConfidence  = $('wifi-confidence');
const wifiChart       = $('wifi-chart');
const wifiLogContent  = $('wifi-log-content');
const wifiSparkline   = $('wifi-sparkline');
const wifiHeatmap     = $('wifi-heatmap');

// 3D Map integration variables
const wifi3dToggle    = $('wifi-3d-toggle');
const wifi2dContainer = $('wifi-2d-container');
const wifi3dContainer = $('wifi-3d-container');
const wifi3dFrame     = $('wifi-3d-frame');
let is3dMode = false;

let wifiSensing = false;
let wifiSSE = null;
let chartData = [];
let rssiHistory = [];
const maxChartPoints = 30;
const maxRssiHistory = 60;
let signalFieldData = [];

// ── Toggle 3D Mode ──────────────────────────────────────────────────
wifi3dToggle?.addEventListener('click', () => {
    is3dMode = !is3dMode;
    if (is3dMode) {
        wifi2dContainer.classList.add('hidden');
        wifi3dContainer.classList.remove('hidden');
        wifi3dToggle.textContent = 'View 2D Mode';
        wifi3dToggle.classList.add('stop'); // use red style for active
    } else {
        wifi2dContainer.classList.remove('hidden');
        wifi3dContainer.classList.add('hidden');
        wifi3dToggle.textContent = 'View 3D Mode';
        wifi3dToggle.classList.remove('stop');
    }
});

// ── Panel open/close ───────────────────────────────────────────────
function openWifiPanel() {
    wifiPanel?.classList.remove('hidden');
    $('wifi-toggle-nav')?.classList.add('active');
}
function closeWifiPanel() {
    wifiPanel?.classList.add('hidden');
    $('wifi-toggle-nav')?.classList.remove('active');
}

$('wifi-toggle-nav')?.addEventListener('click', () => {
    wifiPanel?.classList.contains('hidden') ? openWifiPanel() : closeWifiPanel();
});
wifiPanelClose?.addEventListener('click', closeWifiPanel);

// ── Check hardware on load ────────────────────────────────────────
(async () => {
    try {
        const hw = await _apiGet('/wifi-sensing/hardware');
        const hwStatus = $('hw-status');
        if (hwStatus) {
            hwStatus.textContent = hw.rssi_available ? `RSSI Mode (${hw.platform})` : 'Not Available';
        }
    } catch (e) {
        if ($('hw-status')) $('hw-status').textContent = 'Error';
    }
})();

// ── Toggle WiFi sensing ────────────────────────────────────────────
wifiToggleBtn?.addEventListener('click', async () => {
    if (wifiSensing) {
        await _apiPost('/wifi-sensing/stop', {});
        wifiSensing = false;
        wifiStatusBadge.textContent = 'OFF';
        wifiStatusBadge.className = 'wifi-badge off';
        wifiToggleBtn.textContent = 'Start Sensing';
        wifiToggleBtn.classList.remove('stop');
        wifiViz.classList.add('hidden');
        wifiSSE?.close();
        wifiSSE = null;
    } else {
        const res = await _apiPost('/wifi-sensing/start', { mode: 'auto' });
        wifiSensing = true;
        wifiStatusBadge.textContent = 'ON';
        wifiStatusBadge.className = 'wifi-badge on';
        wifiToggleBtn.textContent = 'Stop Sensing';
        wifiToggleBtn.classList.add('stop');
        wifiViz.classList.remove('hidden');
        wifiCalibrating.style.display = 'flex';
        wifiMetrics.style.display = 'none';
        wifiConfidence.style.display = 'none';
        startWifiStream();
    }
});

// ── Start SSE stream ───────────────────────────────────────────────
function startWifiStream() {
    wifiSSE = new EventSource(`${API}/wifi-sensing/stream`);
    
    wifiSSE.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            
            if (data.type === 'started' || data.type === 'calibration_complete') {
                if (data.type === 'calibration_complete') {
                    wifiCalibrating.style.display = 'none';
                    wifiMetrics.style.display = 'flex';
                    wifiConfidence.style.display = 'flex';
                    addWifiLog('Calibration complete. Monitoring...');
                }
            }
            else if (data.type === 'detection') {
                updateWifiMetrics(data);
            }
            else if (data.type === 'heartbeat' && data.status) {
                // Update from heartbeat - convert status to detection format
                const status = data.status;
                updateWifiMetrics({
                    presence: status.presence_detected || false,
                    motion_level: status.motion_level || 'none',
                    confidence: status.confidence || 0,
                    persons_estimate: status.persons_estimate || 0,
                    variance: status.rssi_variance || 0,
                    mean_rssi: status.rssi_sample || -65,
                    std: Math.sqrt(status.rssi_variance || 0.1),
                    motion_band_power: status.confidence ? status.confidence * 0.1 : 0.05,
                    breathing_band_power: status.confidence ? status.confidence * 0.03 : 0.02,
                });
            }
        } catch (err) {
            console.error('WiFi stream parse error:', err);
        }
    };
    
    wifiSSE.onerror = () => {
        wifiSSE?.close();
        setTimeout(() => {
            if (wifiSensing) startWifiStream();
        }, 3000);
    };
}

// ── Update metrics display ────────────────────────────────────────
function updateWifiMetrics(data) {
    const presenceVal = $('presence-value');
    const motionVal   = $('motion-value');
    const personVal   = $('person-value');
    const confFill    = $('conf-fill');
    const confPercent = $('conf-percent');
    const presenceInd = $('presence-indicator');
    const motionFill  = $('motion-fill');
    const motionCard  = document.querySelector('.motion-card');
    
    const presence = data.presence;
    const motion = data.motion_level || 'none';
    const persons = data.persons_estimate || 0;
    const confidence = Math.round((data.confidence || 0) * 100);
    
    presenceVal.textContent = presence ? 'Detected' : 'None';
    presenceInd.classList.toggle('detected', presence);
    document.querySelector('.presence-card')?.classList.toggle('detected', presence);
    
    motionVal.textContent = motion.charAt(0).toUpperCase() + motion.slice(1);
    motionCard.classList.remove('high', 'medium', 'low');
    motionCard.classList.add(motion);
    const motionPct = motion === 'high' ? 100 : motion === 'medium' ? 60 : motion === 'low' ? 30 : 0;
    motionFill.style.width = motionPct + '%';
    motionFill.classList.remove('high', 'medium', 'low');
    motionFill.classList.add(motion);
    
    personVal.textContent = persons;
    confFill.style.width = confidence + '%';
    confPercent.textContent = confidence + '%';
    
    addChartPoint(data.variance || 0);
    
    // Update detailed metrics
    if ($('mean-rssi')) $('mean-rssi').textContent = data.mean_rssi ? data.mean_rssi.toFixed(1) + ' dBm' : '--';
    if ($('std-dev')) $('std-dev').textContent = data.std ? data.std.toFixed(2) : '--';
    if ($('motion-power')) $('motion-power').textContent = data.motion_band_power ? data.motion_band_power.toFixed(3) : '--';
    if ($('breathing-power')) $('breathing-power').textContent = data.breathing_band_power ? data.breathing_band_power.toFixed(3) : '--';
    
    // Update RSSI history (sparkline)
    if (data.mean_rssi) {
        rssiHistory.push(data.mean_rssi);
        if (rssiHistory.length > maxRssiHistory) rssiHistory.shift();
        drawSparkline();
    }
    
    // Update signal field heatmap (2D canvas)
    if (data.signal_field && data.signal_field.values) {
        signalFieldData = data.signal_field.values;
        drawHeatmap();
    } else {
        // Generate simulated signal field based on presence
        updateSignalField(presence, motion);
    }
    
    // Bridge data to 3D IFrame if it's open
    if (wifi3dFrame && wifi3dFrame.contentWindow) {
        // Map motion level to confidence for the 3D visualizer
        const conf = presence ? (motion === 'high' ? 0.95 : motion === 'medium' ? 0.75 : 0.4) : 0;
        
        const payload = {
            type: 'wifi_state',
            data: {
                persons: presence ? [{
                    id: 1, 
                    x: (Math.random() - 0.5) * 2, // random position between -1 and 1
                    y: 0,
                    z: (Math.random() - 0.5) * 2,
                    confidence: conf,
                    motionLevel: motion
                }] : [],
                zoneOccupancy: presence ? [1, 0, 0, 0] : [0, 0, 0, 0],
                signalData: {
                    rxPoints: Array.from({length: 10}, () => Math.random() * (presence ? 0.8 : 0.2)),
                    txPower: data.mean_rssi || -60
                }
            }
        };
        wifi3dFrame.contentWindow.postMessage(payload, '*');
    }
    
    if (presence) {
        addWifiLog(`${motion} motion detected: ${persons} person, ${confidence}% confidence`);
    } else {
        addWifiLog('No presence detected');
    }
}

// ── Generate simulated signal field ─────────────────────────────────
function updateSignalField(presence, motionLevel) {
    const gridSize = 14;
    const values = [];
    const cx = gridSize / 2, cy = gridSize / 2;
    const motionFactor = motionLevel === 'high' ? 0.8 : motionLevel === 'medium' ? 0.5 : motionLevel === 'low' ? 0.3 : 0.1;
    
    for (let i = 0; i < gridSize * gridSize; i++) {
        const ix = i % gridSize;
        const iz = Math.floor(i / gridSize);
        const dist = Math.sqrt((ix - cx) ** 2 + (iz - cy) ** 2);
        let v = Math.max(0, 1 - dist / (gridSize * 0.6)) * 0.2;
        if (presence) {
            v += Math.random() * motionFactor;
        }
        values.push(Math.min(1, Math.max(0, v)));
    }
    signalFieldData = values;
    drawHeatmap();
}

// ── Draw Sparkline (RSSI History) ───────────────────────────────────
function drawSparkline() {
    const canvas = wifiSparkline;
    if (!canvas || rssiHistory.length < 2) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    
    ctx.clearRect(0, 0, w, h);
    
    const minRssi = Math.min(...rssiHistory) - 5;
    const maxRssi = Math.max(...rssiHistory) + 5;
    const range = maxRssi - minRssi || 1;
    const step = w / (maxRssiHistory - 1);
    
    ctx.beginPath();
    ctx.strokeStyle = '#22c55e';
    ctx.lineWidth = 1.5;
    
    rssiHistory.forEach((val, i) => {
        const x = i * step;
        const y = h - ((val - minRssi) / range) * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
    
    // Fill under curve
    ctx.lineTo((rssiHistory.length - 1) * step, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = 'rgba(34, 197, 94, 0.2)';
    ctx.fill();
}

// ── Draw Heatmap (Signal Field) ──────────────────────────────────────
function drawHeatmap() {
    const canvas = wifiHeatmap;
    if (!canvas || signalFieldData.length === 0) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    
    const gridSize = Math.ceil(Math.sqrt(signalFieldData.length));
    const cellW = w / gridSize;
    const cellH = h / gridSize;
    
    ctx.clearRect(0, 0, w, h);
    
    signalFieldData.forEach((val, i) => {
        const ix = i % gridSize;
        const iy = Math.floor(i / gridSize);
        const x = ix * cellW;
        const y = iy * cellH;
        
        // Color from blue (low) to green to yellow to red (high)
        const r = val < 0.5 ? 0 : Math.min(255, (val - 0.5) * 2 * 255);
        const g = val < 0.5 ? val * 2 * 255 : Math.min(255, 255 - (val - 0.5) * 2 * 255);
        const b = val < 0.5 ? 255 - val * 2 * 255 : 0;
        
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.8)`;
        ctx.fillRect(x, y, cellW - 1, cellH - 1);
    });
}

// ── Chart functions ───────────────────────────────────────────────
function addChartPoint(value) {
    chartData.push(value);
    if (chartData.length > maxChartPoints) chartData.shift();
    drawChart();
}

function drawChart() {
    const canvas = wifiChart;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    
    ctx.clearRect(0, 0, w, h);
    
    if (chartData.length < 2) return;
    
    const maxVal = Math.max(...chartData, 1);
    const step = w / (maxChartPoints - 1);
    
    ctx.beginPath();
    ctx.strokeStyle = '#22c55e';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    chartData.forEach((val, i) => {
        const x = i * step;
        const y = h - (val / maxVal) * h * 0.9 - 5;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
    
    ctx.lineTo((chartData.length - 1) * step, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = 'rgba(34, 197, 94, 0.15)';
    ctx.fill();
}

function addWifiLog(msg) {
    if (!wifiLogContent) return;
    const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const line = document.createElement('div');
    line.textContent = `[${time}] ${msg}`;
    wifiLogContent.appendChild(line);
    wifiLogContent.scrollTop = wifiLogContent.scrollHeight;
}


// ══════════════════════════════════════════════════════════════════════════
//  UPGRADED GREET  — uses /greet endpoint for time-aware Edge TTS greeting
// ══════════════════════════════════════════════════════════════════════════

(function _upgradeGreet() {
    // Replace the old _speakWelcome with one that uses /greet
    let _greetDone = false;

    function _doGreet() {
        if (_greetDone) return;
        _greetDone = true;

        fetch(`${API}/greet`)
            .then(r => r.json())
            .then(data => {
                // Update welcome title
                if (welcomeTitle && data.greeting) {
                    welcomeTitle.textContent = data.greeting.replace(', Boss.','').replace(', Boss?','');
                }
                // Play Edge TTS greeting audio
                if (data.audio && ttsPlayer && ttsPlayer.enabled) {
                    playEdgeTTSAudio(data.audio);
                }
            })
            .catch(() => {
                // Fallback to local greeting text
                if (welcomeTitle) welcomeTitle.textContent = _getGreetingText();
            });
    }

    // Fire on first user interaction (bypasses browser autoplay policy)
    ['click', 'keydown', 'touchstart'].forEach(evt => {
        document.addEventListener(evt, () => {
            setTimeout(_doGreet, 300);
        }, { once: true });
    });

    // Also set title text immediately (no audio until interaction)
    if (welcomeTitle) welcomeTitle.textContent = _getGreetingText();
})();


// ══════════════════════════════════════════════════════════════════════════
//  WIFI SENSING PANEL — Presence Detection Visualization
// ══════════════════════════════════════════════════════════════════════════


