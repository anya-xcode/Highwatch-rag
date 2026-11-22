const API_BASE = '/api/v1';
const KEY_STORAGE = 'highwatch_api_key';

// DOM Elements
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const syncBtn = document.getElementById('sync-btn');
const fileInput = document.getElementById('file-input');
const dropZone = document.getElementById('drop-zone');
const uploadHint = document.getElementById('upload-hint');
const uploadQueue = document.getElementById('upload-queue');
const documentList = document.getElementById('document-list');
const docCount = document.getElementById('doc-count');
const toast = document.getElementById('toast');
const systemStatus = document.getElementById('system-status');
const statusIndicator = document.getElementById('status-indicator');
const llmBadge = document.getElementById('llm-badge');

const state = {
    config: null,
    apiKey: readStoredKey(),
    asking: false,
    uploading: false,
    messageSeq: 0,
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    await loadConfig();
    loadDocuments();
    checkStatus();
});

function setupEventListeners() {
    sendBtn.addEventListener('click', handleQuery);
    queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleQuery();
        }
    });

    syncBtn.addEventListener('click', handleSync);

    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    });
    fileInput.addEventListener('change', () => {
        handleFiles(Array.from(fileInput.files));
        fileInput.value = '';
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFiles(Array.from(e.dataTransfer.files));
    });
}

// --- API helper ---

class ApiError extends Error {
    constructor(message, status, detail) {
        super(message);
        this.status = status;
        this.detail = detail;
    }
}

function readStoredKey() {
    try { return localStorage.getItem(KEY_STORAGE) || ''; } catch { return ''; }
}

function storeKey(key) {
    try {
        if (key) localStorage.setItem(KEY_STORAGE, key);
        else localStorage.removeItem(KEY_STORAGE);
    } catch { /* storage unavailable: key lives for this page only */ }
}

function errorMessage(data, status) {
    const detail = data && data.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail.message === 'string') return detail.message;
    if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
    return `Request failed (HTTP ${status})`;
}

async function api(path, options = {}, allowKeyPrompt = true) {
    const headers = new Headers(options.headers || {});
    if (state.apiKey) headers.set('X-API-Key', state.apiKey);

    let response;
    try {
        response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    } catch {
        throw new ApiError('Cannot reach the server. Is it running?', 0);
    }

    const text = await response.text();
    let data = null;
    if (text) {
        try { data = JSON.parse(text); } catch { data = { detail: text }; }
    }

    if (response.status === 401 && allowKeyPrompt) {
        const key = window.prompt('This server requires an API key. Enter it to continue:');
        if (key && key.trim()) {
            state.apiKey = key.trim();
            storeKey(state.apiKey);
            return api(path, options, false);
        }
    }
    if (response.status === 401) {
        state.apiKey = '';
        storeKey('');
    }
    if (!response.ok) {
        throw new ApiError(errorMessage(data, response.status), response.status, data && data.detail);
    }
    return data;
}

// --- Config & status ---

async function loadConfig() {
    try {
        state.config = await api('/config');
        const c = state.config;
        const label = c.llm_provider === 'extractive'
            ? 'Extractive mode (no LLM)'
            : `${capitalize(c.llm_provider)} · ${c.llm_model}`;
        llmBadge.querySelector('span').textContent = label;
        const exts = c.allowed_extensions.map((e) => e.replace('.', '').toUpperCase()).join(', ');
        uploadHint.textContent = `${exts} · max ${c.max_upload_mb} MB`;
        fileInput.accept = c.allowed_extensions.join(',');
        if (!c.drive_configured) {
            syncBtn.title = 'Google Drive is not configured on the server (no credentials.json / token.json).';
        }
    } catch (error) {
        llmBadge.querySelector('span').textContent = 'Offline';
    }
}

