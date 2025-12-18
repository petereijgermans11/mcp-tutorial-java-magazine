// Generate new thread_id on each page load
let thread_id = crypto.randomUUID();

const chatWindow = document.getElementById('chat-window');
const mainContainer = document.getElementById('main');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');

// Add dark mode toggle button
document.getElementById('sidebar').insertAdjacentHTML('beforeend', '<button id="dark-mode-btn" style="width:100%;margin-top:10px;">🌙 Dark Mode</button>');
const darkModeBtn = document.getElementById('dark-mode-btn');

// Apply dark mode by default (unless explicitly set to false)
if (localStorage.getItem('dark_mode') !== 'false') {
    document.body.classList.add('dark');
    darkModeBtn.textContent = '☀️ Light Mode';
}

darkModeBtn.onclick = function() {
    document.body.classList.toggle('dark');
    const isDark = document.body.classList.contains('dark');
    localStorage.setItem('dark_mode', isDark);
    darkModeBtn.textContent = isDark ? '☀️ Light Mode' : '🌙 Dark Mode';
};

// Handle expand/collapse clicks for tool results
chatWindow.addEventListener('click', function(e) {
    if (e.target.classList.contains('expand-btn')) {
        e.stopPropagation();
        const btn = e.target;
        const full = btn.getAttribute('data-full');
        const truncated = btn.getAttribute('data-truncated');
        const contentSpan = btn.parentElement; // The span that contains the content and button
        
        // Escape HTML properly
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        const isExpanded = btn.textContent.trim() === 'collapse';
        
        if (isExpanded) {
            // Collapse: show truncated content (500 chars)
            contentSpan.innerHTML = escapeHtml(truncated) + '<span class="expand-btn" data-full="' + full.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '" data-truncated="' + truncated.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '" style="color:#888;cursor:pointer;text-decoration:underline;margin-left:5px;">...expand</span>';
        } else {
            // Expand: show full content
            contentSpan.innerHTML = escapeHtml(full) + '<span class="expand-btn" data-full="' + full.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '" data-truncated="' + truncated.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '" style="color:#888;cursor:pointer;text-decoration:underline;margin-left:5px;">collapse</span>';
        }
    }
});

function linkifyText(text) {
    // First, convert markdown-style links [text](url) to HTML links
    let processed = text.replace(/\[([^\]]+)\]\(((?:https?:\/\/)?[^\)]+)\)/g, function(match, linkText, url) {
        const fullUrl = url.startsWith('http') ? url : 'https://' + url;
        return '<a href="' + fullUrl + '" target="_blank" rel="noopener noreferrer">' + linkText + '</a>';
    });
    
    // Then, convert bare URLs that are NOT already inside HTML tags
    // Negative lookbehind to avoid matching URLs already in href=""
    processed = processed.replace(/(?<!href="|">)((?:https?:\/\/)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:\/[^\s<]*)?)/g, function(match) {
        // Skip if this looks like it's inside an HTML tag
        if (match.startsWith('http') || match.includes('.')) {
            const url = match.startsWith('http') ? match : 'https://' + match;
            return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + match + '</a>';
        }
        return match;
    });
    
    // Convert newlines to <br> tags for proper line breaks
    processed = processed.replace(/\n/g, '<br>');
    return processed;
}

function appendMessage(text, sender) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message ' + sender;
    msgDiv.innerHTML = linkifyText(text);
    chatWindow.appendChild(msgDiv);
    mainContainer.scrollTop = mainContainer.scrollHeight;
}

