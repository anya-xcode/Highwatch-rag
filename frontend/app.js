const API_BASE = '/api/v1';
const KEY_STORAGE = 'highwatch_api_key';
const INK_COUNT = 5; // highlighter colours; citation n uses ink ((n - 1) % 5) + 1

const $ = (id) => document.getElementById(id);
const els = {
    thread: $('thread'),
    column: $('column'),
    intro: $('intro'),
    introStatus: $('intro-status'),
    askForm: $('ask-form'),
    queryInput: $('query-input'),
    sendBtn: $('send-btn'),
    sendLabel: $('send-label'),
    askHint: $('ask-hint'),
    keyRow: $('key-row'),
    keyInput: $('key-input'),
    keySave: $('key-save'),
    keyCancel: $('key-cancel'),
    syncBtn: $('sync-btn'),
    syncNote: $('sync-note'),
    chooseBtn: $('choose-btn'),
    fileInput: $('file-input'),
    dropZone: $('drop-zone'),
    uploadHint: $('upload-hint'),
    uploadQueue: $('upload-queue'),
    documentList: $('document-list'),
    docCount: $('doc-count'),
    toast: $('toast'),
    systemStatus: $('system-status'),
    statusIndicator: $('status-indicator'),
    modelValue: $('model-value'),
};

const state = {
    config: null,
    apiKey: readStoredKey(),
    asking: false,
    docs: new Map(),
    totals: { documents: 0, indexed: 0, chunks: 0 },
    citedDocs: new Map(), // doc_id -> citation numbers in the latest answer
    latestKey: '',        // exchange id of the latest answer, for library chips
    exchangeSeq: 0,
};

const icon = (body, cls = '') => `<svg class="i${cls ? ` ${cls}` : ''}" viewBox="0 0 16 16" aria-hidden="true">${body}</svg>`;
const ICONS = {
    file: icon('<path d="M9 1.5H4.5a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V5zM9 1.5V5h3.5"/>'),
    drive: icon('<path d="M5.5 2.5h5l4 7-2.5 4h-8L1.5 9.5z"/><path d="M5.5 2.5l4 7h5M1.5 9.5h8L7 13.5"/>'),
    spinner: icon('<circle cx="8" cy="8" r="5.5" stroke="#d9dbdf"/><path d="M8 2.5A5.5 5.5 0 0 1 13.5 8"/>'),
    alert: icon('<path d="M8 1.8 15 14H1z"/><path d="M8 6v3.6M8 11.6v.4"/>'),
    queued: icon('<circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.5"/>'),
    check: icon('<path d="M3 8.5l3.2 3L13 4.5"/>'),
    copy: icon('<rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M2 11V3a1 1 0 0 1 1-1h8"/>'),
    close: icon('<path d="M4 4l8 8M12 4l-8 8"/>'),
    trash: icon('<path d="M2.5 4h11M6 4V2.5h4V4M4 4l.6 9.5h6.8L12 4"/>'),
    info: icon('<circle cx="8" cy="8" r="6.5"/><path d="M8 7v4.5M8 4.8v.4"/>'),
    noMatch: icon('<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5l3 3M5 7h4"/>'),
    database: icon('<ellipse cx="8" cy="4" rx="5" ry="2"/><path d="M3 4v8c0 1.1 2.2 2 5 2s5-.9 5-2V4M3 8c0 1.1 2.2 2 5 2s5-.9 5-2"/>'),
    chevron: icon('<path d="M4 6l4 4 4-4"/>', 'chev'),
    external: icon('<path d="M9.5 2.5h4v4M13.5 2.5 8 8M11.5 9.5v3a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3"/>'),
};
ICONS.duplicate = ICONS.copy;
ICONS.done = ICONS.check;
ICONS.error = ICONS.alert;
ICONS.working = icon('<path d="M8 2a6 6 0 1 1-6 6"/>');

// ── Startup ─────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    swipeIn(document.querySelector('.example .answer')); // show the motion before anyone asks
    await loadConfig();
    await loadDocuments();
    checkStatus();
});

