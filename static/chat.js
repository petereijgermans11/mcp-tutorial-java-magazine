// Generate or retrieve persistent thread_id
let thread_id = localStorage.getItem('thread_id');
if (!thread_id) {
    if (window.crypto && window.crypto.randomUUID) {
        thread_id = crypto.randomUUID();
    } else {
        thread_id = Math.random().toString(36).substring(2) + Date.now();
    }
    localStorage.setItem('thread_id', thread_id);
}

const chatWindow = document.getElementById('chat-window');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');

// Add dark mode toggle button
document.getElementById('sidebar').insertAdjacentHTML('beforeend', '<button id="dark-mode-btn" style="width:100%;margin-top:10px;">🌙 Dark Mode</button>');
const darkModeBtn = document.getElementById('dark-mode-btn');

// Apply dark mode if set
if (localStorage.getItem('dark_mode') === 'true') {
    document.body.classList.add('dark');
    darkModeBtn.textContent = '☀️ Light Mode';
}

darkModeBtn.onclick = function() {
    document.body.classList.toggle('dark');
    const isDark = document.body.classList.contains('dark');
    localStorage.setItem('dark_mode', isDark);
    darkModeBtn.textContent = isDark ? '☀️ Light Mode' : '🌙 Dark Mode';
};

function appendMessage(text, sender) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message ' + sender;
    msgDiv.innerText = text;
    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function sendMessage(text, showUserBubble = true) {
    if (!text) return;
    if (showUserBubble) appendMessage(text, 'user');
    userInput.value = '';
    userInput.disabled = true;
    sendBtn.disabled = true;

    // Placeholder for AI message while waiting
    const aiMsgDiv = document.createElement('div');
    aiMsgDiv.className = 'message ai';
    aiMsgDiv.innerText = '...';
    chatWindow.appendChild(aiMsgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    (async () => {
        try {
            const formData = new URLSearchParams();
            formData.append('user_input', text);
            formData.append('thread_id', thread_id);
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData.toString()
            });
            if (!response.ok) {
                aiMsgDiv.innerText = '[Error: ' + response.status + ']';
            } else {
                // Streaming support (if backend supports it)
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let aiMsg = '';
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value);
                    if (chunk.startsWith('\n__FINAL__:')) {
                        aiMsgDiv.innerText = chunk.replace('\n__FINAL__:', '');
                        break;
                    } else if (chunk.includes('__TOOL_CALL__:')) {
                        // Tool call message
                        const msg = chunk.split('__TOOL_CALL__:')[1].trim();
                        const toolDiv = document.createElement('div');
                        toolDiv.className = 'message tool';
                        toolDiv.innerHTML = '<b>Tool Call:</b> <span>' + msg + '</span>';
                        chatWindow.appendChild(toolDiv);
                        chatWindow.scrollTop = chatWindow.scrollHeight;
                        continue;
                    } else if (chunk.includes('__TOOL_CALL_RESULT__:')) {
                        // Tool result message
                        const msg = chunk.split('__TOOL_CALL_RESULT__:')[1].trim();
                        const toolDiv = document.createElement('div');
                        toolDiv.className = 'message tool';
                        toolDiv.innerHTML = '<b>Tool Result:</b> <span>' + msg + '</span>';
                        chatWindow.appendChild(toolDiv);
                        chatWindow.scrollTop = chatWindow.scrollHeight;
                        continue;
                    } else {
                        aiMsg += chunk;
                        aiMsgDiv.innerText = aiMsg;
                    }
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }
            }
        } catch (err) {
            aiMsgDiv.innerText = '[Network error]';
        }
        userInput.disabled = false;
        sendBtn.disabled = false;
        userInput.focus();
    })();
}

sendBtn.onclick = function() {
    const text = userInput.value.trim();
    sendMessage(text);
};

userInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendBtn.onclick();
});

// On page load, if chat is empty, send 'who are you' as the first message (hide user bubble)
window.addEventListener('DOMContentLoaded', function() {
    if (chatWindow.children.length === 0) {
        sendMessage('who are you', false);
    }
});

newChatBtn.onclick = function() {
    localStorage.removeItem('thread_id');
    thread_id = null;
    // Clear chat window
    chatWindow.innerHTML = '';
    // Generate new thread_id
    if (window.crypto && window.crypto.randomUUID) {
        thread_id = crypto.randomUUID();
    } else {
        thread_id = Math.random().toString(36).substring(2) + Date.now();
    }
    localStorage.setItem('thread_id', thread_id);
    // Send 'who are you' as the first message in the new chat (hide user bubble)
    sendMessage('who are you', false);
}; 