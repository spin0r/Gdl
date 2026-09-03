/**
 * Gallery-DL Web Extractor - Interactive Frontend Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // State
  let currentItems = [];
  let filteredItems = [];
  let currentMode = 'single'; // 'single' | 'batch'
  let currentFilter = 'all'; // 'all' | 'image' | 'video' | 'audio'
  let currentLayout = 'grid'; // 'grid' | 'list'
  let timerInterval = null;
  let startTime = 0;

  // DOM Elements
  const singleUrlTab = document.getElementById('singleUrlTab');
  const batchUrlTab = document.getElementById('batchUrlTab');
  const singleInputContainer = document.getElementById('singleInputContainer');
  const batchInputContainer = document.getElementById('batchInputContainer');
  const urlInput = document.getElementById('urlInput');
  const batchInput = document.getElementById('batchInput');
  const extractForm = document.getElementById('extractForm');
  const submitBtn = document.getElementById('submitBtn');
  const btnText = submitBtn.querySelector('.btn-text');
  const btnLoader = submitBtn.querySelector('.btn-loader');
  const pasteBtn = document.getElementById('pasteBtn');
  const batchPasteBtn = document.getElementById('batchPasteBtn');
  const clearBtn = document.getElementById('clearBtn');
  
  const statusIndicator = document.getElementById('statusIndicator');
  const statusText = document.getElementById('statusText');
  const statusTimer = document.getElementById('statusTimer');
  
  const errorBanner = document.getElementById('errorBanner');
  const errorMessage = document.getElementById('errorMessage');
  const dismissErrorBtn = document.getElementById('dismissErrorBtn');
  
  const resultsSection = document.getElementById('resultsSection');
  const totalCountEl = document.getElementById('totalCount');
  const sourceUrlTag = document.getElementById('sourceUrlTag');
  const mediaGrid = document.getElementById('mediaGrid');
  const mediaList = document.getElementById('mediaList');
  const noFilterResults = document.getElementById('noFilterResults');
  
  const filterInput = document.getElementById('filterInput');
  const filterPills = document.querySelectorAll('.filter-pill');
  const filterAllCount = document.getElementById('filterAllCount');
  const filterImgCount = document.getElementById('filterImgCount');
  const filterVidCount = document.getElementById('filterVidCount');
  const filterAudCount = document.getElementById('filterAudCount');
  
  const gridViewBtn = document.getElementById('gridViewBtn');
  const listViewBtn = document.getElementById('listViewBtn');
  
  const copyAllBtn = document.getElementById('copyAllBtn');
  const exportDropdownBtn = document.getElementById('exportDropdownBtn');
  const exportMenu = document.getElementById('exportMenu');
  const exportTxtBtn = document.getElementById('exportTxtBtn');
  const exportJsonBtn = document.getElementById('exportJsonBtn');
  const exportM3uBtn = document.getElementById('exportM3uBtn');
  const telegraphBtn = document.getElementById('telegraphBtn');
  const openAllBtn = document.getElementById('openAllBtn');
  
  // History Drawer
  const historyToggleBtn = document.getElementById('historyToggleBtn');
  const historyDrawer = document.getElementById('historyDrawer');
  const drawerOverlay = document.getElementById('drawerOverlay');
  const closeHistoryBtn = document.getElementById('closeHistoryBtn');
  const clearHistoryBtn = document.getElementById('clearHistoryBtn');
  const historyList = document.getElementById('historyList');
  const historyBadge = document.getElementById('historyBadge');
  
  // Modal
  const mediaModal = document.getElementById('mediaModal');
  const modalBackdrop = document.getElementById('modalBackdrop');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const modalMediaContainer = document.getElementById('modalMediaContainer');
  const modalMediaInfo = document.getElementById('modalMediaInfo');
  const modalOpenBtn = document.getElementById('modalOpenBtn');
  const modalCopyBtn = document.getElementById('modalCopyBtn');
  
  // Theme Toggle
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');

  // Initialize Lucide Icons
  lucide.createIcons();

  // Load Saved History on Startup
  updateHistoryUI();

  // Mode Switch Tabs
  singleUrlTab.addEventListener('click', () => setMode('single'));
  batchUrlTab.addEventListener('click', () => setMode('batch'));

  function setMode(mode) {
    currentMode = mode;
    if (mode === 'single') {
      singleUrlTab.classList.add('active');
      batchUrlTab.classList.remove('active');
      singleInputContainer.style.display = 'block';
      batchInputContainer.style.display = 'none';
      urlInput.setAttribute('required', 'true');
      batchInput.removeAttribute('required');
      urlInput.focus();
    } else {
      batchUrlTab.classList.add('active');
      singleUrlTab.classList.remove('active');
      batchInputContainer.style.display = 'block';
      singleInputContainer.style.display = 'none';
      urlInput.removeAttribute('required');
      batchInput.setAttribute('required', 'true');
      batchInput.focus();
    }
  }

  // Quick Sample Chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const sampleUrl = chip.dataset.sample;
      setMode('single');
      urlInput.value = sampleUrl;
      clearBtn.style.display = 'flex';
      extractForm.dispatchEvent(new Event('submit'));
    });
  });

  // Input Clear / Paste Handlers
  urlInput.addEventListener('input', () => {
    clearBtn.style.display = urlInput.value ? 'flex' : 'none';
  });

  clearBtn.addEventListener('click', () => {
    urlInput.value = '';
    clearBtn.style.display = 'none';
    urlInput.focus();
  });

  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        clearBtn.style.display = 'flex';
        showToast('Link pasted from clipboard', 'success');
      }
    } catch (e) {
      showToast('Clipboard access denied. Please paste manually.', 'error');
    }
  });

  batchPasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        batchInput.value = text.trim();
        showToast('Pasted links into batch input', 'success');
      }
    } catch (e) {
      showToast('Clipboard access denied. Please paste manually.', 'error');
    }
  });

  // Dismiss Error
  dismissErrorBtn.addEventListener('click', () => {
    errorBanner.style.display = 'none';
  });

  // Form Submit / Extraction Request
  extractForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorBanner.style.display = 'none';

    let payload = {};
    let displaySource = '';

    if (currentMode === 'single') {
      const singleVal = urlInput.value.trim();
      if (!singleVal) return;
      payload = { url: singleVal };
      displaySource = singleVal;
    } else {
      const batchVal = batchInput.value.trim();
      const lines = batchVal.split('\n').map(l => l.trim()).filter(Boolean);
      if (lines.length === 0) return;
      payload = { urls: lines };
      displaySource = `${lines.length} Batch URLs`;
    }

    startLoadingState();

    try {
      const res = await fetch('/api/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      stopLoadingState();

      if (!res.ok || !data.success) {
        const msg = data.detail || (data.errors ? data.errors.join('\n') : 'Failed to extract links');
        showError(msg);
        return;
      }

      if (data.items.length === 0) {
        showError('No media links found at the specified URL.');
        return;
      }

      // Success
      currentItems = data.items;
      sourceUrlTag.textContent = displaySource;
      sourceUrlTag.title = displaySource;
      
      saveToHistory(displaySource, currentItems);
      applyFilterAndRender();
      resultsSection.style.display = 'block';
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

      showToast(`Successfully extracted ${currentItems.length} media links!`, 'success');
    } catch (err) {
      stopLoadingState();
      showError(err.message || 'Network error occurred while connecting to server.');
    }
  });

  function startLoadingState() {
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoader.style.display = 'flex';
    statusIndicator.style.display = 'flex';
    
    startTime = Date.now();
    statusText.textContent = 'Invoking gallery-dl engine to inspect media...';
    
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      statusTimer.textContent = `${elapsed}s`;
    }, 100);
  }

  function stopLoadingState() {
    submitBtn.disabled = false;
    btnText.style.display = 'inline-flex';
    btnLoader.style.display = 'none';
    statusIndicator.style.display = 'none';
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function showError(msg) {
    errorMessage.textContent = msg;
    errorBanner.style.display = 'flex';
    errorBanner.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  // Filtering & Search
  filterInput.addEventListener('input', () => {
    applyFilterAndRender();
  });

  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentFilter = pill.dataset.filter;
      applyFilterAndRender();
    });
  });

  function applyFilterAndRender() {
    const query = filterInput.value.toLowerCase().trim();

    // Calculate category counts
    const imgCount = currentItems.filter(i => i.type === 'image').length;
    const vidCount = currentItems.filter(i => i.type === 'video').length;
    const audCount = currentItems.filter(i => i.type === 'audio').length;

    filterAllCount.textContent = currentItems.length;
    filterImgCount.textContent = imgCount;
    filterVidCount.textContent = vidCount;
    filterAudCount.textContent = audCount;
    totalCountEl.textContent = currentItems.length;

    // Apply Filter & Search
    filteredItems = currentItems.filter(item => {
      const matchesType = (currentFilter === 'all') || (item.type === currentFilter);
      const matchesSearch = !query || 
        item.url.toLowerCase().includes(query) || 
        item.filename.toLowerCase().includes(query);
      return matchesType && matchesSearch;
    });

    renderMediaItems();
  }

  // Render Grid and List views
  function renderMediaItems() {
    mediaGrid.innerHTML = '';
    mediaList.innerHTML = '';

    if (filteredItems.length === 0) {
      noFilterResults.style.display = 'flex';
      mediaGrid.style.display = 'none';
      mediaList.style.display = 'none';
      return;
    }

    noFilterResults.style.display = 'none';
    if (currentLayout === 'grid') {
      mediaGrid.style.display = 'grid';
      mediaList.style.display = 'none';
    } else {
      mediaGrid.style.display = 'none';
      mediaList.style.display = 'flex';
    }

    filteredItems.forEach(item => {
      // 1. Grid Card
      const card = createGridCard(item);
      mediaGrid.appendChild(card);

      // 2. List Item
      const row = createListRow(item);
      mediaList.appendChild(row);
    });

    lucide.createIcons();
  }

  function createGridCard(item) {
    const card = document.createElement('div');
    card.className = 'media-card';

    let previewHtml = '';
    if (item.type === 'image') {
      const previewSrc = item.thumbnail_url || item.url;
      previewHtml = `
        <div class="card-preview-area" data-zoom="true">
          <img src="${escapeHtml(previewSrc)}" alt="${escapeHtml(item.filename)}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'preview-fallback\\'><i data-lucide=\\'image-off\\'></i><span>Preview Unavailable</span></div>'; lucide.createIcons();" />
          <span class="card-type-badge image">IMG</span>
          <span class="card-index-badge">#${item.index}</span>
        </div>
      `;
    } else if (item.type === 'video') {
      previewHtml = `
        <div class="card-preview-area">
          <video src="${escapeHtml(item.url)}" controls preload="metadata" playsinline onerror="this.parentElement.innerHTML='<div class=\\'preview-fallback\\'><i data-lucide=\\'video-off\\'></i><span>Video Preview Unavailable</span></div>'; lucide.createIcons();"></video>
          <span class="card-type-badge video">VID</span>
          <span class="card-index-badge">#${item.index}</span>
        </div>
      `;
    } else if (item.type === 'audio') {
      previewHtml = `
        <div class="card-preview-area">
          <div class="preview-fallback">
            <i data-lucide="music"></i>
            <span>Audio File</span>
          </div>
          <span class="card-type-badge audio">AUD</span>
          <span class="card-index-badge">#${item.index}</span>
        </div>
      `;
    } else {
      previewHtml = `
        <div class="card-preview-area">
          <div class="preview-fallback">
            <i data-lucide="file"></i>
            <span>Direct File</span>
          </div>
          <span class="card-type-badge">FILE</span>
          <span class="card-index-badge">#${item.index}</span>
        </div>
      `;
    }

    card.innerHTML = `
      ${previewHtml}
      <div class="card-meta-area">
        <div>
          <div class="card-filename" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</div>
          <div class="card-url-preview" title="${escapeHtml(item.url)}">${escapeHtml(item.url)}</div>
        </div>
        <div class="card-actions">
          <button class="btn-copy-card" data-url="${escapeHtml(item.url)}">
            <i data-lucide="copy"></i> Copy
          </button>
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer" download="${escapeHtml(item.filename)}">
            <i data-lucide="external-link"></i> Open
          </a>
        </div>
      </div>
    `;

    // Click on preview to zoom
    const previewArea = card.querySelector('.card-preview-area');
    if (previewArea && item.type === 'image') {
      previewArea.addEventListener('click', () => openModal(item));
    }

    // Copy single button handler
    const copyBtn = card.querySelector('.btn-copy-card');
    copyBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      copyToClipboard(item.url, copyBtn);
    });

    return card;
  }

  function createListRow(item) {
    const row = document.createElement('div');
    row.className = 'list-item';
    row.innerHTML = `
      <div class="list-item-left">
        <span class="list-index">#${item.index}</span>
        <a class="list-url-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer" title="${escapeHtml(item.url)}">
          ${escapeHtml(item.url)}
        </a>
      </div>
      <div class="list-actions">
        <button class="btn-copy-list" data-url="${escapeHtml(item.url)}">
          <i data-lucide="copy"></i> Copy
        </button>
        <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">
          <i data-lucide="external-link"></i> Open
        </a>
      </div>
    `;

    const copyBtn = row.querySelector('.btn-copy-list');
    copyBtn.addEventListener('click', () => copyToClipboard(item.url, copyBtn));

    return row;
  }

  // Layout Toggles
  gridViewBtn.addEventListener('click', () => {
    currentLayout = 'grid';
    gridViewBtn.classList.add('active');
    listViewBtn.classList.remove('active');
    mediaGrid.style.display = 'grid';
    mediaList.style.display = 'none';
  });

  listViewBtn.addEventListener('click', () => {
    currentLayout = 'list';
    listViewBtn.classList.add('active');
    gridViewBtn.classList.remove('active');
    mediaGrid.style.display = 'none';
    mediaList.style.display = 'flex';
  });

  // Bulk Copy Action
  copyAllBtn.addEventListener('click', () => {
    if (filteredItems.length === 0) return;
    const allUrls = filteredItems.map(i => i.url).join('\n');
    navigator.clipboard.writeText(allUrls).then(() => {
      showToast(`Copied ${filteredItems.length} URLs to clipboard!`, 'success');
    });
  });

  // Export Dropdown
  exportDropdownBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    exportMenu.style.display = exportMenu.style.display === 'none' ? 'flex' : 'none';
  });

  document.addEventListener('click', () => {
    exportMenu.style.display = 'none';
  });

  exportTxtBtn.addEventListener('click', () => {
    if (filteredItems.length === 0) return;
    const content = filteredItems.map(i => i.url).join('\n');
    downloadBlob(content, 'extracted_links.txt', 'text/plain');
  });

  exportJsonBtn.addEventListener('click', () => {
    if (filteredItems.length === 0) return;
    const content = JSON.stringify(filteredItems, null, 2);
    downloadBlob(content, 'extracted_links.json', 'application/json');
  });

  exportM3uBtn.addEventListener('click', () => {
    if (filteredItems.length === 0) return;
    let content = '#EXTM3U\n';
    filteredItems.forEach(i => {
      content += `#EXTINF:-1,${i.filename}\n${i.url}\n`;
    });
    downloadBlob(content, 'playlist.m3u', 'audio/x-mpegurl');
  });

  function downloadBlob(text, filename, type) {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Downloaded ${filename}`, 'success');
  }

  // Open All Links in Browser Tabs
  openAllBtn.addEventListener('click', () => {
    if (filteredItems.length === 0) return;
    if (filteredItems.length > 20) {
      if (!confirm(`You are about to open ${filteredItems.length} new browser tabs. Continue?`)) {
        return;
      }
    }
    filteredItems.forEach(i => {
      window.open(i.url, '_blank');
    });
    showToast(`Opened ${filteredItems.length} tabs`, 'success');
  });

  // Telegra.ph Publisher
  telegraphBtn.addEventListener('click', async () => {
    if (filteredItems.length === 0) return;
    
    const originalText = telegraphBtn.innerHTML;
    telegraphBtn.disabled = true;
    telegraphBtn.innerHTML = `<div class="spinner"></div> Publishing...`;

    try {
      const urls = filteredItems.map(i => i.url);
      const res = await fetch('/api/telegraph', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `Gallery-DL Extracted (${urls.length} Links)`,
          urls: urls,
          source_url: sourceUrlTag.textContent || '',
        }),
      });

      const data = await res.json();
      telegraphBtn.disabled = false;
      telegraphBtn.innerHTML = originalText;
      lucide.createIcons();

      if (data.success && data.telegraph_url) {
        window.open(data.telegraph_url, '_blank');
        showToast('Created Telegra.ph page! Opened in new tab.', 'success');
      } else {
        showToast(data.detail || 'Failed to publish to Telegra.ph', 'error');
      }
    } catch (err) {
      telegraphBtn.disabled = false;
      telegraphBtn.innerHTML = originalText;
      lucide.createIcons();
      showToast(err.message || 'Telegraph publish error', 'error');
    }
  });

  // Modal / Lightbox
  function openModal(item) {
    modalMediaContainer.innerHTML = '';
    if (item.type === 'image') {
      const img = document.createElement('img');
      img.src = item.url;
      modalMediaContainer.appendChild(img);
    } else if (item.type === 'video') {
      const vid = document.createElement('video');
      vid.src = item.url;
      vid.controls = true;
      vid.autoplay = true;
      modalMediaContainer.appendChild(vid);
    }

    modalMediaInfo.textContent = item.filename;
    modalOpenBtn.href = item.url;
    modalCopyBtn.onclick = () => copyToClipboard(item.url, modalCopyBtn);

    mediaModal.style.display = 'flex';
  }

  function closeModal() {
    mediaModal.style.display = 'none';
    modalMediaContainer.innerHTML = '';
  }

  closeModalBtn.addEventListener('click', closeModal);
  modalBackdrop.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  // Copy Helper with UI Feedback
  function copyToClipboard(text, btnElement) {
    navigator.clipboard.writeText(text).then(() => {
      showToast('Copied direct link to clipboard!', 'success');
      if (btnElement) {
        const oldContent = btnElement.innerHTML;
        btnElement.innerHTML = `<i data-lucide="check"></i> Copied!`;
        btnElement.style.background = 'var(--success)';
        btnElement.style.color = '#fff';
        lucide.createIcons();
        setTimeout(() => {
          btnElement.innerHTML = oldContent;
          btnElement.style.background = '';
          btnElement.style.color = '';
          lucide.createIcons();
        }, 1500);
      }
    });
  }

  // Toast Notification System
  function showToast(message, type = 'normal') {
    const toastContainer = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'info';
    if (type === 'success') icon = 'check-circle';
    if (type === 'error') icon = 'alert-circle';

    toast.innerHTML = `<i data-lucide="${icon}"></i> <span>${escapeHtml(message)}</span>`;
    toastContainer.appendChild(toast);
    lucide.createIcons();

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // History Management (LocalStorage)
  function saveToHistory(sourceUrl, items) {
    try {
      const history = JSON.parse(localStorage.getItem('gallerydl_history') || '[]');
      const entry = {
        id: Date.now(),
        sourceUrl,
        items,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        date: new Date().toLocaleDateString(),
      };
      // Keep max 20 entries
      const updated = [entry, ...history.filter(h => h.sourceUrl !== sourceUrl)].slice(0, 20);
      localStorage.setItem('gallerydl_history', JSON.stringify(updated));
      updateHistoryUI();
    } catch (e) {
      console.error('Failed to save to history', e);
    }
  }

  function updateHistoryUI() {
    try {
      const history = JSON.parse(localStorage.getItem('gallerydl_history') || '[]');
      historyList.innerHTML = '';

      if (history.length === 0) {
        historyBadge.style.display = 'none';
        historyList.innerHTML = `
          <div class="empty-state">
            <i data-lucide="history"></i>
            <p>No recent extractions yet.</p>
          </div>
        `;
        lucide.createIcons();
        return;
      }

      historyBadge.textContent = history.length;
      historyBadge.style.display = 'inline-block';

      history.forEach(item => {
        const card = document.createElement('div');
        card.className = 'history-card';
        card.innerHTML = `
          <div class="history-card-top">
            <span>${item.date} ${item.timestamp}</span>
            <span>${item.items.length} links</span>
          </div>
          <div class="history-card-url">${escapeHtml(item.sourceUrl)}</div>
          <div class="history-card-count">Click to reload results</div>
        `;

        card.addEventListener('click', () => {
          currentItems = item.items;
          sourceUrlTag.textContent = item.sourceUrl;
          applyFilterAndRender();
          resultsSection.style.display = 'block';
          closeDrawer();
          resultsSection.scrollIntoView({ behavior: 'smooth' });
          showToast(`Restored ${item.items.length} links from history!`, 'success');
        });

        historyList.appendChild(card);
      });
      lucide.createIcons();
    } catch (e) {
      console.error('History load error', e);
    }
  }

  // History Drawer Toggles
  historyToggleBtn.addEventListener('click', () => {
    historyDrawer.classList.add('open');
    drawerOverlay.style.display = 'block';
  });

  function closeDrawer() {
    historyDrawer.classList.remove('open');
    drawerOverlay.style.display = 'none';
  }

  closeHistoryBtn.addEventListener('click', closeDrawer);
  drawerOverlay.addEventListener('click', closeDrawer);
  
  clearHistoryBtn.addEventListener('click', () => {
    localStorage.removeItem('gallerydl_history');
    updateHistoryUI();
    showToast('Extraction history cleared', 'success');
  });

  // Theme Toggle
  themeToggleBtn.addEventListener('click', () => {
    const isLight = document.body.classList.toggle('light-theme');
    themeIcon.setAttribute('data-lucide', isLight ? 'sun' : 'moon');
    lucide.createIcons();
  });

  // Utility: Escape HTML
  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, (m) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    })[m]);
  }
});
