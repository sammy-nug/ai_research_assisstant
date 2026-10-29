(() => {
  'use strict';

  const MAX_FILE_BYTES = 25 * 1024 * 1024;
  const MAX_PAGES = 500;
  const CHUNK_SIZE = 1100;
  const STOPWORDS = new Set('a an and are as at be by for from how i in is it much of on or that the their this to was what when where which who why with would did does do'.split(' '));
  const state = { document: null, pages: [], chunks: [], history: [], summaryLength: 'concise', activeTab: 'summary', busy: false };
  const $ = (id) => document.getElementById(id);

  if (window.pdfjsLib) window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  }
  function formatBytes(bytes) {
    return bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }
  function setStatus(message, type = 'info') {
    const node = $('processingStatus');
    node.textContent = message; node.hidden = !message; node.className = `processing-status ${type}`;
  }
  function showToast(message) {
    const node = $('toast'); node.textContent = message; node.hidden = false;
    window.clearTimeout(showToast.timer); showToast.timer = window.setTimeout(() => { node.hidden = true; }, 4600);
  }
  function tokens(text) {
    return String(text).toLowerCase().match(/[a-z0-9']+/g)?.map((token) => token.length > 4 && token.endsWith('s') ? token.slice(0, -1) : token).filter((token) => !STOPWORDS.has(token)) || [];
  }
  function splitSentences(text) {
    return String(text).replace(/\s+/g, ' ').split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter((s) => s.length > 25);
  }
  function buildChunks(pages) {
    const chunks = [];
    pages.forEach((page) => {
      const words = page.text.split(/\s+/).filter(Boolean);
      let start = 0; let index = 0;
      while (start < words.length) {
        const current = []; let chars = 0; let cursor = start;
        while (cursor < words.length && (chars + words[cursor].length + 1 <= CHUNK_SIZE || current.length === 0)) {
          current.push(words[cursor]); chars += words[cursor].length + 1; cursor += 1;
        }
        chunks.push({ id: `p${page.pageNumber}-c${index}`, text: current.join(' '), pageNumber: page.pageNumber, source: state.document?.name || '' });
        if (cursor >= words.length) break;
        start += Math.max(1, cursor - start - 30); index += 1;
      }
    });
    return chunks;
  }
  function retrieve(query) {
    const queryTokens = new Set(tokens(query));
    if (!queryTokens.size) return [];
    const ranked = state.chunks.map((chunk) => {
      const chunkTokens = tokens(chunk.text); const unique = new Set(chunkTokens);
      let score = 0; queryTokens.forEach((term) => { if (unique.has(term)) score += 1; });
      if (chunk.text.toLowerCase().includes(query.toLowerCase())) score += 2;
      return { ...chunk, score };
    }).sort((a, b) => b.score - a.score);
    return ranked.filter((item) => item.score > 0).slice(0, 4);
  }
  function buildSummary(detailed) {
    const sentences = state.pages.flatMap((page) => splitSentences(page.text).map((text) => ({ text, pageNumber: page.pageNumber })));
    if (!sentences.length) return 'No summary could be produced from the extracted text.';
    const frequencies = new Map(); sentences.forEach(({ text }) => tokens(text).forEach((term) => frequencies.set(term, (frequencies.get(term) || 0) + 1)));
    const ranked = sentences.map((sentence, index) => ({ ...sentence, index, score: tokens(sentence.text).reduce((sum, term) => sum + (frequencies.get(term) || 0), 0) })).sort((a, b) => b.score - a.score || a.index - b.index);
    const limit = detailed ? 8 : 4; const selected = ranked.slice(0, Math.min(limit, ranked.length)).sort((a, b) => a.index - b.index);
    return selected.map((item) => item.text).join(' ');
  }
  function answerQuestion(question, results) {
    if (!results.length) return { text: "I don't have enough evidence in the uploaded document to answer that question.", sources: [] };
    const q = new Set(tokens(question));
    const candidateSentences = results.flatMap((chunk) => splitSentences(chunk.text).map((text) => ({ text, chunk })));
    const ranked = candidateSentences.map((item) => ({ ...item, score: tokens(item.text).filter((term) => q.has(term)).length })).sort((a, b) => b.score - a.score);
    const useful = ranked.filter((item) => item.score > 0).slice(0, 2);
    if (!useful.length) return { text: "I don't have enough evidence in the uploaded document to answer that question.", sources: [] };
    const citedIds = new Set(useful.map((item) => item.chunk.id));
    return { text: useful.map((item) => item.text).join(' '), sources: results.filter((result) => citedIds.has(result.id)) };
  }
  async function parsePdf(file) {
    if (!window.pdfjsLib) throw new Error('The PDF reader could not load. Check your connection and refresh the page.');
    const data = new Uint8Array(await file.arrayBuffer());
    let pdf;
    try { pdf = await window.pdfjsLib.getDocument({ data }).promise; } catch (error) {
      if (error?.name === 'PasswordException') throw new Error('This PDF is password-protected. Upload an unlocked copy.');
      throw new Error('This PDF is corrupted, encrypted, or unsupported.');
    }
    if (!pdf.numPages) throw new Error('The PDF has no pages.');
    if (pdf.numPages > MAX_PAGES) throw new Error(`This PDF has ${pdf.numPages} pages. The maximum is ${MAX_PAGES}.`);
    const pages = [];
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      setStatus(`Reading page ${pageNumber} of ${pdf.numPages}…`);
      const page = await pdf.getPage(pageNumber); const content = await page.getTextContent();
      const text = content.items.map((item) => item.str || '').join(' ').replace(/\s+/g, ' ').trim();
      pages.push({ pageNumber, text });
    }
    const characters = pages.reduce((sum, page) => sum + page.text.length, 0);
    if (!characters) throw new Error('No selectable text was found. This looks like a scanned PDF; run OCR first, then upload the OCR-enabled copy.');
    return { pages, characters };
  }
  async function handleFile(file) {
    if (!file) return;
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) return showToast('Please choose a PDF file.');
    if (file.size > MAX_FILE_BYTES) return showToast('This file is larger than 25 MB. Choose a smaller PDF.');
    state.busy = true; setStatus('Preparing your document…'); $('dropzone').classList.add('is-loading');
    try {
      const parsed = await parsePdf(file); state.document = { name: file.name, size: file.size, totalPages: parsed.pages.length, characters: parsed.characters };
      state.pages = parsed.pages; state.chunks = buildChunks(parsed.pages); state.history = []; state.summaryLength = 'concise';
      $('documentCard').hidden = false; $('documentName').textContent = file.name; $('documentStats').textContent = `${parsed.pages.length} pages · ${parsed.characters.toLocaleString()} characters · ${state.chunks.length} chunks`;
      $('retrievalMode').textContent = 'Browser retrieval ready'; $('modelStatus').textContent = 'Browser fallback active'; $('workspaceDocLabel').textContent = file.name.toUpperCase();
      $('emptyState').hidden = true; $('documentWorkspace').hidden = false; setStatus(`Ready — ${parsed.pages.length} pages indexed in this session.`, 'success'); renderDetails(); renderChat(); switchTab('summary');
    } catch (error) { setStatus(error.message, 'error'); showToast(error.message); }
    finally { state.busy = false; $('dropzone').classList.remove('is-loading'); }
  }
  function renderSummary() {
    const result = $('summaryResult');
    if (!state.summary) { result.className = 'result-card muted-result'; result.innerHTML = '<div class="result-placeholder"><span class="placeholder-mark">✦</span><span>Select a length, then generate a grounded overview.</span></div>'; return; }
    result.className = 'result-card'; result.innerHTML = `<div class="summary-copy"><p>${escapeHtml(state.summary)}</p><div class="summary-footnote">Extractive overview · based only on selectable text in this session</div></div>`;
  }
  function renderChat() {
    const history = $('chatHistory');
    if (!state.history.length) { history.innerHTML = '<div class="chat-empty"><span>↳</span><p>Your questions and cited answers will appear here.</p></div>'; return; }
    history.innerHTML = state.history.map((item) => `<div class="chat-item ${item.role}"><p class="chat-role">${item.role === 'user' ? 'You asked' : 'Evidence-based answer'}</p><div class="chat-message">${escapeHtml(item.text)}</div>${item.sources?.length ? `<div class="source-list">${item.sources.map((source) => `<div class="source-card"><strong>${escapeHtml(source.source)} · page ${source.pageNumber}</strong>${escapeHtml(source.text.slice(0, 420))}${source.text.length > 420 ? '…' : ''}</div>`).join('')}</div>` : ''}</div>`).join('');
    history.scrollTop = history.scrollHeight;
  }
  function renderDetails() {
    if (!state.document) return;
    $('detailGrid').innerHTML = [['Pages', state.document.totalPages], ['Characters', state.document.characters.toLocaleString()], ['Chunks', state.chunks.length], ['File size', formatBytes(state.document.size)], ['Retrieval', 'Browser lexical'], ['Persistence', 'Session only']].map(([label, value]) => `<div class="detail-tile"><div class="tile-label">${label}</div><div class="tile-value">${value}</div></div>`).join('');
  }
  function switchTab(tab) {
    state.activeTab = tab; document.querySelectorAll('.tab').forEach((button) => button.classList.toggle('active', button.dataset.tab === tab)); document.querySelectorAll('[data-panel]').forEach((panel) => { panel.hidden = panel.dataset.panel !== tab; });
  }
  function resetSession() {
    state.document = null; state.pages = []; state.chunks = []; state.history = []; state.summary = null; $('fileInput').value = ''; $('documentCard').hidden = true; $('documentWorkspace').hidden = true; $('emptyState').hidden = false; setStatus(''); showToast('New document session started.');
  }

  $('fileInput').addEventListener('change', (event) => handleFile(event.target.files[0]));
  $('dropzone').addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('fileInput').click(); } });
  ['dragenter', 'dragover'].forEach((eventName) => $('dropzone').addEventListener(eventName, (event) => { event.preventDefault(); $('dropzone').classList.add('is-dragging'); }));
  ['dragleave', 'drop'].forEach((eventName) => $('dropzone').addEventListener(eventName, (event) => { event.preventDefault(); $('dropzone').classList.remove('is-dragging'); }));
  $('dropzone').addEventListener('drop', (event) => handleFile(event.dataTransfer.files[0]));
  $('newSessionButton').addEventListener('click', resetSession);
  document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', () => switchTab(button.dataset.tab)));
  document.querySelectorAll('[data-summary-length]').forEach((button) => button.addEventListener('click', () => { state.summaryLength = button.dataset.summaryLength; document.querySelectorAll('[data-summary-length]').forEach((item) => item.classList.toggle('active', item === button)); }));
  $('generateSummary').addEventListener('click', () => { if (!state.document) return; $('generateSummary').disabled = true; $('generateSummary').innerHTML = 'Working <span>…</span>'; window.setTimeout(() => { state.summary = buildSummary(state.summaryLength === 'detailed'); renderSummary(); $('generateSummary').disabled = false; $('generateSummary').innerHTML = 'Regenerate summary <span>→</span>'; }, 180); });
  $('questionForm').addEventListener('submit', (event) => { event.preventDefault(); const input = $('questionInput'); const question = input.value.trim(); if (!question || !state.document || state.busy) return; state.history.push({ role: 'user', text: question }); const results = retrieve(question); const answer = answerQuestion(question, results); state.history.push({ role: 'assistant', text: answer.text, sources: answer.sources }); input.value = ''; renderChat(); });
  $('questionInput').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('questionForm').requestSubmit(); } });
})();
