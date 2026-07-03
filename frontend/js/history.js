// frontend/js/history.js

let currentPage = 1;
const PAGE_LIMIT = 10;
let queryDebounceTimer = null;

// Bridge: auth-guard.js exports getAuthHeaders(), this file uses authHeaders()
function authHeaders() {
    if (typeof getAuthHeaders === 'function') return getAuthHeaders();
    const token = localStorage.getItem('token');
    return token ? { 'Authorization': 'Bearer ' + token } : {};
}

document.addEventListener('DOMContentLoaded', () => {
    fetchHistory();
    setupEventListeners();
});

function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    const riskFilter = document.getElementById('riskFilter');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');

    searchInput.addEventListener('input', () => {
        clearTimeout(queryDebounceTimer);
        // Add fake debounce UX for search visually, though filtering is done strictly by backend for pagination
        // Currently exact name search is not in backend yet, so we will filter visually or just let it be. 
        // For production, we should add name search param. 
        // We'll perform frontend filtering on fetched results as a fast UX approach.
        queryDebounceTimer = setTimeout(() => {
            renderTable();
        }, 300);
    });

    statusFilter.addEventListener('change', () => {
        currentPage = 1;
        fetchHistory();
    });

    riskFilter.addEventListener('change', () => {
        currentPage = 1;
        fetchHistory();
    });

    prevBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            fetchHistory();
        }
    });

    nextBtn.addEventListener('click', () => {
        currentPage++;
        fetchHistory();
    });
}

function getRiskBadge(level) {
    if (!level || level === 'n/a') return `<span style="color:var(--text-muted)">—</span>`;
    
    if (level.toLowerCase() === 'high' || level.toLowerCase() === 'критический') {
        return `<span class="badge-status" style="border:1px solid rgba(239, 68, 68, 0.4); color:#ef4444;">Критический</span>`;
    }
    if (level.toLowerCase() === 'medium' || level.toLowerCase() === 'умеренный') {
        return `<span class="badge-status" style="border:1px solid rgba(245, 158, 11, 0.4); color:#f59e0b;">Умеренный</span>`;
    }
    return `<span class="badge-status" style="border:1px solid rgba(16, 185, 129, 0.4); color:#10b981;">Низкий</span>`;
}

function getStatusBadge(statusStr) {
    if (statusStr === 'Успешно') return `<span class="badge-status status-success">Успешно</span>`;
    if (statusStr === 'Ошибка') return `<span class="badge-status status-error">Ошибка</span>`;
    return `<span class="badge-status status-pending">В очереди</span>`;
}

let currentData = [];

async function fetchHistory() {
    const tableBody = document.getElementById('historyTableBody');
    const loadingDiv = document.getElementById('historyLoading');
    const emptyState = document.getElementById('historyEmptyState');
    const table = document.getElementById('historyTable');
    const pagination = document.getElementById('historyPagination');

    const statusFilter = document.getElementById('statusFilter').value;
    const riskFilter = document.getElementById('riskFilter').value;

    table.style.display = 'none';
    emptyState.style.display = 'none';
    pagination.style.display = 'none';
    loadingDiv.style.display = 'block';

    try {
        let url = `/api/history?page=${currentPage}&limit=${PAGE_LIMIT}`;
        if (statusFilter) url += `&status=${statusFilter}`;
        if (riskFilter) url += `&risk_level=${riskFilter}`;

        const res = await fetch(url, {
            headers: authHeaders(),
            cache: 'no-store'
        });

        if (res.status === 401) {
            console.warn('History API: 401 Unauthorized');
            // Don't clear session — let user stay logged in on other pages
            throw new Error("Не удалось загрузить историю. Попробуйте перелогиниться.");
        }

        if (!res.ok) throw new Error("Failed to load history");

        const data = await res.json();
        currentData = data.items || [];
        
        document.getElementById('totalFilesCount').textContent = data.total;
        
        if (currentData.length === 0 && Object.keys(data).length > 0 && currentPage === 1 && !statusFilter && !riskFilter) {
            loadingDiv.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }

        loadingDiv.style.display = 'none';
        table.style.display = 'block';
        
        if (data.total_pages > 1 || currentPage > 1) {
            pagination.style.display = 'flex';
            document.getElementById('currentPageLabel').textContent = data.page;
            document.getElementById('totalPagesLabel').textContent = data.total_pages;
            
            document.getElementById('prevPageBtn').disabled = data.page <= 1;
            document.getElementById('nextPageBtn').disabled = data.page >= data.total_pages;
        }

        renderTable();

    } catch (err) {
        console.error(err);
        loadingDiv.textContent = 'Ошибка загрузки истории. Повторите попытку.';
    }
}