function setupEventListeners() {
    els.askForm.addEventListener('submit', (e) => {
        e.preventDefault();
        handleQuery();
    });

    els.syncBtn.addEventListener('click', handleSync);
    els.chooseBtn.addEventListener('click', () => els.fileInput.click());
    els.fileInput.addEventListener('change', () => {
        handleFiles(Array.from(els.fileInput.files));
        els.fileInput.value = '';
    });

    els.dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        els.dropZone.classList.add('dragover');
    });
    els.dropZone.addEventListener('dragleave', (e) => {
        if (!els.dropZone.contains(e.relatedTarget)) els.dropZone.classList.remove('dragover');
    });
    els.dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        els.dropZone.classList.remove('dragover');
        handleFiles(Array.from(e.dataTransfer.files));
    });

    // A highlighted claim or its number opens the matching source.
    els.thread.addEventListener('click', (e) => {
        const link = e.target.closest('a.cite, mark.hl[data-cite]');
        if (!link || window.getSelection().toString()) return;
        e.preventDefault();
        openCitation(link.dataset.cite);
    });
    els.thread.addEventListener('mouseover', (e) => lightCitation(e, true));
    els.thread.addEventListener('mouseout', (e) => lightCitation(e, false));
    els.thread.addEventListener('focusin', (e) => lightCitation(e, true));
    els.thread.addEventListener('focusout', (e) => lightCitation(e, false));
}

