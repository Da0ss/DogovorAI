/**
 * DogovorAI — Dashboard Logic
 */

const API_ANALYZE = '/api/analyze';
const API_HISTORY = '/api/history';

let currentUser = null;
let token = null;

// Selectors
const mainWorkspace = document.querySelector('main');
const docViewerSection = document.querySelector('section.lg\\:w-7\\/12');
const riskCardsSection = document.querySelector('section.lg\\:w-5\\/12');
const progressBarSection = document.querySelector('section.bg-surface-container-low');

// Get Auth Token
function checkAuth() {
  token = localStorage.getItem('access_token');
  currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  if (!token) {
    window.location.href = '/app/login';
    return false;
  }
  return true;
}

// Fetch user history
async function loadHistory() {
  try {
    const res = await fetch(API_HISTORY, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Failed to load history');
    const data = await res.json();
    return data.items || [];
  } catch (err) {
    console.error(err);
    return [];
  }
}

// Render the Dropzone / Upload State
function renderUploadState() {
  if (progressBarSection) {
    progressBarSection.style.display = 'none';
  }
  
  if (docViewerSection) {
    docViewerSection.className = "w-full lg:w-12/12 flex flex-col bg-surface-container-lowest rounded-xl shadow-luminous border border-outline-variant p-10 items-center justify-center text-center relative";
    docViewerSection.style.height = 'calc(100vh - 280px)';
    
    docViewerSection.innerHTML = `
      <div id="dropzone" class="border-2 border-dashed border-outline-variant hover:border-primary rounded-xl p-10 flex flex-col items-center justify-center cursor-pointer transition-all duration-300 w-full max-w-xl h-80 bg-surface">
        <span class="material-symbols-outlined text-[64px] text-outline mb-4">cloud_upload</span>
        <h3 class="font-title-md text-title-md text-on-surface mb-2">Загрузите документ для анализа</h3>
        <p class="font-body-sm text-body-sm text-on-surface-variant max-w-xs mb-6">Поддерживаются форматы PDF, DOCX, TXT, PNG, JPG</p>
        <button class="bg-primary text-on-primary font-label-caps text-label-caps uppercase px-6 py-3 rounded-lg hover:brightness-110 active:scale-95 transition-all">Выбрать файл</button>
        <input type="file" id="fileInput" class="hidden" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg">
      </div>
    `;
    
    // Bind click & drag handlers
    const dropzone = docViewerSection.querySelector('#dropzone');
    const fileInput = docViewerSection.querySelector('#fileInput');
    
    dropzone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFileSelect(e.target.files[0]));
    
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('border-primary', 'bg-surface-container-low');
    });
    
    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('border-primary', 'bg-surface-container-low');
    });
    
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('border-primary', 'bg-surface-container-low');
      if (e.dataTransfer.files.length > 0) {
        handleFileSelect(e.dataTransfer.files[0]);
      }
    });
  }
  
  if (riskCardsSection) {
    riskCardsSection.style.display = 'none';
  }
}

// Render Circular Loading state during analysis
function renderLoadingState(fileName) {
  if (docViewerSection) {
    docViewerSection.innerHTML = `
      <div class="flex flex-col items-center justify-center text-center w-full max-w-md space-y-6">
        <div class="mb-lg flex items-center gap-sm bg-surface-container-high px-4 py-2 rounded-full border border-outline-variant">
          <span class="material-symbols-outlined text-secondary text-lg">description</span>
          <span class="font-body-sm text-body-sm text-on-surface-variant">${fileName}</span>
        </div>
        <div class="relative w-48 h-48 flex items-center justify-center">
          <div class="absolute inset-0 border-4 border-outline-variant rounded-full opacity-20"></div>
          <div class="absolute inset-0 border-t-4 border-primary rounded-full animate-spin"></div>
          <span class="material-symbols-outlined text-primary text-[48px]">security</span>
        </div>
        <div>
          <h2 class="text-xl font-semibold shimmer-text">Анализируем документ...</h2>
          <p class="text-gray-400 text-sm mt-2">Наша нейросеть выявляет скрытые юридические риски и готовит рекомендации.</p>
        </div>
      </div>
    `;
  }
}