async function checkStatus() {
    try {
        const ready = await api('/health/ready');
        const problems = Object.entries(ready.checks)
            .filter(([, c]) => !c.ok)
            .map(([name, c]) => `${name.replace('_', ' ')}: ${c.error || 'not ok'}`);
        setStatus(ready.status, ready.status === 'ready' ? 'System Ready' : `Degraded — ${problems[0]}`);
        statusIndicator.title = problems.join('\n');
    } catch (error) {
        setStatus('not_ready', error.status === 0 ? 'Server unreachable' : 'System not ready');
        statusIndicator.title = error.message;
    }
}

function setStatus(kind, text) {
    statusIndicator.dataset.state = kind;
    systemStatus.textContent = text;
}

// --- Ask ---

async function handleQuery() {
    const query = queryInput.value.trim();
    if (!query || state.asking) return;
    if (query.length < 3) {
        showToast('Please ask a slightly longer question.', 'info');
        return;
    }

    appendMessage('user', escapeHtml(query));
    queryInput.value = '';
    setAsking(true);
    const loadingId = appendMessage('system', '<span class="thinking"><span></span><span></span><span></span></span> Searching your documents…');

    try {
        const data = await api('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, top_k: 5 }),
        });
        removeMessage(loadingId);
        appendMessage('system', renderAnswer(data), data.answer_status);
    } catch (error) {
        removeMessage(loadingId);
        appendMessage('system', `<div class="answer-error"><i class="fas fa-exclamation-triangle"></i> ${escapeHtml(error.message)}</div>`, 'error');
        showToast('Error generating answer', 'error');
    } finally {
        setAsking(false);
        queryInput.focus();
    }
}

function setAsking(busy) {
    state.asking = busy;
    sendBtn.disabled = busy;
    queryInput.disabled = busy;
    sendBtn.innerHTML = busy ? '<i class="fas fa-spinner fa-spin"></i>' : '<i class="fas fa-paper-plane"></i>';
}

function renderAnswer(data) {
    const msgKey = `m${++state.messageSeq}`;
    let html = '';

    if (data.warning) {
        html += `<div class="answer-warning"><i class="fas fa-exclamation-circle"></i> ${escapeHtml(data.warning)}</div>`;
    }
    if (data.answer_status === 'insufficient_context' || data.answer_status === 'no_documents') {
        html += `<div class="answer-notice"><i class="fas fa-info-circle"></i> ${escapeHtml(data.answer)}</div>`;
    } else {
        html += `<div class="answer-text">${formatText(data.answer, msgKey)}</div>`;
    }

    const citations = data.citations || [];
    if (citations.length) {
        html += `<div class="citations"><div class="citations-title">Sources</div>`;
        for (const c of citations) {
            const where = c.page ? (c.page_end && c.page_end !== c.page ? `pp. ${c.page}–${c.page_end}` : `p. ${c.page}`) : '';
            const meta = [where, c.section ? escapeHtml(c.section) : '', `relevance ${c.score.toFixed(2)}`].filter(Boolean).join(' · ');
            const link = c.url && /^https:\/\//.test(c.url)
                ? ` <a href="${escapeAttr(c.url)}" target="_blank" rel="noopener noreferrer" title="Open in Google Drive"><i class="fas fa-external-link-alt"></i></a>`
                : '';
            html += `
                <details class="citation" id="${msgKey}-cite-${c.number}">
                    <summary><span class="cite-num">[${c.number}]</span> <span class="cite-file">${escapeHtml(c.file_name)}</span>${link}<span class="cite-meta">${meta}</span></summary>
                    <blockquote>${escapeHtml(c.snippet)}</blockquote>
                </details>`;
        }
        html += '</div>';
    } else if (data.sources && data.sources.length && data.answer_status !== 'insufficient_context') {
        const tags = data.sources.map((s) => `<span class="source-tag">${escapeHtml(s)}</span>`).join('');
        html += `<div class="sources"><strong>Sources:</strong> ${tags}</div>`;
    }
    return html;
}

