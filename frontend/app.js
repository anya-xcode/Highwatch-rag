const API_BASE = '/api/v1';

// DOM Elements
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const syncBtn = document.getElementById('sync-btn');
const fileInput = document.getElementById('file-input');
const dropZone = document.getElementById('drop-zone');
const documentList = document.getElementById('document-list');
const docCount = document.getElementById('doc-count');
const toast = document.getElementById('toast');
const systemStatus = document.getElementById('system-status');

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    loadDocuments();
    setupEventListeners();
});

function setupEventListeners() {
    // Send message on click or Enter
    sendBtn.addEventListener('click', handleQuery);
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleQuery();
    });

    // Sync Drive
    syncBtn.addEventListener('click', handleSync);

    // File Upload
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileUpload);
    
    // Drag and Drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--accent-primary)';
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = 'var(--glass-border)';
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        handleFileUpload({ target: { files: e.dataTransfer.files } });
    });
}

// --- API Interactions ---

async function handleQuery() {
    const query = queryInput.value.trim();
    if (!query) return;

    // Add user message to UI
    appendMessage('user', query);
    queryInput.value = '';
    
    // Show typing indicator or state
    const loadingId = appendMessage('system', '<i class="fas fa-spinner fa-spin"></i> Thinking...', true);
    
    try {
        const response = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, top_k: 5 })
        });
        
        const data = await response.json();
        
        // Remove loading and add AI response
        removeMessage(loadingId);
        
        let content = data.answer;
        if (data.sources && data.sources.length > 0) {
            const sourceTags = data.sources.map(s => `<span class="source-tag">${s}</span>`).join('');
            content += `<div class="sources"><strong>Sources:</strong> ${sourceTags}</div>`;
        }
        
        appendMessage('system', content);
    } catch (error) {
        removeMessage(loadingId);
        showToast('Error generating answer', 'error');
        appendMessage('system', 'Sorry, something went wrong while processing your request.');
    }
}

async function handleSync() {
    syncBtn.disabled = true;
    syncBtn.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Syncing...';
    showToast('Starting Google Drive sync...');
    
    try {
        const response = await fetch(`${API_BASE}/sync-drive`, { method: 'POST' });
        const data = await response.json();
        
        showToast(data.message, 'success');

        loadDocuments();
    } catch (error) {
        showToast('Sync failed. Please check your credentials.', 'error');
    } finally {
        syncBtn.disabled = false;
        syncBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Sync G-Drive';
    }
}

async function handleFileUpload(e) {
    const files = e.target.files;
    if (!files.length) return;

    showToast(`Uploading ${files.length} file(s)...`);
    
    const formData = new FormData();
    for (const file of files) {
        formData.append('file', file);
    }

    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        showToast(data.message, 'success');

        loadDocuments();
    } catch (error) {
        showToast('Upload failed', 'error');
    }
}

async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}/documents`);
        const data = await response.json();
        
        documentList.innerHTML = '';
        docCount.textContent = data.documents.length;

        if (data.documents.length === 0) {
            documentList.innerHTML = '<div class="nav-section">No documents indexed yet.</div>';
            return;
        }

        data.documents.forEach(doc => {
            const li = document.createElement('li');
            li.className = 'doc-item';
            const icon = doc.endsWith('.pdf') ? 'fa-file-pdf' : (doc.endsWith('.docx') ? 'fa-file-word' : 'fa-file-alt');
            li.innerHTML = `<i class="fas ${icon}"></i> <span>${doc}</span>`;
            documentList.appendChild(li);
        });
    } catch (error) {
        console.error('Failed to load documents');
    }
}

// --- UI Helpers ---

function appendMessage(role, content, isLoading = false) {
    const id = Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.id = `msg-${id}`;
    
    const icon = role === 'system' ? 'fa-robot' : 'fa-user';
    
    messageDiv.innerHTML = `
        <div class="avatar"><i class="fas ${icon}"></i></div>
        <div class="content">${content}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return `msg-${id}`;
}

function removeMessage(id) {
    const msg = document.getElementById(id);
    if (msg) msg.remove();
}

function showToast(message, type = 'info') {
    const icons = {
        info: 'fa-info-circle',
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle'
    };
    
    toast.innerHTML = `
        <i class="fas ${icons[type]} toast-icon"></i>
        <span>${message}</span>
    `;
    
    toast.className = `toast ${type}`;
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 4000);
}
