/**
 * DogovorAI Frontend — Main Application Logic
 * Загрузка файлов, отправка на API, отображение результатов юридического анализа.
 */

// ============================================================
// CONSTANTS
// ============================================================
const API_BASE = window.location.origin;
const API_ENDPOINT = `${API_BASE}/api/analyze`;

/** Текст ошибки из тела FastAPI ({ detail: string | array }) */
function formatApiDetail(detail) {
    if (detail == null) return '';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail.map((e) => (e && e.msg) ? e.msg : JSON.stringify(e)).join(' ');
    }
    return String(detail);
}

// ============================================================
// STATE
// ============================================================
let selectedFile = null;

// ============================================================
// DOM ELEMENTS
// ============================================================
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const filePreviewIcon = document.getElementById('filePreviewIcon');
const removeFileBtn = document.getElementById('removeFile');
const analyzeBtn = document.getElementById('analyzeBtn');
const progressContainer = document.getElementById('progressContainer');
const progressStep = document.getElementById('progressStep');
const resultsSection = document.getElementById('resultsSection');
const uploadCard = document.getElementById('uploadCard');
const errorToast = document.getElementById('errorToast');
const toastMessage = document.getElementById('toastMessage');

// Expose selectedFile state globally so inline scripts can check it
window._appHasFile = function() { return selectedFile !== null; };

// ============================================================
// FILE HANDLING
// ============================================================

// Клик по дропзоне — открываем выбор файла
// Гард от двойного открытия: флаг защищает от рекурсиĐ
// (возникал, когда fileInput был внутри dropZone)
let _clickGuard = false;
dropZone.addEventListener('click', (e) => {
    if (!isAuthenticated()) { requireAuth(); return; }
    if (_clickGuard) return;
    _clickGuard = true;
    fileInput.click();
    // сбрасываем флаг после короткой задержки (браузер успевает обработать один вызов)
    setTimeout(() => { _clickGuard = false; }, 500);
});

// Выбор файла через инпут
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
    }
    // НЕ сбрасываем fileInput.value здесь — это ломало updateAnalyzeBtn(),
    // который проверял fileInput.files.length === 0.
    // Сброс происходит только в resetFileSelection().
});

// Drag & Drop
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', (e) => {
    if (!dropZone.contains(e.relatedTarget)) {
        dropZone.classList.remove('dragover');
    }
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (!isAuthenticated()) { requireAuth(); return; }
    if (e.dataTransfer.files.length > 0) {
        handleFileSelect(e.dataTransfer.files[0]);
    }
});

// Удаление выбранного файла
removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetFileSelection();
});

/**
 * Обработка выбранного файла: валидация, показ preview.
 * @param {File} file
 */
function handleFileSelect(file) {
    const ALLOWED_TYPES = [
        'application/pdf', 
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'image/jpeg', 
        'image/jpg', 
        'image/png',
        'text/plain'
    ];

    const ALLOWED_EXTS = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.txt'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!ALLOWED_TYPES.includes(file.type) && !ALLOWED_EXTS.includes(ext)) {
        showError('Неподдерживаемый формат. Загрузите PDF, DOCX, TXT, JPG или PNG.');
        return;
    }

    const MAX_SIZE = 20 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
        showError(`Файл слишком большой: ${formatFileSize(file.size)}. Максимум: 20 МБ.`);
        return;
    }

    selectedFile = file;

    // Показываем preview
    dropZone.style.display = 'none';
    filePreview.style.display = 'flex';
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    filePreviewIcon.textContent = getFileIcon(file.type, ext);

    // Активируем кнопку анализа
    analyzeBtn.disabled = false;

    // Синхронизируем состояние для inline updateAnalyzeBtn()
    if (typeof updateAnalyzeBtn === 'function') updateAnalyzeBtn();
}

/**
 * Сброс выбора файла — возврат к дропзоне.
 */
function resetFileSelection() {
    selectedFile = null;
    fileInput.value = '';
    dropZone.style.display = 'block';
    filePreview.style.display = 'none';
    analyzeBtn.disabled = true;
}

// ============================================================
// ANALYSIS
// ============================================================