// Handle File Selection and Upload
async function handleFileSelect(file) {
  if (!file) return;
  
  renderLoadingState(file.name);
  
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const res = await fetch(API_ANALYZE, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Ошибка при анализе документа.');
    }
    
    const analysisResult = await res.json();
    renderAnalysisResult(file.name, analysisResult);
  } catch (err) {
    alert(err.message);
    renderUploadState();
  }
}

// Render Analysis Results
function renderAnalysisResult(fileName, result) {
  // Show progress bar section
  if (progressBarSection) {
    progressBarSection.style.display = 'block';
    
    // Update counters
    const criticalCount = result.risks.filter(r => r.severity === 'critical').length;
    const amberCount = result.risks.filter(r => r.severity === 'warning' || r.severity === 'amber').length;
    const neutralCount = result.risks.length - criticalCount - amberCount;
    
    progressBarSection.innerHTML = `
      <div class="max-w-container-max mx-auto px-gutter">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-end mb-sm gap-md">
          <div>
            <h1 class="font-headline-lg text-headline-lg text-on-surface mb-xs">${fileName}</h1>
            <p class="font-body-sm text-body-sm text-on-surface-variant">Анализ завершен сегодня в ${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</p>
          </div>
          <div class="flex gap-md font-label-caps text-label-caps uppercase">
            <div class="flex items-center gap-xs text-error"><span class="w-2 h-2 rounded-full bg-error"></span> ${criticalCount} Критических</div>
            <div class="flex items-center gap-xs text-tertiary"><span class="w-2 h-2 rounded-full bg-tertiary"></span> ${amberCount} Предупреждений</div>
            <div class="flex items-center gap-xs text-on-surface-variant"><span class="w-2 h-2 rounded-full bg-outline"></span> ${neutralCount} Информационных</div>
          </div>
        </div>
        <div class="w-full h-3 bg-surface-container-highest rounded-full overflow-hidden flex shadow-inner">
          <div class="h-full bg-error" style="width: ${result.risks.length ? (criticalCount / result.risks.length * 100) : 0}%;"></div>
          <div class="h-full bg-tertiary" style="width: ${result.risks.length ? (amberCount / result.risks.length * 100) : 0}%;"></div>
          <div class="h-full bg-outline" style="width: ${result.risks.length ? (neutralCount / result.risks.length * 100) : 0}%;"></div>
        </div>
      </div>
    `;
  }
  
  // Update Left Pane: Document Text Viewer
  if (docViewerSection) {
    docViewerSection.className = "w-full lg:w-7/12 flex flex-col bg-surface-container-lowest rounded-xl shadow-luminous border border-outline-variant overflow-hidden relative";
    docViewerSection.style.height = 'calc(100vh - 280px)';
    
    // Convert document text to simple HTML paragraphs
    let docTextHtml = result.text.split('\n\n').map(p => `<p class="mb-4">${p}</p>`).join('');
    if (!docTextHtml.trim()) {
      docTextHtml = `<p class="text-gray-400 italic">Текст договора успешно извлечен и обработан.</p>`;
    }
    
    docViewerSection.innerHTML = `
      <div class="bg-surface-container py-sm px-lg border-b border-outline-variant flex justify-between items-center z-10 sticky top-0">
        <div class="font-label-caps text-label-caps text-on-surface-variant flex items-center gap-xs">
          <span class="material-symbols-outlined text-[18px]">description</span> 
          ${fileName}
        </div>
        <div class="flex gap-sm">
          <button onclick="renderUploadState()" class="px-3 py-1 rounded bg-primary/10 hover:bg-primary/20 text-primary font-label-caps text-xs flex items-center gap-1 transition-colors">
            <span class="material-symbols-outlined text-sm">cloud_upload</span> Загрузить новый
          </button>
        </div>
      </div>
      <div class="p-lg md:p-xl overflow-y-auto custom-scrollbar font-body-lg text-body-lg text-on-surface/90 leading-relaxed relative bg-surface-container-lowest">
        ${docTextHtml}
      </div>
    `;
  }
  
  // Update Right Pane: Risk cards
  if (riskCardsSection) {
    riskCardsSection.style.display = 'flex';
    riskCardsSection.innerHTML = `
      <div class="font-label-caps text-label-caps text-on-surface-variant mb-xs px-xs uppercase tracking-wider">Найдено рисков (${result.risks.length})</div>
    `;
    
    if (result.risks.length === 0) {
      riskCardsSection.innerHTML += `
        <div class="bg-surface-container rounded-xl p-md shadow-sm border border-outline-variant text-center py-10">
          <span class="material-symbols-outlined text-[48px] text-secondary mb-2">check_circle</span>
          <h4 class="font-title-md text-title-md text-on-surface">Риски не обнаружены</h4>
          <p class="font-body-sm text-body-sm text-on-surface-variant mt-1">Документ выглядит безопасным для подписания.</p>
        </div>
      `;
    } else {
      result.risks.forEach((risk, index) => {
        const isCritical = risk.severity === 'critical';
        const isWarning = risk.severity === 'warning' || risk.severity === 'amber';
        
        let severityClass = 'bg-outline';
        let severityText = 'Инфо';
        let borderHoverClass = 'hover:border-outline';
        let leftBarClass = 'bg-outline';
        
        if (isCritical) {
          severityClass = 'bg-error-container text-on-error-container';
          severityText = 'Критический риск';
          borderHoverClass = 'hover:border-error';
          leftBarClass = 'bg-error';
        } else if (isWarning) {
          severityClass = 'bg-tertiary-container/30 text-on-tertiary-container';
          severityText = 'Предупреждение';
          borderHoverClass = 'hover:border-tertiary';
          leftBarClass = 'bg-tertiary';
        }
        
        riskCardsSection.innerHTML += `
          <div class="bg-surface-container rounded-xl p-md shadow-sm border border-outline-variant ${borderHoverClass} transition-all duration-200 cursor-pointer flex flex-col gap-sm relative overflow-hidden group">
            <div class="absolute top-0 left-0 w-1 h-full ${leftBarClass}"></div>
            <div class="flex justify-between items-start">
              <div class="${severityClass} px-2 py-1 rounded-full font-label-caps text-label-caps uppercase flex items-center gap-1">
                <span class="material-symbols-outlined text-[14px]">${isCritical ? 'warning' : 'info'}</span> ${severityText}
              </div>
              <span class="text-on-surface-variant text-xs font-bold">ПУНКТ ${index + 1}</span>
            </div>
            <h4 class="font-title-md text-title-md text-on-surface">${risk.title || 'Риск в договоре'}</h4>
            <p class="font-body-sm text-body-sm text-on-surface-variant">${risk.description}</p>
            ${risk.recommendation ? `
              <div class="mt-sm bg-secondary-container/10 rounded-lg p-sm border border-secondary-container/20">
                <div class="flex items-center gap-xs font-label-caps text-secondary mb-xs uppercase">
                  <span class="material-symbols-outlined text-[16px]">lightbulb</span> Рекомендация
                </div>
                <p class="font-body-sm text-body-sm text-on-secondary-container">${risk.recommendation}</p>
              </div>
            ` : ''}
          </div>
        `;
      });
    }
  }
}

