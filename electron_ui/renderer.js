const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const closeBtn = document.getElementById('close-btn');
let thinkingBubble = null; // Track the "thinking..." indicator
const minBtn = document.getElementById('min-btn');
const newChatMenuBtn = document.getElementById('new-chat-menu-btn');
const statusDot = document.getElementById('status-dot');
const connectionStatus = document.getElementById('connection-status');
const quickActions = document.querySelectorAll('.quick-actions button');
const menuBtn = document.getElementById('menu-btn');
const quickCaptureBtn = document.getElementById('quick-capture-btn');
const menuDropdown = document.getElementById('menu-dropdown');
const captureMenuBtn = document.getElementById('capture-menu-btn');
const settingsMenuBtn = document.getElementById('settings-menu-btn');
const emptyGreeting = document.getElementById('empty-greeting');
const greetingName = document.getElementById('greeting-name');

const { ipcRenderer } = require('electron');
let ws = null;
let reconnectTimer = null;
let isConnected = false;

function connectWebSocket() {
    const chatPort = process.env.CHAT_SERVER_PORT || '8000';
    ws = new WebSocket(`ws://127.0.0.1:${chatPort}/ws`);

    ws.onopen = () => {
        isConnected = true;
            statusDot.className = 'status-dot online';
            connectionStatus.textContent = 'Online';
        console.log(`Connected to WebSocket server on port ${chatPort}`);
        sendAction('get_settings');
        
        setTimeout(() => {
            updateEmptyState();
        }, 200);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            if (data.action && window.settingsUI && settingsUI.handles(data.action)) {
                settingsUI.handleMessage(data);
                return;
            }

            if (data.action) {
                if (data.action === 'hide') {
                    ipcRenderer.send('hide-window');
                } else if (data.action === 'quit') {
                    window.close();
                } else if (data.action === 'clear') {
                    chatHistory.innerHTML = '';
                    updateEmptyState();
                } else if (data.action === 'thinking') {
                    showThinking();
                } else if (data.action === 'remove_last_assistant') {
                    const messages = chatHistory.querySelectorAll('.message-row.system:not(#thinking-row)');
                    if (messages.length) messages[messages.length - 1].remove();
                }
                return;
            }

            if (data.sender === 'system') {
                removeThinking();
            }

            ipcRenderer.send('show-window');
            addMessage(data.text, data.sender);
        } catch (error) {
            removeThinking();
            ipcRenderer.send('show-window');
            addMessage(event.data, 'system');
        }
    };

    ws.onclose = () => {
        isConnected = false;
            statusDot.className = 'status-dot';
            connectionStatus.textContent = 'Reconnecting';
        console.log('Disconnected from WebSocket server; retrying...');
        reconnectTimer = setTimeout(connectWebSocket, 1000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket connection error:', error);
        ws.close();
    };
}

connectWebSocket();

closeBtn.addEventListener('click', () => {
    ipcRenderer.send('hide-window');
});

minBtn.addEventListener('click', () => {
    ipcRenderer.send('minimize-window');
});

function formatTime() {
    const now = new Date();
    let hours = now.getHours();
    let minutes = now.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    minutes = minutes < 10 ? '0' + minutes : minutes;
    return `${hours}:${minutes} ${ampm}`;
}

function typingPrefs() {
    const general = window.settingsUI && settingsUI.state.settings && settingsUI.state.settings.general;
    return general
        ? { enabled: general.typing_animation, speed: general.typing_speed }
        : { enabled: true, speed: 18 };
}

function typeWriter(bubble, text, speed = typingPrefs().speed) {
    let i = 0;
    bubble.innerHTML = '<span class="cursor">|</span>';
    const cursor = bubble.querySelector('.cursor');

    const interval = setInterval(() => {
        if (i < text.length) {
            cursor.insertAdjacentText('beforebegin', text.charAt(i));
            i++;
            chatHistory.scrollTop = chatHistory.scrollHeight;
        } else {
            clearInterval(interval);
            cursor.remove();
        }
    }, speed);
}