analyzeBtn.addEventListener('click', (e) => safeSubmit(startAnalysis, e));

/**
 * Запуск анализа: отправка файла на API и обработка ответа.
 */
async function startAnalysis() {
    if (!isAuthenticated()) { requireAuth(); return; }

    const tab = typeof activeTab !== 'undefined' ? activeTab : 'file';
    let fileToUpload = null;

    if (tab === 'file') {
        if (!selectedFile) return;
        fileToUpload = selectedFile;
    } else if (tab === 'text') {
        const textVal = (document.getElementById('textInput') || {}).value || '';
        if (textVal.trim().length < 100) {
            showError('Введите текст договора (минимум 100 символов).');
            return;
        }
        fileToUpload = new File([textVal], 'text_input.txt', { type: 'text/plain' });
    } else if (tab === 'url') {
        const urlVal = (document.getElementById('urlInput') || {}).value || '';
        if (!urlVal.startsWith('http')) {
            showError('Введите корректную ссылку.');
            return;
        }
        try {
            const fetchResp = await fetch(urlVal);
            if (!fetchResp.ok) throw new Error('Не удалось скачать файл по ссылке.');
            const blob = await fetchResp.blob();
            const fileNameFromUrl = urlVal.split('/').pop() || 'document.pdf';
            fileToUpload = new File([blob], fileNameFromUrl, { type: blob.type });
        } catch (e) {
            showError('Не удалось загрузить документ по ссылке. Убедитесь, что ссылка является прямой и сервер разрешает CORS-запросы.');
            return;
        }
    }

    if (!fileToUpload) return;

    // GA4: трекинг начала анализа
    if (typeof trackEvent === 'function') {
      trackEvent('feature_usage', { feature_name: 'contract_analysis', input_type: tab });
    }

    analyzeBtn.disabled = true;
    analyzeBtn.classList.add('loading');
    analyzeBtn.setAttribute('data-was-loading', 'true');

    // Скрываем форму, показываем прогресс
    uploadCard.style.display = 'none';
    progressContainer.style.display = 'block';
    resultsSection.style.display = 'none';

    // Анимируем шаги прогресса
    animateProgress();

    try {
        const formData = new FormData();
        formData.append('file', fileToUpload);
        formData.append('filename', fileToUpload.name);

        const headers = (typeof getAuthHeaders === 'function') ? getAuthHeaders() : {};

        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            headers: headers,
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));

            // Handle 402 — limit exceeded → show paywall
            if (response.status === 402 && errorData.detail && errorData.detail.error === 'limit_exceeded') {
                progressContainer.style.display = 'none';
                uploadCard.style.display = 'block';
                if (typeof handleLimitError === 'function') {
                    handleLimitError(errorData.detail);
                }
                return;
            }

            const msg = formatApiDetail(errorData.detail) || `Ошибка сервера: ${response.status}`;
            throw new Error(msg);
        }

        const data = await response.json();
        displayResults(data);

        // GA4: трекинг успешного анализа
        if (typeof trackEvent === 'function') {
          trackEvent('feature_usage', { feature_name: 'contract_analysis_success' });
        }

        // Refresh usage bar after successful analysis
        if (typeof loadUsageInfo === 'function') loadUsageInfo();

    } catch (error) {
        console.error('Analysis error:', error);
        progressContainer.style.display = 'none';
        uploadCard.style.display = 'block';

        // GA4: трекинг ошибки анализа
        if (typeof trackError === 'function') {
          trackError('analysis_failed', error.message, 'index');
        }

        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showError('Не удалось подключиться к серверу. Убедитесь что сервер запущен.');
        } else {
            showError(error.message || 'Произошла ошибка при анализе договора.');
        }
    }
}

/**
 * Анимация шагов прогресса.
 */
function animateProgress() {
    const steps = ['step1', 'step2', 'step3'];
    const messages = [
        'Извлечение текста из документа...',
        'AI анализирует юридические риски...',
        'Сопоставление с законодательством РК...'
    ];

    steps.forEach(id => {
        document.getElementById(id).classList.remove('active', 'done');
    });

    let currentStep = 0;

    function activateStep(index) {
        if (index > 0) {
            document.getElementById(steps[index - 1]).classList.remove('active');
            document.getElementById(steps[index - 1]).classList.add('done');
        }
        if (index < steps.length) {
            document.getElementById(steps[index]).classList.add('active');
            progressStep.textContent = messages[index];
        }
    }

    activateStep(0);
    const timer1 = setTimeout(() => activateStep(1), 2000);
    const timer2 = setTimeout(() => activateStep(2), 5000);
}

