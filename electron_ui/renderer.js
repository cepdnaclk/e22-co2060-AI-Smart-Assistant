const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const closeBtn = document.getElementById('close-btn');
let thinkingBubble = null; // Track the "thinking..." indicator
const minBtn = document.getElementById('min-btn');

const { ipcRenderer } = require('electron');
let ws = null;
let reconnectTimer = null;
let isConnected = false;

function connectWebSocket() {
    ws = new WebSocket('ws://127.0.0.1:8000/ws');

    ws.onopen = () => {
        isConnected = true;
        console.log('Connected to WebSocket server');
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            if (data.action) {
                if (data.action === 'hide') {
                    ipcRenderer.send('hide-window');
                } else if (data.action === 'minimize') {
                    ipcRenderer.send('minimize-window');
                } else if (data.action === 'quit') {
                    window.close();
                }
                return;
            }

            if (data.sender === 'system') {
                removeThinking();
            }

            ipcRenderer.send('show-window');
            addMessage(data.text, data.sender);
        } catch (e) {
            removeThinking();
            ipcRenderer.send('show-window');
            addMessage(event.data, 'system');
        }
    };

    ws.onclose = () => {
        isConnected = false;
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
    ipcRenderer.send('quit-app');
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

function typeWriter(bubble, text, speed = 18) {
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
        chatHistory.appendChild(row);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        setTimeout(() => {
            typeWriter(bubble, text);
        }, 600);
    }

    chatHistory.scrollTop = chatHistory.scrollHeight;
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

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
