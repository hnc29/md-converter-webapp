document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide Icons
  lucide.createIcons();

  // Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const selectFileBtn = document.getElementById('selectFileBtn');
  const fileQueueList = document.getElementById('fileQueueList');
  const clearAllBtn = document.getElementById('clearAllBtn');
  
  const summaryBanner = document.getElementById('summaryBanner');
  const readyBadge = document.getElementById('readyBadge');
  const warnBadge = document.getElementById('warnBadge');
  const failBadge = document.getElementById('failBadge');

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
  const ocrStatusBadge = document.getElementById('ocrStatusBadge');
  const metaCard = document.getElementById('metaCard');
  const metaTargetFolder = document.getElementById('metaTargetFolder');
  const metaDocId = document.getElementById('metaDocId');
  const metaTitle = document.getElementById('metaTitle');
  const metaOcrEngine = document.getElementById('metaOcrEngine');
  const metaValidation = document.getElementById('metaValidation');
  const metaRetention = document.getElementById('metaRetention');
  const metaSha256 = document.getElementById('metaSha256');
  const warningsContainer = document.getElementById('warningsContainer');
  const warningsList = document.getElementById('warningsList');
  const statusDocName = document.getElementById('statusDocName');
  const statWords = document.getElementById('statWords');
  const statChars = document.getElementById('statChars');

  // Application State
  let documents = []; // list of doc objects
  let activeDocId = null;
  let kbMasterIndex = '';
  let kbManifest = null;
  let kbReport = '';
  let kbReadme = '';
  let rawFilesCache = [];

  // OCR Engine Selection Setup
  const ocrRadios = document.querySelectorAll('input[name="ocrEngine"]');
  const savedOcrEngine = localStorage.getItem('doc2md_ocr_engine') || 'tesseract';
  
  function updateOcrSelectionUI(engineVal) {
    ocrRadios.forEach(radio => {
      const isChecked = radio.value === engineVal;
      radio.checked = isChecked;
      const label = radio.closest('.engine-option-label');
      if (label) {
        if (isChecked) {
          label.classList.add('selected');
        } else {
          label.classList.remove('selected');
        }
      }
    });
  }

  updateOcrSelectionUI(savedOcrEngine);

  ocrRadios.forEach(radio => {
    radio.addEventListener('change', (e) => {
      const selected = e.target.value;
      localStorage.setItem('doc2md_ocr_engine', selected);
      updateOcrSelectionUI(selected);
      showToast(`Đã chọn OCR Engine: ${selected === 'paddleocr' ? 'PaddleOCR (Deep Learning)' : 'Tesseract OCR (Nhanh)'}`, 'info');
    });
  });

  // 1. Check System Health
  async function checkHealth() {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        const data = await res.json();
        const dot = systemHealth.querySelector('.status-dot');
        dot.classList.add('healthy');
        
        let engines = [];
        if (data.tesseract_available) engines.push('Tesseract');
        if (data.paddleocr_available) engines.push('PaddleOCR');
        if (data.libreoffice_available) engines.push('LibreOffice');

        healthText.textContent = `Sẵn sàng: ${engines.join(' • ') || 'MarkItDown'}`;
        if (ocrStatusBadge) {
          const count = (data.tesseract_available ? 1 : 0) + (data.paddleocr_available ? 1 : 0);
          ocrStatusBadge.textContent = `${count} Models Sẵn Sàng`;
        }
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
    if (filename === '00_Master_Index.md') return '<i data-lucide="map" style="color: #f59e0b"></i>';
    if (filename === 'conversion_report.md') return '<i data-lucide="clipboard-check" style="color: #10b981"></i>';
    if (filename === 'manifest.json') return '<i data-lucide="file-json" style="color: #6366f1"></i>';
    if (filename === 'README.txt') return '<i data-lucide="info" style="color: #38bdf8"></i>';

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

  // 3. Render File Queue UI with Folder Grouping
  function renderQueue() {
    const readyDocs = documents.filter(d => d.group === 'upload_to_ai');
    const technicalDocs = documents.filter(d => d.group === 'technical');

    if (documents.length > 0) {
      batchDownloadBtn.disabled = false;
      batchDownloadBtnTop.style.display = 'inline-flex';
      batchCountBadge.textContent = readyDocs.length;
      clearAllBtn.style.display = 'inline-flex';
    } else {
      batchDownloadBtn.disabled = true;
      batchDownloadBtnTop.style.display = 'none';
      clearAllBtn.style.display = 'none';
      summaryBanner.style.display = 'none';
    }

    if (documents.length === 0) {
      fileQueueList.innerHTML = `
        <div class="queue-empty">
          <i data-lucide="files" opacity="0.4"></i>
          <p>Chưa có tài liệu nào</p>
          <span>Kéo thả hoặc bấm nút <strong>BUILD KNOWLEDGE</strong> ở trên</span>
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

    let html = '';

    // Folder 1: upload_to_ai/ (Ready for AI)
    if (readyDocs.length > 0) {
      html += `
        <div class="folder-group-header folder-upload">
          <i data-lucide="folder-check" style="width: 14px; height: 14px;"></i>
          <span>Thư mục: upload_to_ai/ (${readyDocs.length} file an toàn)</span>
        </div>
      `;
      html += readyDocs.map(doc => renderDocItemHtml(doc)).join('');
    }

    // Folder 2: technical/
    if (technicalDocs.length > 0) {
      html += `
        <div class="folder-group-header folder-technical">
          <i data-lucide="folder-cog" style="width: 14px; height: 14px;"></i>
          <span>Thư mục: technical/ & Báo cáo (${technicalDocs.length})</span>
        </div>
      `;
      html += technicalDocs.map(doc => renderDocItemHtml(doc)).join('');
    }

    fileQueueList.innerHTML = html;
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

  function renderDocItemHtml(doc) {
    const isActive = doc.id === activeDocId;
    let statusBadge = '';
    
    if (doc.isSpecial) {
      statusBadge = '<span class="badge badge-accent" style="font-size: 0.65rem; padding: 0.1rem 0.4rem;">Knowledge Entry</span>';
    } else {
      const vStatus = doc.validation ? doc.validation.status : 'PASS';
      const vColor = vStatus === 'PASS' ? '#10b981' : (vStatus === 'WARNING' ? '#f59e0b' : '#ef4444');
      const ocrTag = (doc.pages_ocr && doc.pages_ocr.length > 0) ? '<span class="badge badge-red" style="font-size: 0.65rem; padding: 0.1rem 0.4rem; margin-left: 3px;">OCR</span>' : '';
      statusBadge = `<span style="color: ${vColor}; font-size: 0.725rem; font-weight: 500;">✓ ${vStatus} (${doc.pages_total || 1} trang)</span> ${ocrTag}`;
    }

    return `
      <div class="queue-item ${isActive ? 'active' : ''} ${doc.isSpecial ? 'special-item' : ''}" data-id="${doc.id}">
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
          <button class="btn-icon-sm btn-download-single" data-id="${doc.id}" title="Tải file này">
            <i data-lucide="download" style="width: 14px; height: 14px;"></i>
          </button>
          ${!doc.isSpecial ? `
            <button class="btn-icon-sm btn-remove-single" data-id="${doc.id}" title="Xóa khỏi danh sách" style="color: var(--danger)">
              <i data-lucide="trash-2" style="width: 14px; height: 14px;"></i>
            </button>
          ` : ''}
        </div>
      </div>
    `;
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

    copyBtn.disabled = false;
    downloadBtn.disabled = false;

    metaCard.style.display = 'block';
    metaTargetFolder.textContent = doc.group === 'upload_to_ai' ? 'upload_to_ai/' : 'technical/';
    metaTargetFolder.style.color = doc.group === 'upload_to_ai' ? '#38bdf8' : '#a78bfa';

    metaDocId.textContent = doc.document_id || (doc.metadata ? doc.metadata.document_id : '-');
    metaTitle.textContent = (doc.metadata && doc.metadata.title) ? doc.metadata.title : doc.filename;
    metaTitle.title = metaTitle.textContent;

    if (metaOcrEngine) {
      const eng = doc.ocr_engine_used || 'Tesseract';
      metaOcrEngine.textContent = eng.toUpperCase();
      metaOcrEngine.className = `badge ${eng.toLowerCase().includes('paddle') ? 'badge-accent' : 'badge-blue'}`;
    }

    if (doc.validation) {
      metaValidation.textContent = doc.validation.status;
      metaValidation.className = `badge ${doc.validation.status === 'PASS' ? 'badge-green' : (doc.validation.status === 'WARNING' ? 'badge-yellow' : 'badge-red')}`;
    } else {
      metaValidation.textContent = 'PASS';
      metaValidation.className = 'badge badge-green';
    }

    if (doc.metadata) {
      metaRetention.textContent = `${Math.round(doc.metadata.text_retention_ratio * 100)}%`;
      metaSha256.textContent = doc.metadata.source_sha256 ? `${doc.metadata.source_sha256.substring(0, 18)}...` : '-';
    } else {
      metaRetention.textContent = '100%';
      metaSha256.textContent = '-';
    }

    const allWarns = (doc.warnings || []).concat(doc.validation ? doc.validation.warnings : []);
    if (allWarns.length > 0) {
      warningsContainer.style.display = 'block';
      warningsList.innerHTML = Array.from(new Set(allWarns)).map(w => `<li>${w}</li>`).join('');
    } else {
      warningsContainer.style.display = 'none';
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
      rawFilesCache = [];
      activeDocId = null;
      renderQueue();
      showToast('Đã xóa toàn bộ danh sách tệp', 'info');
    }
  });

  // 5. BUILD KNOWLEDGE Batch Execution
  async function handleFiles(fileList) {
    const files = Array.from(fileList);
    if (files.length === 0) return;

    rawFilesCache = files;
    loadingOverlay.style.display = 'flex';

    const activeOcrEngine = document.querySelector('input[name="ocrEngine"]:checked')?.value || 'tesseract';

    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    formData.append('ocr_engine', activeOcrEngine);

    showToast(`Đang BUILD KNOWLEDGE (${activeOcrEngine.toUpperCase()}) cho ${files.length} tài liệu...`, 'info');

    try {
      const response = await fetch('/api/convert-knowledge-base', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'Lỗi máy chủ' }));
        throw new Error(errData.detail || `Lỗi (${response.status})`);
      }

      const kbData = await response.json();
      kbMasterIndex = kbData.master_index_md;
      kbManifest = kbData.manifest_json;
      kbReport = kbData.conversion_report_md;
      kbReadme = kbData.readme_txt;

      // Update Summary Banner
      summaryBanner.style.display = 'flex';
      readyBadge.textContent = `🚀 ${kbData.ready_count} Sẵn sàng nạp AI`;
      
      if (kbData.warning_count > 0) {
        warnBadge.style.display = 'inline-block';
        warnBadge.textContent = `⚠️ ${kbData.warning_count} Cảnh báo`;
      } else {
        warnBadge.style.display = 'none';
      }

      if (kbData.failed_count > 0) {
        failBadge.style.display = 'inline-block';
        failBadge.textContent = `❌ ${kbData.failed_count} Cần kiểm tra`;
      } else {
        failBadge.style.display = 'none';
      }

      // Build structured document list
      const readyDocItems = [];
      if (!kbData.is_single_mode && kbMasterIndex) {
        readyDocItems.push({
          id: 'kb_master_index',
          filename: '00_Master_Index.md',
          document_id: 'MASTER-INDEX',
          status: 'completed',
          isSpecial: true,
          group: 'upload_to_ai',
          markdown: kbMasterIndex,
          pages_total: 1,
          pages_ocr: [],
          ocr_engine_used: activeOcrEngine,
          warnings: []
        });
      }

      kbData.upload_to_ai_documents.forEach(d => {
        const baseName = d.filename.replace(/\.[^/.]+$/, '');
        readyDocItems.push({
          id: Math.random().toString(36).substring(2, 9),
          filename: `${baseName}.md`,
          document_id: d.document_id,
          status: 'completed',
          isSpecial: false,
          group: 'upload_to_ai',
          markdown: d.markdown,
          metadata: d.metadata,
          sections: d.sections,
          validation: d.validation,
          pages_total: d.pages_total,
          pages_ocr: d.pages_ocr,
          ocr_engine_used: d.ocr_engine_used || activeOcrEngine,
          duration_ms: d.duration_ms,
          word_count: d.word_count,
          character_count: d.character_count,
          warnings: d.warnings || []
        });
      });

      const technicalDocItems = [
        {
          id: 'kb_report',
          filename: 'conversion_report.md',
          document_id: 'QUALITY-REPORT',
          status: 'completed',
          isSpecial: true,
          group: 'technical',
          markdown: kbReport,
          pages_total: 1,
          pages_ocr: [],
          warnings: []
        },
        {
          id: 'kb_manifest',
          filename: 'manifest.json',
          document_id: 'MANIFEST-JSON',
          status: 'completed',
          isSpecial: true,
          group: 'technical',
          markdown: '```json\n' + JSON.stringify(kbManifest, null, 2) + '\n```',
          pages_total: 1,
          pages_ocr: [],
          warnings: []
        },
        {
          id: 'kb_readme',
          filename: 'README.txt',
          document_id: 'README-TXT',
          status: 'completed',
          isSpecial: true,
          group: 'technical',
          markdown: '```text\n' + kbReadme + '\n```',
          pages_total: 1,
          pages_ocr: [],
          warnings: []
        }
      ];

      kbData.failed_documents.forEach(d => {
        const baseName = d.filename.replace(/\.[^/.]+$/, '');
        technicalDocItems.push({
          id: Math.random().toString(36).substring(2, 9),
          filename: `failed/${baseName}.md`,
          document_id: d.document_id,
          status: 'error',
          isSpecial: false,
          group: 'technical',
          markdown: d.markdown,
          metadata: d.metadata,
          sections: d.sections,
          validation: d.validation,
          pages_total: d.pages_total,
          pages_ocr: d.pages_ocr,
          warnings: d.warnings || []
        });
      });

      documents = [...readyDocItems, ...technicalDocItems];
      activeDocId = readyDocItems[0] ? readyDocItems[0].id : technicalDocItems[0].id;
      renderQueue();
      selectActiveDocument(activeDocId);

      showToast(`Đã BUILD KNOWLEDGE thành công (${kbData.ready_count} tài liệu trong upload_to_ai/)!`, 'success');

    } catch (err) {
      showToast(`Lỗi: ${err.message}`, 'error');
    } finally {
      loadingOverlay.style.display = 'none';
    }
  }

  // 6. Download Handlers
  function downloadSingleDoc(doc) {
    if (!doc || !doc.markdown) return;
    const filename = doc.filename.endsWith('.md') || doc.filename.endsWith('.json') || doc.filename.endsWith('.txt') ? doc.filename.split('/').pop() : `${doc.filename.replace(/\.[^/.]+$/, '')}.md`;
    let content = doc.markdown;
    if (doc.filename === 'manifest.json' && kbManifest) {
      content = JSON.stringify(kbManifest, null, 2);
    } else if (doc.filename === 'README.txt' && kbReadme) {
      content = kbReadme;
    }
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
    showToast(`Đã tải về tệp ${filename}`, 'success');
  }

  async function downloadKnowledgeBaseZip() {
    if (!rawFilesCache || rawFilesCache.length === 0) {
      showToast('Không có tài liệu nguồn để đóng gói', 'warning');
      return;
    }

    loadingOverlay.style.display = 'flex';
    showToast('Đang đóng gói Knowledge Package (.zip)...', 'info');

    try {
      const activeOcrEngine = document.querySelector('input[name="ocrEngine"]:checked')?.value || 'tesseract';
      const formData = new FormData();
      rawFilesCache.forEach(f => formData.append('files', f));
      formData.append('ocr_engine', activeOcrEngine);

      const res = await fetch('/api/convert-knowledge-base/zip', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) throw new Error(`Lỗi tải gói zip (${res.status})`);

      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `Knowledge_Package.zip`;
      link.click();
      URL.revokeObjectURL(link.href);

      showToast('Đã tải về gói Knowledge_Package.zip thành công!', 'success');
    } catch (err) {
      showToast(`Lỗi: ${err.message}`, 'error');
    } finally {
      loadingOverlay.style.display = 'none';
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

  batchDownloadBtn.addEventListener('click', downloadKnowledgeBaseZip);
  batchDownloadBtnTop.addEventListener('click', downloadKnowledgeBaseZip);

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