// ── API helper ──────────────────────────────────────────────

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
    } catch { /* storage unavailable: the key lives for this page only */ }
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
        const key = await requestApiKey();
        if (key) {
            state.apiKey = key;
            storeKey(key);
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

/** Ask for the server's API key inline, above the question box. Concurrent 401s share one request. */
let pendingKeyRequest = null;
function requestApiKey() {
    if (pendingKeyRequest) return pendingKeyRequest;
    pendingKeyRequest = new Promise((resolve) => {
        els.keyRow.hidden = false;
        els.keyInput.value = '';
        els.keyInput.focus();
        const finish = (value) => {
            els.keyRow.hidden = true;
            els.keySave.removeEventListener('click', save);
            els.keyCancel.removeEventListener('click', cancel);
            els.keyInput.removeEventListener('keydown', onKey);
            pendingKeyRequest = null;
            resolve(value);
        };
        const save = () => { if (els.keyInput.value.trim()) finish(els.keyInput.value.trim()); };
        const cancel = () => finish('');
        const onKey = (e) => {
            if (e.key === 'Enter') { e.preventDefault(); save(); }
            if (e.key === 'Escape') { e.preventDefault(); cancel(); }
        };
        els.keySave.addEventListener('click', save);
        els.keyCancel.addEventListener('click', cancel);
        els.keyInput.addEventListener('keydown', onKey);
    });
    return pendingKeyRequest;
}

// ── Config & status ─────────────────────────────────────────

function formatExtensions(exts) {
    const order = ['.pdf', '.docx', '.txt', '.md'];
    const sorted = [...exts].sort((a, b) => {
        const ia = order.indexOf(a), ib = order.indexOf(b);
        return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
    });
    const names = sorted.map((e) => e.replace('.', '').toUpperCase());
    return names.length > 1 ? `${names.slice(0, -1).join(', ')} or ${names[names.length - 1]}` : names.join('');
}

async function loadConfig() {
    try {
        state.config = await api('/config');
        const c = state.config;
        if (c.llm_provider === 'extractive') {
            els.modelValue.innerHTML = '<b>Extractive</b><span class="model-id"> · no AI model</span>';
            els.modelValue.title = 'No language model: answers quote the most relevant passages.';
        } else {
            els.modelValue.innerHTML = `<b>${escapeHtml(capitalize(c.llm_provider))}</b><span class="model-id"> · ${escapeHtml(c.llm_model || '')}</span>`;
            els.modelValue.title = `Answers are written by ${c.llm_model} using only your documents.`;
        }
        els.uploadHint.innerHTML = `<b>Drop ${escapeHtml(formatExtensions(c.allowed_extensions))}</b><span class="limit">Up to ${c.max_upload_mb} MB per file</span>`;
        els.fileInput.accept = c.allowed_extensions.join(',');
        if (!c.drive_configured) {
            els.syncBtn.disabled = true;
            els.syncNote.textContent = 'Google Drive isn’t connected on this server. See “Google Drive setup” in the README.';
            els.syncNote.hidden = false;
        }
    } catch (error) {
        els.modelValue.textContent = 'Model unavailable';
        els.modelValue.title = error.message;
    }
}

async function checkStatus() {
    try {
        const ready = await api('/health/ready');
        const problems = Object.entries(ready.checks)
            .filter(([, c]) => !c.ok)
            .map(([name, c]) => `${name.replace(/_/g, ' ')}: ${c.error || 'not ok'}`);
        const label = { ready: 'Ready', degraded: 'Degraded', not_ready: 'Not ready' }[ready.status] || ready.status;
        setStatus(ready.status, label, problems.join('\n') || 'All checks passed');
    } catch (error) {
        setStatus('not_ready', error.status === 0 ? 'Offline' : 'Not ready', error.message);
    }
}

function setStatus(kind, text, detail) {
    els.statusIndicator.dataset.state = kind;
    els.systemStatus.textContent = text;
    els.statusIndicator.title = detail || '';
}

// ── Ask ─────────────────────────────────────────────────────

async function handleQuery() {
    const query = els.queryInput.value.trim();
    if (!query || state.asking) return;
    if (query.length < 3) {
        showToast('Ask a slightly longer question.', 'info');
        return;
    }

    const key = `ex${++state.exchangeSeq}`;
    const section = document.createElement('section');
    section.className = 'ex';
    section.id = key;
    section.setAttribute('aria-label', 'Question and answer');
    section.innerHTML = `<h2 class="q"></h2>
        <p class="pending" role="status"><span class="bar" aria-hidden="true"></span><span></span></p>`;
    section.querySelector('.q').textContent = query;
    section.querySelector('.pending span:last-child').textContent = state.totals.chunks
        ? `Searching ${plural(state.totals.chunks, 'chunk')}…`
        : 'Searching your documents…';

    els.intro.hidden = true;
    els.column.querySelectorAll('.ex:not(.past)').forEach(foldExchange);
    els.column.appendChild(section);
    scrollToExchange(section);

    els.queryInput.value = '';
    setAsking(true);
    const searched = { ...state.totals };

    try {
        const data = await api('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, top_k: 5 }),
        });
        renderAnswer(section, key, data, searched);
    } catch (error) {
        section.querySelector('.pending')?.remove();
        section.insertAdjacentHTML('beforeend', `<p class="notice error" role="alert">${ICONS.alert}<span>${escapeHtml(error.message)}</span></p>`);
    } finally {
        setAsking(false);
        els.queryInput.focus();
    }
}

function setAsking(busy) {
    state.asking = busy;
    els.sendBtn.disabled = busy;
    els.queryInput.disabled = busy;
    els.sendLabel.textContent = busy ? 'Asking…' : 'Ask';
    els.thread.setAttribute('aria-busy', String(busy));
}