function addMessage(text, sender) {
    const row = document.createElement('div');
    row.className = `message-row ${sender}`;

    const timeString = formatTime();

    const timeSpan = document.createElement('span');
    timeSpan.className = 'time';
    timeSpan.innerText = timeString;

    const bubble = document.createElement('div');
    bubble.className = `bubble ${sender}`;

    if (sender === 'user') {
        bubble.innerText = text;
        row.appendChild(timeSpan);
        row.appendChild(bubble);
        chatHistory.appendChild(row);
    } else {
        // Show typing dots first, then animate text
        bubble.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
        row.appendChild(bubble);
        row.appendChild(timeSpan);
        const actions = document.createElement('div');
        actions.className = 'message-actions';
        const copyButton = document.createElement('button');
        copyButton.textContent = 'Copy';
        copyButton.title = 'Copy response';
        copyButton.addEventListener('click', async () => {
            await navigator.clipboard.writeText(text);
            copyButton.textContent = 'Copied';
            setTimeout(() => { copyButton.textContent = 'Copy'; }, 1200);
        });
        actions.appendChild(copyButton);
        const regenerateButton = document.createElement('button');
        regenerateButton.textContent = 'Regenerate';
        regenerateButton.addEventListener('click', regenerateLastResponse);
        actions.appendChild(regenerateButton);
        row.appendChild(actions);
        chatHistory.appendChild(row);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        if (typingPrefs().enabled) {
            setTimeout(() => {
                typeWriter(bubble, text);
            }, 600);
        } else {
            bubble.innerText = text;
        }
    }

    chatHistory.scrollTop = chatHistory.scrollHeight;
    updateEmptyState();
}

function updateEmptyState() {
    if (chatHistory.children.length === 0) {
        const profile = window.settingsUI && window.settingsUI.state && window.settingsUI.state.profile;
        let name = 'there';
        if (profile) {
            if (profile.nickname && profile.nickname.trim()) {
                name = profile.nickname.trim();
            } else if (profile.full_name && profile.full_name.trim()) {
                name = profile.full_name.trim().split(' ')[0];
            }
        }
        greetingName.textContent = name;
        emptyGreeting.classList.add('show');
    } else {
        emptyGreeting.classList.remove('show');
    }
}

function sendAction(action, extra = {}) {
    if (ws && isConnected && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ ...extra, action }));
        return true;
    }
    return false;
}

menuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    menuDropdown.classList.toggle('show');
});

quickCaptureBtn.addEventListener('click', () => {
    if (!sendAction('capture')) {
        addMessage('Capture is still connecting. Please try again in a moment.', 'system');
    }
});

document.addEventListener('click', (e) => {
    if (!menuDropdown.contains(e.target) && e.target !== menuBtn) {
        menuDropdown.classList.remove('show');
    }
});

captureMenuBtn.addEventListener('click', () => {
    menuDropdown.classList.remove('show');
    if (!sendAction('capture')) {
        addMessage('Capture is still connecting. Please try again in a moment.', 'system');
    }
});

settingsMenuBtn.addEventListener('click', () => {
    menuDropdown.classList.remove('show');
    settingsUI.open();
});

function regenerateLastResponse() {
    if (sendAction('regenerate')) showThinking();
}

function showThinking() {
    removeThinking(); // Clear any existing one first

    const row = document.createElement('div');
    row.className = 'message-row system';
    row.id = 'thinking-row';

    const bubble = document.createElement('div');
    bubble.className = 'bubble system thinking-bubble';
    bubble.innerHTML = '<span class="thinking-label">Thinking</span><span class="thinking-dots-animated"><span></span><span></span><span></span></span>';

    row.appendChild(bubble);
    chatHistory.appendChild(row);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    thinkingBubble = row;
}

function removeThinking() {
    if (thinkingBubble) {
        thinkingBubble.remove();
        thinkingBubble = null;
    }
}

function sendMessage() {
    const text = chatInput.value.trim();
    if (text && ws && isConnected && ws.readyState === WebSocket.OPEN) {
        ws.send(text);
        chatInput.value = '';
        chatInput.focus();
        // Show "Thinking..." after user sends a message
        // Small delay so the user message appears first
        setTimeout(showThinking, 100);
    } else if (text) {
        addMessage('Chat service is still connecting. Please try again in a moment.', 'system');
    }
}

sendBtn.addEventListener('click', sendMessage);

newChatMenuBtn.addEventListener('click', () => {
    menuDropdown.classList.remove('show');
    if (sendAction('clear_history')) {
        chatHistory.innerHTML = '';
        updateEmptyState();
        chatInput.focus();
    }
});

quickActions.forEach((button) => {
    button.addEventListener('click', () => {
        chatInput.value = `${button.dataset.prompt} `;
        chatInput.focus();
    });
});

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