// ============================================================
// RESULTS DISPLAY
// ============================================================

/**
 * Отображение результатов анализа.
 * @param {Object} data - Ответ от API
 */
function displayResults(data) {
    progressContainer.style.display = 'none';
    resultsSection.style.display = 'block';

    const fileInfo = data.file_info;
    const analysis = data.analysis;

    // Файл информация
    document.getElementById('resultsFilename').textContent =
        `${fileInfo.filename} · ${formatFileSize(fileInfo.char_count, true)}`;

    // Тип документа
    document.getElementById('docTypeBadge').textContent = analysis.document_type;

    // Резюме
    document.getElementById('summaryText').textContent = analysis.summary || 'Резюме недоступно.';

    // Уровень риска (вердикт)
    const verdictEl = document.getElementById('resultsVerdict');
    const verdictIcon = document.getElementById('verdictIcon');
    const verdictText = document.getElementById('verdictText');

    if (analysis.overall_risk_level === 'high') {
        verdictEl.className = 'flex items-center gap-2 px-3 py-1.5 rounded-full border bg-error-container/30 border-error text-error';
        verdictIcon.textContent = '🔴';
        verdictText.textContent = 'Высокий риск';
    } else if (analysis.overall_risk_level === 'medium') {
        verdictEl.className = 'flex items-center gap-2 px-3 py-1.5 rounded-full border bg-tertiary-fixed/30 border-tertiary text-amber-600';
        verdictIcon.textContent = '🟡';
        verdictText.textContent = 'Умеренный риск';
    } else {
        verdictEl.className = 'flex items-center gap-2 px-3 py-1.5 rounded-full border bg-secondary-container/20 border-secondary text-secondary';
        verdictIcon.textContent = '🟢';
        verdictText.textContent = 'Низкий риск';
    }

    // Статистика рисков
    const risks = analysis.risks || [];
    const highRisks = risks.filter(r => r.risk_level === 'high');
    const mediumRisks = risks.filter(r => r.risk_level === 'medium');
    const lowRisks = risks.filter(r => r.risk_level === 'low');

    document.getElementById('highCount').textContent = highRisks.length;
    document.getElementById('mediumCount').textContent = mediumRisks.length;
    document.getElementById('lowCount').textContent = lowRisks.length;

    // Список рисков (сначала в fallback рендерим, потом переносим в сплит-скрин)
    const risksListFb = document.getElementById('risksListFallback');
    risksListFb.innerHTML = '';

    if (risks.length === 0) {
        risksListFb.innerHTML = `
            <div class="bg-surface-container-lowest rounded-[12px] p-6 text-center border border-outline-variant">
                <p class="text-secondary font-bold text-lg flex items-center justify-center gap-2">
                    <span class="material-symbols-outlined">check_circle</span> Рисков не обнаружено
                </p>
            </div>
        `;
    } else {
        // Сначала критические, потом умеренные, потом низкие
        [...highRisks, ...mediumRisks, ...lowRisks].forEach((risk, i) => {
            risksListFb.appendChild(createRiskCard(risk, i + 1));
        });
    }

    // Рекомендации
    const recommendations = analysis.recommendations || [];
    const recCard = document.getElementById('recommendationsCard');
    const recList = document.getElementById('recList');

    if (recommendations.length > 0) {
        recCard.style.display = 'block';
        recList.innerHTML = recommendations
            .map(rec => `<li>${escapeHtml(rec)}</li>`)
            .join('');
    }

    // Обновляем прогресс-бар и сплит-скрин
    if (typeof updateRiskProgressBar === 'function') {
        updateRiskProgressBar(highRisks.length, mediumRisks.length, lowRisks.length);
    }
    if (typeof showSplitScreen === 'function') {
        showSplitScreen(fileInfo.extracted_text);
    }

    // Плавная прокрутка к результатам
    setTimeout(() => {
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

/**
 * Создаёт DOM-элемент карточки риска.
 * @param {Object} risk
 * @param {number} index
 * @returns {HTMLElement}
 */
function createRiskCard(risk, index) {
    const card = document.createElement('div');
    card.className = `risk-card risk-${risk.risk_level} cursor-pointer transition-all duration-200 hover:shadow-md`;
    card.style.animationDelay = `${index * 0.07}s`;

    let badgeClass = 'badge-low';
    let levelLabel = 'Низкий риск';

    if (risk.risk_level === 'high') {
        badgeClass = 'badge-high';
        levelLabel = 'Критический риск';
    } else if (risk.risk_level === 'medium') {
        badgeClass = 'badge-medium';
        levelLabel = 'Умеренный риск';
    }

    let html = `
        <div class="risk-card-header">
            <span class="risk-level-badge ${badgeClass}">${levelLabel}</span>
            <span class="risk-category">${escapeHtml(risk.category)}</span>
        </div>
        <div class="risk-description">
            ${escapeHtml(risk.description)}
        </div>
    `;

    if (risk.original_clause) {
        html += `
            <div class="risk-original-clause">
                ${escapeHtml(risk.original_clause)}
            </div>
        `;
    }

    if (risk.recommendation || risk.law_reference) {
        html += `<div class="risk-footer">`;
        
        if (risk.recommendation) {
            html += `
                <div class="risk-recommendation">
                    ${escapeHtml(risk.recommendation)}
                </div>
            `;
        }

        if (risk.law_reference) {
            const title = risk.law_description ? `title="${escapeHtml(risk.law_description)}"` : '';
            html += `
                <div class="risk-law" ${title}>
                    Закон: <span class="risk-law-ref">${escapeHtml(risk.law_reference)}</span>
                    ${risk.law_description ? `<span style="font-size: 10px; opacity: 0.6; margin-left: 4px;">— подробнее</span>` : ''}
                </div>
            `;
        }
        
        html += `</div>`;
    }

    card.innerHTML = html;

    // Click handler for law tooltip detail
    if (risk.law_reference && risk.law_description) {
        const lawEl = card.querySelector('.risk-law-ref');
        if (lawEl) {
            lawEl.parentElement.addEventListener('click', (e) => {
                e.stopPropagation();
                alert(`${risk.law_reference}\n\n${risk.law_description}`);
            });
        }
    }

    return card;
}

// ============================================================
// NEW ANALYSIS
// ============================================================

document.getElementById('newAnalysisBtn').addEventListener('click', () => {
    resultsSection.style.display = 'none';
    uploadCard.style.display = 'block';
    resetFileSelection();
    document.getElementById('upload').scrollIntoView({ behavior: 'smooth' });
});

// ============================================================
// ERROR HANDLING
// ============================================================

/**
 * Показывает тост с сообщением об ошибке.
 * @param {string} message
 */
function showError(message) {
    toastMessage.textContent = message;
    errorToast.style.display = 'flex';
    setTimeout(() => closeToast(), 7000);
}

function closeToast() {
    errorToast.style.display = 'none';
}

// ============================================================
// UTILITIES
// ============================================================

/**
 * Форматирует размер файла в человекочитаемый вид.
 * @param {number} bytes
 * @param {boolean} isChars - true если это символы (не байты)
 * @returns {string}
 */
function formatFileSize(bytes, isChars = false) {
    if (isChars) return `${bytes.toLocaleString()} символов`;
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
}

/**
 * Выбирает иконку файла по MIME-типу или расширению.
 * @param {string} mimeType
 * @param {string} ext
 * @returns {string}
 */
function getFileIcon(mimeType, ext) {
    if (mimeType === 'application/pdf' || ext === '.pdf') return '📕';
    if (mimeType?.includes('word') || ['.doc', '.docx'].includes(ext)) return '📘';
    if (mimeType?.startsWith('image/') || ['.jpg', '.jpeg', '.png'].includes(ext)) return '🖼️';
    return '📄';
}

/**
 * Экранирует HTML-специальные символы.
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}