/** Fold an earlier exchange to its question and first lines; it can be reopened. */
function foldExchange(section) {
    section.classList.add('past');
    if (!section.querySelector('.answer, .sources') || section.querySelector('.past-toggle')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'link-btn past-toggle';
    btn.textContent = 'Show full answer';
    btn.setAttribute('aria-expanded', 'false');
    btn.addEventListener('click', () => {
        const open = section.classList.toggle('expanded');
        btn.textContent = open ? 'Fold answer' : 'Show full answer';
        btn.setAttribute('aria-expanded', String(open));
    });
    const budget = section.querySelector('.budget');
    (budget || section.lastElementChild).insertAdjacentElement('afterend', btn);
}

/** Bring the new question into view with the previous exchange's divider at the top edge. */
function scrollToExchange(section) {
    const prev = section.previousElementSibling;
    const anchor = prev && prev.classList.contains('ex') ? prev : null;
    const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
    if (getComputedStyle(els.thread).overflowY === 'visible') {
        (anchor || section).scrollIntoView({ behavior, block: 'start' });
    } else {
        els.thread.scrollTo({ top: anchor ? anchor.offsetTop : 0, behavior });
    }
}

function renderAnswer(section, key, data, searched) {
    section.querySelector('.pending')?.remove();
    const citations = data.citations || [];
    const numbers = new Set(citations.map((c) => c.number));
    const snippets = new Map(citations.map((c) => [c.number, c.snippet || '']));
    const refused = data.answer_status === 'insufficient_context' || data.answer_status === 'no_documents';
    const claims = new Map();
    state.latestKey = key;
    let html = '';

    if (data.warning) {
        html += `<p class="notice" role="note">${ICONS.alert}<span>${escapeHtml(data.warning)}</span></p>`;
    }

    if (refused) {
        html += `<p class="refusal">${ICONS.noMatch}<span>${escapeHtml(data.answer)}</span></p>`;
    } else {
        html += `<div class="answer">${formatAnswer(data.answer, key, numbers, claims, snippets)}</div>`;
    }

    if (data.answer_status !== 'no_documents' && searched.chunks) {
        const scope = `Searched ${plural(searched.indexed, 'document')} · ${plural(searched.chunks, 'chunk')}`;
        const note = refused ? ' · no passage was relevant enough'
            : data.answer_status === 'extractive' ? ' · quoted directly, no AI model' : '';
        html += `<p class="budget">${ICONS.database}<span>${scope}${note}</span></p>`;
    }

    if (citations.length) {
        html += renderSources(key, citations, claims, data.answer_status === 'answered');
    } else if (!refused && data.sources && data.sources.length) {
        html += `<p class="src-plain">Sources: ${data.sources.map(escapeHtml).join(', ')}</p>`;
    }

    section.insertAdjacentHTML('beforeend', html);
    swipeIn(section.querySelector('.answer'));

    state.citedDocs = new Map();
    for (const c of citations) {
        if (!state.citedDocs.has(c.doc_id)) state.citedDocs.set(c.doc_id, []);
        state.citedDocs.get(c.doc_id).push(c.number);
    }
    renderDocumentList();
}

/** The one authored motion: highlights swipe in, left to right, as an answer lands. */
function swipeIn(answer) {
    if (!answer) return;
    const marks = answer.querySelectorAll('mark.hl');
    if (!marks.length) return;
    marks.forEach((m, i) => { m.style.animationDelay = `${120 + i * 140}ms`; });
    answer.classList.add('swipe');
    setTimeout(() => answer.classList.remove('swipe'), 800 + marks.length * 140);
}

// ── Highlighting ────────────────────────────────────────────

const ink = (n) => ((Number(n) - 1) % INK_COUNT) + 1;
// onInk: the chip sits on a highlight of its own colour, so it takes a darker tint instead.
const citeChip = (key, n, onInk = false) => `<a class="cite" href="#${key}-c${n}" data-cite="${key}-c${n}" aria-label="Source ${n}"><span class="chip${onInk ? ' on-ink' : ''}" data-c="${ink(n)}">${n}</span></a>`;
const CITE_GROUP = /\s*\[(\d+(?:\s*[,;]\s*\d+)*)\]/g;

/**
 * Answer text → HTML. Each claim (the sentence fragment that ends in [n]) is wrapped in a
 * highlighter mark in its source's ink, with the source number as a chip. Escapes first.
 */
function formatAnswer(text, key, numbers, claims, snippets) {
    const lines = (text || '').split('\n');
    let html = '';
    let inList = false;
    for (const raw of lines) {
        const line = raw.trim();
        // Extractive answers: "[n] passage" paragraphs.
        const passage = line.match(/^\[(\d+)\]\s+(.*)$/);
        if (passage && numbers.has(Number(passage[1]))) {
            if (inList) { html += '</ul>'; inList = false; }
            claims.set(Number(passage[1]), passage[2]);
            html += `<p class="passage">${citeChip(key, passage[1])}<span>${inlineFormat(escapeHtml(passage[2]))}</span></p>`;
            continue;
        }
        const bullet = line.match(/^([-*•]|\d+[.)])\s+(.*)$/);
        if (bullet) {
            if (!inList) { html += '<ul>'; inList = true; }
            html += `<li>${highlightClaims(bullet[2], key, numbers, claims, snippets)}</li>`;
            continue;
        }
        if (inList) { html += '</ul>'; inList = false; }
        if (line) html += `<p>${highlightClaims(line, key, numbers, claims, snippets)}</p>`;
    }
    if (inList) html += '</ul>';
    return html;
}

