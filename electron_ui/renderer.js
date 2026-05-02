const ws = new WebSocket('ws://localhost:8000/ws');

const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const closeBtn = document.getElementById('close-btn');
let thinkingBubble = null; // Track the "thinking..." indicator
const minBtn = document.getElementById('min-btn');

const { ipcRenderer } = require('electron');

closeBtn.addEventListener('click', () => {
    ipcRenderer.send('hide-window');
});

minBtn.addEventListener('click', () => {
    ipcRenderer.send('minimize-window');
});

ws.onopen = () => {
    console.log('Connected to WebSocket server');
};

ws.onmessage = (event) => {
    try {
        const data = JSON.parse(event.data);

        // Handle action messages (hide, quit) without showing the window
        if (data.action) {
            if (data.action === 'hide') {
                ipcRenderer.send('hide-window');
            } else if (data.action === 'quit') {
                window.close();
            }
            return;
        }

        // Remove the thinking indicator when an AI response arrives
        if (data.sender === 'system') {
            removeThinking();
        }

        // Only show the window for actual chat messages
        ipcRenderer.send('show-window');
        addMessage(data.text, data.sender);
    } catch (e) {
        // Fallback for simple string
        removeThinking();
        ipcRenderer.send('show-window');
        addMessage(event.data, 'system');
    }
};

ws.onclose = () => {
    console.log('Disconnected from WebSocket server');
};

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
    if (text) {
        ws.send(text);
        chatInput.value = '';
        chatInput.focus();
        // Show "Thinking..." after user sends a message
        // Small delay so the user message appears first
        setTimeout(showThinking, 100);
    }
}

sendBtn.addEventListener('click', sendMessage);

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