/** Minimal, safe formatting: escape first, then bullets, **bold**, `code`, [n] citations. */
function formatText(text, msgKey) {
    const lines = escapeHtml(text || '').split('\n');
    let html = '';
    let inList = false;
    for (const raw of lines) {
        const line = raw.trim();
        const bullet = line.match(/^([-*•]|\d+[.)])\s+(.*)$/);
        if (bullet) {
            if (!inList) { html += '<ul>'; inList = true; }
            html += `<li>${inline(bullet[2], msgKey)}</li>`;
            continue;
        }
        if (inList) { html += '</ul>'; inList = false; }
        html += line ? `<p>${inline(line, msgKey)}</p>` : '';
    }
    if (inList) html += '</ul>';
    return html;
}

function inline(text, msgKey) {
    return text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\[(\d+(?:\s*[,;]\s*\d+)*)\]/g, (_, group) => group
            .split(/[,;]/)
            .map((n) => n.trim())
            .map((n) => `<a class="cite" href="#${msgKey}-cite-${n}" data-cite="${msgKey}-cite-${n}">[${n}]</a>`)
            .join(''));
}

chatMessages.addEventListener('click', (e) => {
    const link = e.target.closest('a.cite');
    if (!link) return;
    e.preventDefault();
    const target = document.getElementById(link.dataset.cite);
    if (target) {
        target.open = true;
        target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        target.classList.add('flash');
        setTimeout(() => target.classList.remove('flash'), 1200);
    }
});

// --- Sync ---

async function handleSync() {
    syncBtn.disabled = true;
    syncBtn.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Syncing...';
    showToast('Starting Google Drive sync...');

    try {
        const data = await api('/sync-drive', { method: 'POST' });
        showToast(data.message, data.errors && data.errors.length ? 'info' : 'success', 7000);
        if (data.errors && data.errors.length) {
            console.warn('Drive sync errors', data.errors);
        }
    } catch (error) {
        showToast(`Sync failed: ${error.message}`, 'error', 9000);
    } finally {
        syncBtn.disabled = false;
        syncBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Sync G-Drive';
        loadDocuments();
        checkStatus();
    }
}

// --- Upload ---

function validateFile(file) {
    const c = state.config;
    if (!c) return null;
    const ext = (file.name.match(/\.[^.]+$/) || [''])[0].toLowerCase();
    if (ext === '.doc') return 'Legacy .doc is not supported — save it as .docx.';
    if (!c.allowed_extensions.includes(ext)) return `Unsupported type ${ext || '(none)'}`;
    if (file.size === 0) return 'File is empty';
    if (file.size > c.max_upload_mb * 1024 * 1024) return `Larger than ${c.max_upload_mb} MB`;
    return null;
}

async function handleFiles(files) {
    if (!files.length) return;
    // Upload one at a time: the server processes each file fully per request.
    const items = files.map((file) => ({ file, row: addQueueRow(file.name) }));
    for (const { file, row } of items) {
        const problem = validateFile(file);
        if (problem) {
            setQueueRow(row, 'error', problem);
            continue;
        }
        setQueueRow(row, 'working', 'Uploading & indexing…');
        const formData = new FormData();
        formData.append('file', file);
        try {
            const data = await api('/upload', { method: 'POST', body: formData });
            setQueueRow(row, 'done', `Indexed · ${data.chunks_created} chunks`);
        } catch (error) {
            setQueueRow(row, error.status === 409 ? 'duplicate' : 'error', error.message);
        }
        loadDocuments();
    }
    checkStatus();
}

function addQueueRow(name) {
    const li = document.createElement('li');
    li.className = 'queue-item';
    li.innerHTML = `<i class="fas fa-clock"></i><div class="queue-text"><span class="queue-name"></span><span class="queue-status">Queued</span></div><button class="queue-dismiss" aria-label="Dismiss">&times;</button>`;
    li.querySelector('.queue-name').textContent = name;
    li.querySelector('.queue-dismiss').addEventListener('click', () => li.remove());
    uploadQueue.prepend(li);
    return li;
}

function setQueueRow(row, kind, text) {
    const icons = { working: 'fa-spinner fa-spin', done: 'fa-check-circle', duplicate: 'fa-clone', error: 'fa-exclamation-circle' };
    row.dataset.state = kind;
    row.querySelector('i').className = `fas ${icons[kind] || 'fa-clock'}`;
    row.querySelector('.queue-status').textContent = text;
    if (kind === 'done') setTimeout(() => row.remove(), 8000);
}