/**
 * Mark each claim from the first word it shares with its source excerpt (a 3+ word run, the
 * same words lit in the excerpt) through to its citation; lead-in words stay plain. Without
 * such a run the whole claim (the sentence fragment before [n]) is marked instead.
 */
function highlightClaims(raw, key, numbers, claims, snippets) {
    const fmt = (s) => inlineFormat(escapeHtml(s));
    const chips = (nums, onInkFirst) => nums.map((n, i) => citeChip(key, n, onInkFirst && i === 0)).join('');
    let out = '';
    let pos = 0;
    for (const match of raw.matchAll(CITE_GROUP)) {
        const segment = raw.slice(pos, match.index);
        pos = match.index + match[0].length;
        const nums = match[1].split(/[,;]/).map((n) => Number(n.trim())).filter((n) => numbers.has(n));
        if (!nums.length) {
            out += fmt(segment + match[0]);
            continue;
        }
        // The claim is the last sentence fragment before the citation, without leading punctuation.
        const split = segment.match(/^([\s\S]*[.!?:;]\s+|)([\s\S]*)$/);
        const lead = split[1] + (split[2].match(/^[\s,;:.]*/) || [''])[0];
        const claim = segment.slice(lead.length);
        nums.forEach((n) => { if (!claims.has(n)) claims.set(n, claim); });
        if (!claim.trim()) {
            out += fmt(segment) + chips(nums, false);
            continue;
        }
        const open = `<mark class="hl" data-c="${ink(nums[0])}" data-cite="${key}-c${nums[0]}">`;
        const run = sharedRun(claim, snippets.get(nums[0]) || '');
        if (!run) {
            out += fmt(lead) + open + fmt(claim) + chips(nums, true) + '</mark>';
            continue;
        }
        // Ink starts where the shared phrase starts and runs to the citation, so the
        // number always sits inside its own colour.
        out += fmt(lead + claim.slice(0, run.aStart)) + open + fmt(claim.slice(run.aStart)) + chips(nums, true) + '</mark>';
    }
    return out + fmt(raw.slice(pos));
}

