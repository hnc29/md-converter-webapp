document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide Icons
  lucide.createIcons();

  // Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const selectFileBtn = document.getElementById('selectFileBtn');
  const fileQueueList = document.getElementById('fileQueueList');
  const fileCountText = document.getElementById('fileCountText');
  const clearAllBtn = document.getElementById('clearAllBtn');
  
  const markdownEditor = document.getElementById('markdownEditor');
  const previewArea = document.getElementById('previewArea');
  const copyBtn = document.getElementById('copyBtn');
  const downloadBtn = document.getElementById('downloadBtn');
  const batchDownloadBtn = document.getElementById('batchDownloadBtn');
  const batchDownloadBtnTop = document.getElementById('batchDownloadBtnTop');
  const batchCountBadge = document.getElementById('batchCountBadge');
  
  const themeToggle = document.getElementById('themeToggle');
  const themeIcon = document.getElementById('themeIcon');
  const splitContainer = document.getElementById('splitContainer');
  const viewTabs = document.querySelectorAll('.tab-btn');
  const loadingOverlay = document.getElementById('loadingOverlay');
  const toastContainer = document.getElementById('toastContainer');
  
  // Health & Metadata elements
  const systemHealth = document.getElementById('systemHealth');
  const healthText = document.getElementById('healthText');
  const metaCard = document.getElementById('metaCard');
  const metaFilename = document.getElementById('metaFilename');
  const metaPages = document.getElementById('metaPages');
  const metaOcrPages = document.getElementById('metaOcrPages');
  const metaLegacy = document.getElementById('metaLegacy');
  const metaDuration = document.getElementById('metaDuration');
  const warningsContainer = document.getElementById('warningsContainer');
  const warningsList = document.getElementById('warningsList');
  const statusDocName = document.getElementById('statusDocName');
  const statWords = document.getElementById('statWords');
  const statChars = document.getElementById('statChars');

  // Application State
  let documents = []; // list of doc objects
  let activeDocId = null;

  // 1. Check System Health
  async function checkHealth() {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        const data = await res.json();
        const dot = systemHealth.querySelector('.status-dot');
        dot.classList.add('healthy');
        
        let engines = [];
        if (data.tesseract_available) engines.push('OCR (Tesseract)');
        if (data.libreoffice_available) engines.push('LibreOffice');

        healthText.textContent = `Sẵn sàng: ${engines.join(', ') || 'MarkItDown Core'}`;
      }
    } catch (e) {
      healthText.textContent = 'API Sẵn sàng';
    }
  }
  checkHealth();

  // 2. Marked setup
  marked.setOptions({
    gfm: true,
    breaks: true,
    highlight: function (code, lang) {
      const language = hljs.getLanguage(lang) ? lang : 'plaintext';
      return hljs.highlight(code, { language }).value;
    }
  });

  function renderPreview(markdown) {
    if (!markdown || !markdown.trim()) {
      previewArea.innerHTML = `
        <div class="preview-empty">
          <i data-lucide="file-code"></i>
          <p>Chưa có dữ liệu xem trước</p>
          <span>Hãy chọn một tài liệu trong danh sách bên trái để xem kết quả Markdown</span>
        </div>
      `;
      lucide.createIcons();
      return;
    }
    previewArea.innerHTML = marked.parse(markdown);
  }

  function updateStats(markdown) {
    const cleanText = (markdown || '').replace(/[#*`_~\[\]()><!|]/g, ' ').replace(/\s+/g, ' ').trim();
    const words = cleanText ? cleanText.split(/\s+/).length : 0;
    const chars = (markdown || '').length;
    statWords.textContent = `${words} từ`;
    statChars.textContent = `${chars} ký tự`;
  }

  function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    switch (ext) {
      case 'xlsx':
      case 'xls':
        return '<i data-lucide="table" style="color: #34d399"></i>';
      case 'docx':
      case 'doc':
        return '<i data-lucide="file-text" style="color: #60a5fa"></i>';
      case 'pdf':
        return '<i data-lucide="file-type" style="color: #f87171"></i>';
      default:
        return '<i data-lucide="file" style="color: #a78bfa"></i>';
    }
  }

  // 3. Render File Queue UI
  function renderQueue() {
    fileCountText.textContent = documents.length;
    
    const completedDocs = documents.filter(d => d.status === 'completed');
    if (completedDocs.length > 0) {
      batchDownloadBtn.disabled = false;
      batchDownloadBtnTop.style.display = 'inline-flex';
      batchCountBadge.textContent = completedDocs.length;
      clearAllBtn.style.display = 'inline-flex';
    } else {
      batchDownloadBtn.disabled = true;
      batchDownloadBtnTop.style.display = 'none';
      clearAllBtn.style.display = documents.length > 0 ? 'inline-flex' : 'none';
    }

    if (documents.length === 0) {
      fileQueueList.innerHTML = `
        <div class="queue-empty">
          <i data-lucide="files" opacity="0.4"></i>
          <p>Chưa có tệp nào trong danh sách</p>
          <span>Kéo thả hoặc bấm nút trên để chọn nhiều tệp</span>
        </div>
      `;
      metaCard.style.display = 'none';
      markdownEditor.value = '';
      renderPreview('');
      updateStats('');
      statusDocName.textContent = 'Chưa chọn tệp';
      copyBtn.disabled = true;
      downloadBtn.disabled = true;
      lucide.createIcons();
      return;
    }

    fileQueueList.innerHTML = documents.map(doc => {
      const isActive = doc.id === activeDocId;
      let statusBadge = '';
      
      if (doc.status === 'processing') {
        statusBadge = '<span style="color: #3b82f6; font-size: 0.725rem;"><span class="spin" style="display:inline-block">⏳</span> Đang chuyển đổi...</span>';
      } else if (doc.status === 'completed') {
        const ocrTag = (doc.pages_ocr && doc.pages_ocr.length > 0) ? '<span class="badge badge-red" style="font-size: 0.65rem; padding: 0.1rem 0.4rem;">OCR</span>' : '';
        statusBadge = `<span style="color: #10b981; font-size: 0.725rem;">✓ Hoàn thành (${doc.pages_total || 1} trang) ${ocrTag}</span>`;
      } else if (doc.status === 'error') {
        statusBadge = `<span style="color: #ef4444; font-size: 0.725rem;" title="${doc.errorMessage || ''}">✗ Lỗi chuyển đổi</span>`;
      }

      return `
        <div class="queue-item ${isActive ? 'active' : ''}" data-id="${doc.id}">
          <div class="queue-item-info">
            <div class="queue-item-icon">
              ${getFileIcon(doc.filename)}
            </div>
            <div class="queue-item-details">
              <span class="queue-item-name" title="${doc.filename}">${doc.filename}</span>
              <div class="queue-item-meta">
                ${statusBadge}
              </div>
            </div>
          </div>
          <div class="queue-item-actions">
            ${doc.status === 'completed' ? `
              <button class="btn-icon-sm btn-download-single" data-id="${doc.id}" title="Tải file .md này">
                <i data-lucide="download" style="width: 14px; height: 14px;"></i>
              </button>
            ` : ''}
            <button class="btn-icon-sm btn-remove-single" data-id="${doc.id}" title="Xóa khỏi danh sách" style="color: var(--danger)">
              <i data-lucide="trash-2" style="width: 14px; height: 14px;"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    lucide.createIcons();

    // Attach click events
    fileQueueList.querySelectorAll('.queue-item').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.closest('.queue-item-actions')) return;
        const id = item.getAttribute('data-id');
        selectActiveDocument(id);
      });
    });

    fileQueueList.querySelectorAll('.btn-download-single').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        const doc = documents.find(d => d.id === id);
        if (doc) downloadSingleDoc(doc);
      });
    });

    fileQueueList.querySelectorAll('.btn-remove-single').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        removeDocument(id);
      });
    });
  }

  // 4. Select Active Document for Editor/Preview
  function selectActiveDocument(id) {
    activeDocId = id;
    const doc = documents.find(d => d.id === id);
    if (!doc) return;

    renderQueue();

    markdownEditor.value = doc.markdown || '';
    renderPreview(doc.markdown || '');
    updateStats(doc.markdown || '');
    statusDocName.textContent = doc.filename;

    if (doc.status === 'completed') {
      copyBtn.disabled = false;
      downloadBtn.disabled = false;

      metaCard.style.display = 'block';
      metaFilename.textContent = doc.filename;
      metaFilename.title = doc.filename;
      metaPages.textContent = `${doc.pages_total || 1} trang`;
      
      if (doc.pages_ocr && doc.pages_ocr.length > 0) {
        metaOcrPages.textContent = `Trang: ${doc.pages_ocr.join(', ')}`;
        metaOcrPages.className = 'badge badge-red';
      } else {
        metaOcrPages.textContent = 'Không có (Text layer số)';
        metaOcrPages.className = 'badge badge-green';
      }

      metaLegacy.textContent = doc.converted_via_legacy ? 'Có (Chuyển qua LibreOffice)' : 'Không (Định dạng chuẩn)';
      metaDuration.textContent = `${doc.duration_ms || 0} ms`;

      if (doc.warnings && doc.warnings.length > 0) {
        warningsContainer.style.display = 'block';
        warningsList.innerHTML = doc.warnings.map(w => `<li>${w}</li>`).join('');
      } else {
        warningsContainer.style.display = 'none';
      }
    } else {
      metaCard.style.display = 'none';
      copyBtn.disabled = true;
      downloadBtn.disabled = true;
    }
  }

  function removeDocument(id) {
    documents = documents.filter(d => d.id !== id);
    if (activeDocId === id) {
      activeDocId = documents.length > 0 ? documents[0].id : null;
    }
    if (activeDocId) {
      selectActiveDocument(activeDocId);
    } else {
      renderQueue();
    }
    showToast('Đã xóa tệp khỏi danh sách', 'info');
  }

  clearAllBtn.addEventListener('click', () => {
    if (confirm('Bạn có chắc muốn xóa tất cả các tệp khỏi danh sách?')) {
      documents = [];
      activeDocId = null;
      renderQueue();
      showToast('Đã xóa toàn bộ danh sách tệp', 'info');
    }
  });

  // 5. Individual & Batch File Conversion
  async function convertSingleFile(docItem) {
    const formData = new FormData();
    formData.append('file', docItem.file);

    try {
      const response = await fetch('/api/convert', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'Lỗi máy chủ' }));
        throw new Error(errData.detail || `Lỗi (${response.status})`);
      }

      const res = await response.json();

      // Update state
      documents = documents.map(d => {
        if (d.id === docItem.id) {
          return {
            ...d,
            status: 'completed',
            markdown: res.markdown,
            pages_total: res.pages_total,
            pages_ocr: res.pages_ocr,
            converted_via_legacy: res.converted_via_legacy,
            duration_ms: res.duration_ms,
            word_count: res.word_count,
            character_count: res.character_count,
            warnings: res.warnings
          };
        }
        return d;
      });

      if (activeDocId === docItem.id) {
        selectActiveDocument(docItem.id);
      } else {
        renderQueue();
      }

      return true;
    } catch (err) {
      documents = documents.map(d => {
        if (d.id === docItem.id) {
          return {
            ...d,
            status: 'error',
            errorMessage: err.message,
            markdown: `<!-- Lỗi khi chuyển đổi: ${err.message} -->`
          };
        }
        return d;
      });

      if (activeDocId === docItem.id) {
        selectActiveDocument(docItem.id);
      } else {
        renderQueue();
      }
      return false;
    }
  }

  async function handleFiles(fileList) {
    const files = Array.from(fileList);
    if (files.length === 0) return;

    const newDocs = files.map(file => ({
      id: Math.random().toString(36).substring(2, 9),
      file: file,
      filename: file.name,
      status: 'processing',
      markdown: '',
      pages_total: 0,
      pages_ocr: [],
      converted_via_legacy: false,
      duration_ms: 0,
      word_count: 0,
      character_count: 0,
      warnings: [],
      errorMessage: ''
    }));

    // Prepend new documents to list
    documents = [...newDocs, ...documents];
    activeDocId = newDocs[0].id;
    renderQueue();
    selectActiveDocument(newDocs[0].id);

    showToast(`Đang chuyển đổi ${files.length} tệp...`, 'info');

    // Process all files concurrently
    await Promise.all(newDocs.map(docItem => convertSingleFile(docItem)));

    const successCount = newDocs.filter(nd => {
      const d = documents.find(doc => doc.id === nd.id);
      return d && d.status === 'completed';
    }).length;

    if (successCount === files.length) {
      showToast(`Đã chuyển đổi thành công tất cả ${files.length} tệp!`, 'success');
    } else {
      showToast(`Hoàn tất: ${successCount}/${files.length} tệp thành công.`, 'warning');
    }

    // Ensure active document view is rendered
    if (activeDocId) {
      selectActiveDocument(activeDocId);
    }
  }

  // 6. Download Handlers
  function downloadSingleDoc(doc) {
    if (!doc || !doc.markdown) return;
    const base = doc.filename.replace(/\.[^/.]+$/, '');
    const blob = new Blob([doc.markdown], { type: 'text/markdown;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${base}.md`;
    link.click();
    URL.revokeObjectURL(link.href);
    showToast(`Đã tải về tệp ${base}.md`, 'success');
  }

  async function downloadBatchZip() {
    const completedDocs = documents.filter(d => d.status === 'completed' && d.markdown);
    if (completedDocs.length === 0) {
      showToast('Không có tệp đã hoàn thành để tải', 'warning');
      return;
    }

    try {
      const zip = new JSZip();
      completedDocs.forEach(doc => {
        const base = doc.filename.replace(/\.[^/.]+$/, '');
        const mdName = `${base}.md`;
        zip.file(mdName, doc.markdown);
      });

      const zipBlob = await zip.generateAsync({ type: 'blob' });
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const link = document.createElement('a');
      link.href = URL.createObjectURL(zipBlob);
      link.download = `converted_markdown_${timestamp}.zip`;
      link.click();
      URL.revokeObjectURL(link.href);

      showToast(`Đã tạo và tải về file nén ${completedDocs.length} tệp .md thành công!`, 'success');
    } catch (err) {
      showToast(`Lỗi khi tạo file zip: ${err.message}`, 'error');
    }
  }

  // 7. Event Listeners for File Selection
  selectFileBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener('click', (e) => {
    if (e.target === selectFileBtn || e.target.closest('#selectFileBtn')) return;
    fileInput.click();
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
      fileInput.value = '';
    }
  });

  // Drag & Drop
  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('drag-active');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-active');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  });

  markdownEditor.addEventListener('input', (e) => {
    const text = e.target.value;
    if (activeDocId) {
      documents = documents.map(d => d.id === activeDocId ? { ...d, markdown: text } : d);
    }
    renderPreview(text);
    updateStats(text);
  });

  copyBtn.addEventListener('click', async () => {
    const text = markdownEditor.value;
    if (!text) return;
    await navigator.clipboard.writeText(text);
    showToast('Đã sao chép Markdown vào bộ nhớ tạm!', 'success');
  });

  downloadBtn.addEventListener('click', () => {
    const doc = documents.find(d => d.id === activeDocId);
    if (doc) downloadSingleDoc(doc);
  });

  batchDownloadBtn.addEventListener('click', downloadBatchZip);
  batchDownloadBtnTop.addEventListener('click', downloadBatchZip);

  // View Tabs
  viewTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      viewTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const view = tab.getAttribute('data-view');
      splitContainer.className = `split-container view-${view}`;
    });
  });

  // Theme Toggle
  themeToggle.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const nextTheme = isDark ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', nextTheme);
    themeIcon.setAttribute('data-lucide', nextTheme === 'dark' ? 'sun' : 'moon');
    lucide.createIcons();
  });

  // Toast Helper
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 4000);
  }
});