function sendMessage(text, showUserBubble = true) {
    if (!text) return;
    if (showUserBubble) appendMessage(text, 'user');
    userInput.value = '';
    userInput.style.height = 'auto';
    userInput.disabled = true;
    sendBtn.disabled = true;

    // Placeholder for AI message while waiting
    let aiMsgDiv = document.createElement('div');
    aiMsgDiv.className = 'message ai';
    aiMsgDiv.innerText = '...';
    chatWindow.appendChild(aiMsgDiv);
    mainContainer.scrollTop = mainContainer.scrollHeight;

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
                aiMsgDiv.innerHTML = linkifyText('[Error: ' + response.status + ']');
            } else {
                // Streaming support (if backend supports it)
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let aiMsg = '';
                let toolsUsed = false;
                let buffer = ''; // Buffer for incomplete chunks
                let finalMessageProcessed = false; // Track if final message was already processed
                let processingIndicator = null; // Reference to loading indicator div
                
                function extractMarker(marker) {
                    const pattern = new RegExp(marker + ':(.+?)(?=\\n__TOOL_CALL__:|\\n__TOOL_CALL_RESULT__:|\\n__FINAL__:|$)', 's');
                    const match = buffer.match(pattern) || buffer.match(new RegExp(marker + ':(.+)$', 's'));
                    if (match) {
                        const content = match[1].trim();
                        buffer = buffer.replace(pattern, '');
                        if (buffer.includes(marker + ':')) {
                            buffer = buffer.replace(new RegExp(marker + ':.*$', 's'), '');
                        }
                        return content;
                    }
                    return null;
                }
                
                function showProcessingIndicator() {
                    if (!processingIndicator) {
                        processingIndicator = document.createElement('div');
                        processingIndicator.className = 'message ai';
                        processingIndicator.innerText = '...';
                        const lastChild = chatWindow.lastElementChild;
                        if (lastChild) {
                            chatWindow.insertBefore(processingIndicator, lastChild.nextSibling);
                        } else {
                            chatWindow.appendChild(processingIndicator);
                        }
                        mainContainer.scrollTop = mainContainer.scrollHeight;
                    } else {
                        const lastChild = chatWindow.lastElementChild;
                        if (lastChild && lastChild !== processingIndicator) {
                            chatWindow.removeChild(processingIndicator);
                            chatWindow.insertBefore(processingIndicator, lastChild.nextSibling);
                        }
                    }
                }
                
                function hideProcessingIndicator() {
                    if (processingIndicator && processingIndicator.parentNode) {
                        processingIndicator.remove();
                        processingIndicator = null;
                    }
                }
                
                function processBuffer() {
                    const markers = ['__TOOL_CALL__', '__TOOL_CALL_RESULT__', '__FINAL__'];
                    const firstMarker = markers.find(m => buffer.includes(m + ':'));
                    
                    if (!firstMarker && !toolsUsed && buffer.trim()) {
                        aiMsg += buffer;
                        aiMsgDiv.innerText = aiMsg;
                        buffer = '';
                        mainContainer.scrollTop = mainContainer.scrollHeight;
                        return;
                    }
                    
                    if (firstMarker) {
                        const firstIndex = buffer.indexOf(firstMarker + ':');
                        if (firstIndex > 0 && !toolsUsed) {
                            aiMsg += buffer.substring(0, firstIndex);
                            aiMsgDiv.innerText = aiMsg;
                            buffer = buffer.substring(firstIndex);
                        }
                    }
                    
                    while (true) {
                        let processed = false;
                        
                        if (buffer.includes('__TOOL_CALL__:')) {
                            const msg = extractMarker('__TOOL_CALL__');
                            if (msg) {
                                if (!toolsUsed) {
                                    aiMsgDiv.remove();
                                    aiMsg = '';
                                    toolsUsed = true;
                                }
                                const toolDiv = document.createElement('div');
                                toolDiv.className = 'message tool';
                                toolDiv.innerHTML = '<b>Tool Call:</b> <span>' + msg + '</span>';
                                chatWindow.appendChild(toolDiv);
                                showProcessingIndicator();
                                processed = true;
                            }
                        }
                        
                        if (buffer.includes('__TOOL_CALL_RESULT__:')) {
                            const msg = extractMarker('__TOOL_CALL_RESULT__');
                            if (msg) {
                                const toolDiv = document.createElement('div');
                                toolDiv.className = 'message tool';
                                if (msg.length > 500) {
                                    const truncated = msg.substring(0, 500);
                                    const contentSpan = document.createElement('span');
                                    contentSpan.innerHTML = truncated + '<span class="expand-btn" data-full="' + msg.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '" data-truncated="' + truncated.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '" style="color:#888;cursor:pointer;text-decoration:underline;margin-left:5px;">...expand</span>';
                                    toolDiv.innerHTML = '<b>Tool Result:</b> ';
                                    toolDiv.appendChild(contentSpan);
                                } else {
                                    toolDiv.innerHTML = '<b>Tool Result:</b> <span>' + msg.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</span>';
                                }
                                chatWindow.appendChild(toolDiv);
                                showProcessingIndicator();
                                processed = true;
                            }
                        }
                        
                        if (buffer.includes('__FINAL__:') && !finalMessageProcessed) {
                            const finalMessage = extractMarker('__FINAL__');
                            if (finalMessage) {
                                hideProcessingIndicator();
                                if (toolsUsed) {
                                    if (aiMsgDiv.parentNode) aiMsgDiv.remove();
                                    aiMsgDiv = document.createElement('div');
                                    aiMsgDiv.className = 'message ai';
                                    chatWindow.appendChild(aiMsgDiv);
                                }
                                aiMsgDiv.innerHTML = linkifyText(finalMessage);
                                finalMessageProcessed = true;
                                processed = true;
                            }
                        }
                        
                        if (!processed) break;
                        mainContainer.scrollTop = mainContainer.scrollHeight;
                    }
                }
                
                while (true) {
                    const { value, done } = await reader.read();
                    
                    if (value) {
                        buffer += decoder.decode(value, { stream: true });
                        processBuffer();
                    }
                    
                    if (done) {
                        let lastLength;
                        do {
                            lastLength = buffer.length;
                            processBuffer();
                        } while (buffer.length !== lastLength && buffer.length > 0);
                        
                        hideProcessingIndicator();
                        
                        userInput.disabled = false;
                        sendBtn.disabled = false;
                        userInput.focus();
                        break;
                    }
                }
            }
        } catch (err) {
            if (aiMsgDiv) {
                aiMsgDiv.innerHTML = linkifyText('[Network error]');
            }
            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();
        }
    })();
}

sendBtn.onclick = function() {
    const text = userInput.value.trim();
    sendMessage(text);
};

// Auto-resize textarea to grow with content
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

userInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        if (e.shiftKey) {
            // Allow default behavior (newline) - input event will handle resize
        } else {
            // Prevent default and send message for Enter alone
            e.preventDefault();
            sendBtn.onclick();
        }
    }
});

// On page load, if chat is empty, send 'who are you' as the first message (hide user bubble)
window.addEventListener('DOMContentLoaded', function() {
    if (chatWindow.children.length === 0) {
        sendMessage('who are you', false);
    }
});

newChatBtn.onclick = function() {
    sessionStorage.removeItem('thread_id');
    thread_id = null;
    // Clear chat window
    chatWindow.innerHTML = '';
    // Generate new thread_id
    if (window.crypto && window.crypto.randomUUID) {
        thread_id = crypto.randomUUID();
    } else {
        thread_id = Math.random().toString(36).substring(2) + Date.now();
    }
    sessionStorage.setItem('thread_id', thread_id);
    // Send 'who are you' as the first message in the new chat (hide user bubble)
    sendMessage('who are you', false);
}; 