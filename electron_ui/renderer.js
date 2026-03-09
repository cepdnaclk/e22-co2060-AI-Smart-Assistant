const ws = new WebSocket('ws://localhost:8000/ws');

const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const closeBtn = document.getElementById('close-btn');

const { ipcRenderer } = require('electron');

closeBtn.addEventListener('click', () => {
    // Hide the window via IPC
    ipcRenderer.send('hide-window');
});

ws.onopen = () => {
    console.log('Connected to WebSocket server');
};

ws.onmessage = (event) => {
    ipcRenderer.send('show-window');
    try {
        const data = JSON.parse(event.data);
        addMessage(data.text, data.sender);
    } catch (e) {
        // Fallback for simple string
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

function addMessage(text, sender) {
    const row = document.createElement('div');
    row.className = `message-row ${sender}`;

    const timeString = formatTime();

    const timeSpan = document.createElement('span');
    timeSpan.className = 'time';
    timeSpan.innerText = timeString;

    const bubble = document.createElement('div');
    bubble.className = `bubble ${sender}`;
    bubble.innerText = text;

    if (sender === 'user') {
        row.appendChild(timeSpan);
        row.appendChild(bubble);
    } else {
        row.appendChild(bubble);
        row.appendChild(timeSpan);
    }

    chatHistory.appendChild(row);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function sendMessage() {
    const text = chatInput.value.trim();
    if (text) {
        ws.send(text);
        chatInput.value = '';
        chatInput.focus();
    }
}

sendBtn.addEventListener('click', sendMessage);

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