// --- Documents ---

async function loadDocuments() {
    try {
        const data = await api('/documents');
        documentList.innerHTML = '';
        docCount.textContent = data.total_documents;

        if (data.documents.length === 0) {
            documentList.innerHTML = '<li class="empty-docs">No documents indexed yet.</li>';
            return;
        }

        for (const doc of data.documents) {
            documentList.appendChild(renderDocument(doc));
        }
    } catch (error) {
        documentList.innerHTML = '';
        const li = document.createElement('li');
        li.className = 'empty-docs error';
        li.textContent = `Could not load documents: ${error.message}`;
        documentList.appendChild(li);
    }
}

function renderDocument(doc) {
    const li = document.createElement('li');
    li.className = 'doc-item';
    li.dataset.status = doc.status;

    const name = doc.file_name.toLowerCase();
    let icon = 'fa-file-alt';
    if (name.endsWith('.pdf')) icon = 'fa-file-pdf';
    else if (name.endsWith('.docx')) icon = 'fa-file-word';
    if (doc.source === 'gdrive') icon = 'fa-google-drive fab';

    const parts = [];
    if (doc.status === 'indexed') parts.push(`${doc.chunk_count} chunks`);
    if (doc.page_count) parts.push(`${doc.page_count} pages`);
    parts.push(doc.source === 'gdrive' ? 'Drive' : 'Upload');

    li.innerHTML = `
        <i class="${icon.includes('fab') ? icon : 'fas ' + icon}"></i>
        <div class="doc-text">
            <span class="doc-name"></span>
            <span class="doc-meta"><span class="status-chip"></span> <span class="doc-detail"></span></span>
        </div>
        <button class="doc-delete" title="Remove from knowledge base" aria-label="Remove document"><i class="fas fa-trash-alt"></i></button>`;
    li.querySelector('.doc-name').textContent = doc.file_name;
    li.querySelector('.doc-name').title = doc.file_name;
    const chip = li.querySelector('.status-chip');
    chip.textContent = doc.status;
    chip.dataset.status = doc.status;
    if (doc.error) chip.title = doc.error;
    li.querySelector('.doc-detail').textContent = parts.join(' · ');
    li.querySelector('.doc-delete').addEventListener('click', () => deleteDocument(doc));
    return li;
}

async function deleteDocument(doc) {
    const note = doc.source === 'gdrive' ? '\n\nIt will be re-added on the next Drive sync if it is still in Drive.' : '';
    if (!window.confirm(`Remove "${doc.file_name}" from the knowledge base?${note}`)) return;
    try {
        await api(`/documents/${encodeURIComponent(doc.doc_id)}`, { method: 'DELETE' });
        showToast(`Removed ${doc.file_name}`, 'success');
    } catch (error) {
        showToast(`Delete failed: ${error.message}`, 'error');
    }
    loadDocuments();
}

// --- UI Helpers ---

function appendMessage(role, html, variant = '') {
    const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}${variant ? ` status-${variant}` : ''}`;
    messageDiv.id = id;
    const icon = role === 'system' ? 'fa-robot' : 'fa-user';
    messageDiv.innerHTML = `<div class="avatar"><i class="fas ${icon}"></i></div><div class="content">${html}</div>`;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeMessage(id) {
    const msg = document.getElementById(id);
    if (msg) msg.remove();
}

let toastTimer = null;
function showToast(message, type = 'info', duration = 4000) {
    const icons = { info: 'fa-info-circle', success: 'fa-check-circle', error: 'fa-exclamation-circle' };
    toast.innerHTML = `<i class="fas ${icons[type] || icons.info} toast-icon"></i><span></span>`;
    toast.querySelector('span').textContent = message;
    toast.className = `toast ${type}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add('hidden'), duration);
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeAttr(value) {
    return escapeHtml(value);
}

function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}
