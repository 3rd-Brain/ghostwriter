
// Chatbot integration functionality
let chatSessionId = null;

// Generate a random 13-digit session ID
function generateSessionId() {
  return Date.now().toString() + Math.floor(Math.random() * 1000).toString().padStart(3, '0');
}

// Initialize the chat system
function initChat() {
  // Generate a session ID if not already set
  if (!chatSessionId) {
    chatSessionId = generateSessionId();
    console.log("New chat session started with ID:", chatSessionId);
  }
  
  // Set up event listeners
  const messageInput = document.querySelector('.chatbox-input textarea');
  const sendButton = document.querySelector('.send-button');
  const messagesContainer = document.getElementById('chatbox-messages');
  
  // Add a welcome message
  addMessageToChat('bot', 'Hello! How can I assist you today?');
  
  // Send message on button click
  sendButton.addEventListener('click', function() {
    sendMessage();
  });
  
  // Send message on Enter key (but allow Shift+Enter for new lines)
  messageInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}

// Send a message to the API
async function sendMessage() {
  const messageInput = document.querySelector('.chatbox-input textarea');
  const messagesContainer = document.getElementById('chatbox-messages');
  const messageText = messageInput.value.trim();
  
  if (!messageText) return;
  
  // Add user message to chat
  addMessageToChat('user', messageText);
  
  // Clear input
  messageInput.value = '';
  
  // Show loading indicator
  const loadingId = addLoadingIndicator();
  
  try {
    // Send to API
    const response = await fetch('https://clickdown.app.n8n.cloud/webhook/a889d2ae-2159-402f-b326-5f61e90f602e/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        chatInput: messageText,
        sessionId: chatSessionId
      })
    });
    
    if (!response.ok) {
      throw new Error(`API returned status ${response.status}`);
    }
    
    const data = await response.json();
    
    // Remove loading indicator
    removeLoadingIndicator(loadingId);
    
    // Add bot response to chat
    if (data && data.response) {
      addMessageToChat('bot', data.response);
    } else {
      addMessageToChat('bot', 'Sorry, I encountered an error processing your request.');
    }
  } catch (error) {
    console.error('Error sending message:', error);
    
    // Remove loading indicator
    removeLoadingIndicator(loadingId);
    
    // Add error message
    addMessageToChat('bot', 'Sorry, I encountered an error. Please try again later.');
  }
}

// Add a message to the chat container
function addMessageToChat(sender, text) {
  const messagesContainer = document.getElementById('chatbox-messages');
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${sender}-message`;
  
  // Create avatar for bot messages
  if (sender === 'bot') {
    const avatar = document.createElement('div');
    avatar.className = 'bot-avatar';
    avatar.textContent = 'GW';
    messageDiv.appendChild(avatar);
  }
  
  // Create message content
  const messageContent = document.createElement('div');
  messageContent.className = 'message-content';
  messageContent.textContent = text;
  messageDiv.appendChild(messageContent);
  
  // Add timestamp
  const timestamp = document.createElement('div');
  timestamp.className = 'message-timestamp';
  const now = new Date();
  timestamp.textContent = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
  messageDiv.appendChild(timestamp);
  
  // Add to container
  messagesContainer.appendChild(messageDiv);
  
  // Scroll to latest message
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Add a loading indicator to the chat
function addLoadingIndicator() {
  const messagesContainer = document.getElementById('chatbox-messages');
  const loadingId = 'loading-' + Date.now();
  
  const loadingDiv = document.createElement('div');
  loadingDiv.className = 'message bot-message loading';
  loadingDiv.id = loadingId;
  
  const avatar = document.createElement('div');
  avatar.className = 'bot-avatar';
  avatar.textContent = 'GW';
  loadingDiv.appendChild(avatar);
  
  const dots = document.createElement('div');
  dots.className = 'typing-dots';
  dots.innerHTML = '<span></span><span></span><span></span>';
  loadingDiv.appendChild(dots);
  
  messagesContainer.appendChild(loadingDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  
  return loadingId;
}

// Remove the loading indicator
function removeLoadingIndicator(loadingId) {
  const loadingElement = document.getElementById(loadingId);
  if (loadingElement) {
    loadingElement.remove();
  }
}

// Reset the chat session
function resetChatSession() {
  // Make the API call to reset the session on the server
  fetch('/api/chat/reset', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === 'success') {
      // Generate a new session ID
      chatSessionId = generateSessionId();
      console.log("Chat session reset with new ID:", chatSessionId);
      
      // Clear the messages container
      const messagesContainer = document.getElementById('chatbox-messages');
      messagesContainer.innerHTML = '';
      
      // Add a welcome message
      addMessageToChat('bot', 'Chat session reset. How can I assist you today?');
      
      // Show notification
      if (window.showNotification) {
        window.showNotification('Chat session reset successfully');
      }
    }
  })
  .catch(error => {
    console.error('Error resetting chat session:', error);
    if (window.showNotification) {
      window.showNotification('Failed to reset chat session', true);
    }
  });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  initChat();
  
  // Set up reset chat button
  const resetButton = document.getElementById('reset-chat');
  if (resetButton) {
    resetButton.addEventListener('click', resetChatSession);
  }
});