/** Longest run of words two texts share (case-insensitive), as character ranges in each; null below 3 words. */
function sharedRun(a, b) {
    const words = (s) => [...s.matchAll(/[\p{L}\p{N}]+(?:['’]\p{L}+)?/gu)].map((m) => ({ w: m[0].toLowerCase().replace('’', "'"), i: m.index, e: m.index + m[0].length }));
    const wa = words(a), wb = words(b);
    let best = 0, endA = -1, endB = -1;
    let prev = new Array(wb.length + 1).fill(0);
    for (let i = 1; i <= wa.length; i++) {
        const cur = new Array(wb.length + 1).fill(0);
        for (let j = 1; j <= wb.length; j++) {
            if (wa[i - 1].w === wb[j - 1].w) {
                cur[j] = prev[j - 1] + 1;
                if (cur[j] > best) { best = cur[j]; endA = i - 1; endB = j - 1; }
            }
        }
        prev = cur;
    }
    if (best < 3) return null;
    return {
        aStart: wa[endA - best + 1].i, aEnd: wa[endA].e,
        bStart: wb[endB - best + 1].i, bEnd: wb[endB].e,
    };
}

function inlineFormat(escaped) {
    return escaped
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
}

/** Highlight, in the excerpt, the phrase it shares with the claim, in the claim's ink. */
function highlightExcerpt(snippet, claim, n) {
    const run = claim ? sharedRun(claim, snippet) : null;
    if (!run) return escapeHtml(snippet);
    const { bStart: start, bEnd: end } = run;
    return `${escapeHtml(snippet.slice(0, start))}<mark class="hl" data-c="${ink(n)}">${escapeHtml(snippet.slice(start, end))}</mark>${escapeHtml(snippet.slice(end))}`;
}

function renderSources(key, citations, claims, openFirst) {
    const docs = new Set(citations.map((c) => c.doc_id)).size;
    let html = `<div class="sources-head"><h3>Sources</h3><span class="count">${citations.length}${docs > 1 ? ` · ${plural(docs, 'document')}` : ''}</span></div><ol class="sources">`;
    citations.forEach((c, i) => {
        const where = c.page
            ? (c.page_end && c.page_end !== c.page ? `pp. ${c.page}–${c.page_end}` : `p. ${c.page}`)
            : `chunk ${c.chunk_index + 1}`;
        const label = [where, c.section].filter(Boolean).map(escapeHtml).join(' · ');
        const drive = c.url && /^https:\/\//.test(c.url)
            ? `<div class="src-foot"><a class="open-doc" href="${escapeAttr(c.url)}" target="_blank" rel="noopener noreferrer">${ICONS.external}Open in Google Drive</a></div>`
            : '';
        const open = openFirst && i === 0 ? ' open' : '';
        html += `<li><details class="src" id="${key}-c${c.number}" data-cite="${key}-c${c.number}"${open}>
            <summary><span class="chip" data-c="${ink(c.number)}">${c.number}</span><span class="src-title"><span class="file">${escapeHtml(c.file_name)}</span><span class="where">${label}</span></span><span class="rel">relevance<b>${c.score.toFixed(2)}</b></span>${ICONS.chevron}</summary>
            <p class="excerpt">${highlightExcerpt(c.snippet || '', claims.get(c.number), c.number)}</p>
            ${drive}
        </details></li>`;
    });
    return html + '</ol>';
}

function openCitation(id) {
    const details = document.getElementById(id);
    if (!details) return;
    const section = details.closest('.ex');
    if (section && section.classList.contains('past') && !section.classList.contains('expanded')) {
        section.querySelector('.past-toggle')?.click();
    }
    details.open = true;
    details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    details.classList.add('flash');
    requestAnimationFrame(() => requestAnimationFrame(() => details.classList.remove('flash')));
}

/** Light every place a citation appears: the claim, its number, its source row and its library chip. */
function lightCitation(e, on) {
    const el = e.target.closest('[data-cite]');
    if (!el || !els.thread.contains(el)) return;
    document.querySelectorAll(`[data-cite="${CSS.escape(el.dataset.cite)}"]`).forEach((node) => node.classList.toggle('lit', on));
}

// ── Google Drive sync ───────────────────────────────────────

async function handleSync() {
    const label = els.syncBtn.querySelector('span');
    els.syncBtn.disabled = true;
    els.syncBtn.classList.add('busy');
    label.textContent = 'Syncing…';

    try {
        const data = await api('/sync-drive', { method: 'POST' });
        const failed = data.errors && data.errors.length;
        showToast(data.message, failed ? 'info' : 'success', 7000);
        if (failed) console.warn('Drive sync errors', data.errors);
    } catch (error) {
        showToast(`Sync failed: ${error.message}`, 'error', 9000);
    } finally {
        els.syncBtn.disabled = false;
        els.syncBtn.classList.remove('busy');
        label.textContent = 'Sync Google Drive';
        await loadDocuments();
        checkStatus();
    }
}

// ── Upload ──────────────────────────────────────────────────

function validateFile(file) {
    const c = state.config;
    if (!c) return null;
    const ext = (file.name.match(/\.[^.]+$/) || [''])[0].toLowerCase();
    if (ext === '.doc') return 'Legacy .doc isn’t supported. Save it as .docx and upload again.';
    if (!c.allowed_extensions.includes(ext)) return `${ext || 'Files without an extension'} isn’t supported. Use ${formatExtensions(c.allowed_extensions)}.`;
    if (file.size === 0) return 'The file is empty.';
    if (file.size > c.max_upload_mb * 1024 * 1024) return `Larger than the ${c.max_upload_mb} MB limit.`;
    return null;
}

async function handleFiles(files) {
    if (!files.length) return;
    // One at a time: the server indexes each file fully within its request.
    const items = files.map((file) => ({ file, row: addQueueRow(file.name) }));
    for (const { file, row } of items) {
        const problem = validateFile(file);
        if (problem) {
            setQueueRow(row, 'error', problem);
            continue;
        }
        setQueueRow(row, 'working', 'Uploading and indexing…');
        const formData = new FormData();
        formData.append('file', file);
        try {
            const data = await api('/upload', { method: 'POST', body: formData });
            setQueueRow(row, 'done', `Indexed · ${plural(data.chunks_created, 'chunk')}`);
        } catch (error) {
            setQueueRow(row, error.status === 409 ? 'duplicate' : 'error', error.message);
        }
        await loadDocuments();
    }
    checkStatus();
}

function addQueueRow(name) {
    const li = document.createElement('li');
    li.className = 'qi';
    li.dataset.state = 'queued';
    li.innerHTML = `${ICONS.queued}<div class="qi-text"><span class="qi-name"></span><span class="qi-status">Waiting…</span></div>
        <button type="button" class="qi-dismiss">${ICONS.close}</button>`;
    li.querySelector('.qi-name').textContent = name;
    li.querySelector('.qi-name').title = name;
    const dismiss = li.querySelector('.qi-dismiss');
    dismiss.setAttribute('aria-label', `Dismiss ${name}`);
    dismiss.addEventListener('click', () => li.remove());
    els.uploadQueue.prepend(li);
    return li;
}

function setQueueRow(row, kind, text) {
    row.dataset.state = kind;
    row.querySelector('svg').outerHTML = ICONS[kind] || ICONS.queued;
    row.querySelector('.qi-status').textContent = text;
    if (kind === 'done') setTimeout(() => row.remove(), 8000);
}

// ── Documents ───────────────────────────────────────────────

async function loadDocuments() {
    try {
        const data = await api('/documents');
        state.docs = new Map(data.documents.map((d) => [d.doc_id, d]));
        const indexed = data.documents.filter((d) => d.status === 'indexed').length;
        state.totals = { documents: data.total_documents, indexed, chunks: data.total_chunks };
        renderDocumentList();
    } catch (error) {
        els.documentList.innerHTML = '';
        const li = document.createElement('li');
        li.className = 'docs-empty error';
        li.textContent = `Couldn’t load documents: ${error.message}`;
        els.documentList.appendChild(li);
    }
    updateSummaries();
}

function updateSummaries() {
    const t = state.totals;
    els.docCount.textContent = t.documents ? plural(t.documents, 'document') : '';
    els.askHint.innerHTML = t.indexed
        ? `${ICONS.database}<span>Searches ${plural(t.indexed, 'document')} · ${plural(t.chunks, 'chunk')}</span>`
        : `${ICONS.info}<span>Add a document to the library first.</span>`;
    // The composer hint carries the counts; the intro only speaks up when the library is empty.
    els.introStatus.hidden = Boolean(t.indexed);
    if (!t.indexed) {
        els.introStatus.innerHTML = `${ICONS.info}<span>No documents yet. <a href="#library">Add one to the library</a>, then ask.</span>`;
    }
}

function renderDocumentList() {
    els.documentList.innerHTML = '';
    if (!state.docs.size) {
        els.documentList.innerHTML = '<li class="docs-empty">No documents yet. Drop a file above or sync Google Drive.</li>';
        return;
    }
    for (const doc of state.docs.values()) els.documentList.appendChild(renderDocument(doc));
}

function renderDocument(doc) {
    const li = document.createElement('li');
    li.className = `doc ${doc.status}`;
    li.dataset.docId = doc.doc_id;

    const parts = [];
    if (doc.status === 'processing') parts.push('<b>Processing</b>');
    else if (doc.status === 'failed') parts.push('<b class="st-failed">Failed</b>');
    else parts.push('Indexed');
    if (doc.page_count) parts.push(plural(doc.page_count, 'page'));
    if (doc.status === 'indexed') parts.push(plural(doc.chunk_count, 'chunk'));
    const drive = doc.source === 'gdrive';
    if (drive && doc.url && /^https:\/\//.test(doc.url)) {
        parts.push(`<a href="${escapeAttr(doc.url)}" target="_blank" rel="noopener noreferrer">Google Drive</a>`);
    } else {
        parts.push(drive ? 'Google Drive' : 'Upload');
    }

    const cited = state.citedDocs.get(doc.doc_id) || [];
    const chips = cited.map((n) => `<span class="chip" data-c="${ink(n)}" data-cite="${state.latestKey}-c${n}">${n}</span>`).join('');
    const lead = doc.status === 'processing' ? ICONS.spinner : doc.status === 'failed' ? ICONS.alert : ICONS.file;

    li.innerHTML = `${lead}
        <span class="doc-name"></span>
        <span class="doc-side"${cited.length ? ` title="Cited as ${cited.join(', ')} in the latest answer"` : ''}>${chips}</span>
        <span class="doc-meta">${parts.join(' · ')}</span>
        <button type="button" class="doc-delete">${ICONS.trash}</button>
        ${doc.error ? '<span class="doc-error"></span>' : ''}`;
    li.querySelector('.doc-name').textContent = doc.file_name;
    li.querySelector('.doc-name').title = doc.file_name;
    if (doc.error) li.querySelector('.doc-error').textContent = doc.error;
    const del = li.querySelector('.doc-delete');
    del.setAttribute('aria-label', `Remove ${doc.file_name}`);
    del.title = 'Remove from the library';
    del.addEventListener('click', () => confirmRemoval(li, doc));
    return li;
}

/** Inline confirmation in the document's own row: Remove / Keep. */
function confirmRemoval(li, doc) {
    if (li.querySelector('.doc-confirm')) return;
    li.classList.add('confirming');
    const box = document.createElement('div');
    box.className = 'doc-confirm';
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', `Remove ${doc.file_name}?`);
    const note = doc.source === 'gdrive' ? ' It returns on the next Drive sync if it’s still in the folder.' : '';
    box.innerHTML = '<span></span><button type="button" class="btn danger">Remove</button><button type="button" class="btn">Keep</button>';
    box.querySelector('span').textContent = `Remove from the library?${note}`;
    const [remove, keep] = box.querySelectorAll('button');
    const close = () => {
        box.remove();
        li.classList.remove('confirming');
        li.querySelector('.doc-delete').focus();
    };
    keep.addEventListener('click', close);
    box.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
    remove.addEventListener('click', () => {
        remove.disabled = true;
        keep.disabled = true;
        remove.textContent = 'Removing…';
        deleteDocument(doc);
    });
    li.appendChild(box);
    remove.focus();
}

async function deleteDocument(doc) {
    try {
        await api(`/documents/${encodeURIComponent(doc.doc_id)}`, { method: 'DELETE' });
        state.citedDocs.delete(doc.doc_id);
        showToast(`Removed ${doc.file_name}`, 'success');
    } catch (error) {
        showToast(`Couldn’t remove it: ${error.message}`, 'error');
    }
    await loadDocuments();
}

// ── Helpers ─────────────────────────────────────────────────

let toastTimer = null;
function showToast(message, type = 'info', duration = 4500) {
    const glyph = { info: ICONS.info, success: ICONS.check, error: ICONS.alert }[type] || ICONS.info;
    els.toast.innerHTML = `${glyph}<span></span>`;
    els.toast.querySelector('span').textContent = message;
    els.toast.className = `toast ${type}`;
    els.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { els.toast.hidden = true; }, duration);
}

function plural(n, word) {
    return `${n} ${word}${n === 1 ? '' : 's'}`;
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