// Initialization on DOMContentLoaded
document.addEventListener('DOMContentLoaded', async () => {
  if (!checkAuth()) return;
  
  // Make profile avatar clickable or direct link
  const avatarContainer = document.querySelector('header .w-10.h-10');
  if (avatarContainer) {
    avatarContainer.classList.add('cursor-pointer', 'hover:brightness-110');
    avatarContainer.addEventListener('click', () => {
      window.location.href = '/app/profile';
    });
  }
  
  // Initialize landing / default state
  renderUploadState();
  
  // Update header links to use correct routing
  const navLinks = document.querySelectorAll('header nav a');
  navLinks.forEach(link => {
    const text = link.textContent.trim().toLowerCase();
    if (text === 'dashboard') {
      link.href = '/app';
    } else if (text === 'history') {
      link.href = '/app/history';
    } else if (text === 'pricing') {
      link.href = '/app/pricing';
    }
  });

  // Handle any pending file/text upload from landing page
  const pendingName = sessionStorage.getItem('pending_file_name');
  const pendingType = sessionStorage.getItem('pending_file_type');
  const pendingData = sessionStorage.getItem('pending_file_data');
  
  if (pendingName && pendingData) {
    sessionStorage.removeItem('pending_file_name');
    sessionStorage.removeItem('pending_file_type');
    sessionStorage.removeItem('pending_file_data');
    
    try {
      const res = await fetch(pendingData);
      const blob = await res.blob();
      const file = new File([blob], pendingName, { type: pendingType || 'text/plain' });
      handleFileSelect(file);
    } catch (e) {
      console.error('Failed to restore pending file upload:', e);
    }
  }
});