function renderTable() {
    const tableBody = document.getElementById('historyTableBody');
    tableBody.innerHTML = '';

    const searchTerm = document.getElementById('searchInput').value.toLowerCase().trim();

    let displayData = currentData;
    if (searchTerm) {
        displayData = currentData.filter(item => item.filename.toLowerCase().includes(searchTerm));
    }

    if (displayData.length === 0) {
        tableBody.innerHTML = '<div class="p-8 text-center text-on-surface-variant font-body-md">Ничего не найдено</div>';
        return;
    }

    // Escape HTML helper
    const escHtml = (str) => {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(str));
        return d.innerHTML;
    };

    displayData.forEach(item => {
        const tr = document.createElement('div');
        tr.className = "grid grid-cols-1 md:grid-cols-12 gap-4 px-6 py-5 border-b border-outline-variant items-center hover:bg-surface-container-high/50 transition-colors group";
        
        const dateObj = new Date(item.created_at);
        const dateStr = dateObj.toLocaleDateString('ru-RU');

        const fType = (item.file_type || '').toUpperCase();
        
        let icon = 'description';
        let iconBg = 'bg-surface-container-high text-primary';
        let riskBadge = '';
        
        if (item.analysis_status === 'Ошибка') {
            icon = 'cancel';
            iconBg = 'bg-error-container/20 text-error flex items-center justify-center shrink-0 border border-error/30';
            riskBadge = `
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-error-container/20 text-error font-label-caps border border-error/30">
                    <span class="w-1.5 h-1.5 rounded-full bg-error"></span>
                    Ошибка
                </span>
            `;
        } else if (item.risk_level === 'high' || item.risk_level === 'критический') {
            icon = 'error';
            iconBg = 'bg-error-container/20 text-error flex items-center justify-center shrink-0 border border-error/30';
            riskBadge = `
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-error-container/20 text-error font-label-caps border border-error/30">
                    <span class="w-1.5 h-1.5 rounded-full bg-error"></span>
                    High Risk
                </span>
            `;
        } else if (item.risk_level === 'medium' || item.risk_level === 'умеренный') {
            icon = 'warning';
            iconBg = 'bg-tertiary-container/20 text-tertiary flex items-center justify-center shrink-0 border border-tertiary/30';
            riskBadge = `
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-tertiary-container/20 text-tertiary font-label-caps border border-tertiary/30">
                    <span class="w-1.5 h-1.5 rounded-full bg-tertiary"></span>
                    Medium Risk
                </span>
            `;
        } else {
            icon = 'check_circle';
            iconBg = 'bg-secondary-container/20 text-secondary flex items-center justify-center shrink-0 border border-secondary/30';
            riskBadge = `
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-secondary-container/20 text-secondary font-label-caps border border-secondary/30">
                    <span class="w-1.5 h-1.5 rounded-full bg-secondary"></span>
                    Safe
                </span>
            `;
        }

        tr.innerHTML = `
            <div class="col-span-1 md:col-span-5 flex items-start gap-3 min-w-0">
                <div class="mt-1 w-8 h-8 rounded ${iconBg}">
                    <span class="material-symbols-outlined text-[20px]">${icon}</span>
                </div>
                <div class="min-w-0">
                    <h3 class="font-title-md text-sm font-bold text-on-surface mb-1 truncate" title="${escHtml(item.filename)}">${escHtml(item.filename)}</h3>
                    <div class="flex items-center gap-2 font-body-sm text-xs text-on-surface-variant">
                        <span class="material-symbols-outlined text-[16px]">description</span>
                        <span>${fType} • ${item.risks_count} рисков</span>
                    </div>
                </div>
            </div>
            <div class="col-span-1 md:col-span-2 font-body-sm text-xs text-on-surface-variant flex items-center gap-2">
                <span class="md:hidden font-label-caps text-xs text-outline">Дата:</span>
                ${dateStr}
            </div>
            <div class="col-span-1 md:col-span-2 flex items-center gap-2">
                <span class="md:hidden font-label-caps text-xs text-outline">Статус:</span>
                ${riskBadge}
            </div>
            <div class="col-span-1 md:col-span-3 flex items-center justify-start md:justify-end gap-2 mt-2 md:mt-0 opacity-100 md:opacity-0 group-hover:opacity-100 transition-opacity">
                <button class="view-btn px-3 py-1.5 text-primary font-label-caps rounded border border-primary hover:bg-primary-container hover:text-on-primary-container transition-colors text-xs">
                    View Report
                </button>
                <button class="download-btn p-1.5 text-on-surface-variant hover:text-primary hover:bg-surface-container-highest rounded transition-colors" title="Download">
                    <span class="material-symbols-outlined text-[20px]">download</span>
                </button>
                <button class="delete-btn p-1.5 text-on-surface-variant hover:text-error hover:bg-error-container/20 rounded transition-colors" title="Delete">
                    <span class="material-symbols-outlined text-[20px]">delete</span>
                </button>
            </div>
        `;

        // Action Handlers
        const viewBtn = tr.querySelector('.view-btn');
        if (viewBtn) {
            viewBtn.addEventListener('click', () => {
                window.location.href = '/app?document_id=' + item.document_id;
            });
        }

        const downloadBtn = tr.querySelector('.download-btn');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => {
                alert(`Скачивание отчета: ${item.filename}`);
            });
        }

        const deleteBtn = tr.querySelector('.delete-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Вы уверены, что хотите удалить документ "${item.filename}"?`)) {
                    try {
                        const res = await fetch(`/api/history/${item.document_id}`, {
                            method: 'DELETE',
                            headers: authHeaders()
                        });
                        if (res.ok) {
                            fetchHistory();
                        } else {
                            const errData = await res.json();
                            alert(errData.detail || 'Не удалось удалить документ.');
                        }
                    } catch (err) {
                        console.error('Delete error:', err);
                        alert('Произошла ошибка при удалении документа.');
                    }
                }
            });
        }

        tableBody.appendChild(tr);
    });
}
