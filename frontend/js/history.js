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
        table.style.display = 'table';
        
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
        tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:30px;">Ничего не найдено</td></tr>';
        return;
    }

    displayData.forEach(item => {
        const tr = document.createElement('tr');
        
        const dateObj = new Date(item.created_at);
        const dateStr = dateObj.toLocaleDateString('ru-RU') + ' в ' + dateObj.toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});

        const fType = item.file_type || '';
        let icon = '📄';
        if(fType.includes('pdf')) icon = '📕';
        if(fType.includes('docx') || fType.includes('doc')) icon = '📘';
        if(fType.includes('image') || fType.includes('jpg') || fType.includes('png')) icon = '🖼️';

        tr.innerHTML = `
            <td>
                <div class="doc-name-cell">
                    <div class="doc-icon">${icon}</div>
                    <div class="doc-info">
                        <span class="doc-name" title="${item.filename}">${item.filename}</span>
                        <span class="doc-date">${fType.toUpperCase()} • ${item.risks_count} рисков</span>
                    </div>
                </div>
            </td>
            <td>${dateStr}</td>
            <td>${getStatusBadge(item.analysis_status)}</td>
            <td>${getRiskBadge(item.risk_level)}</td>
            <td class="actions-cell">
                <button class="history-actions-btn" title="Скачать">↓</button>
            </td>
        `;
        // Attach event listener just for show
        const actionBtn = tr.querySelector('.history-actions-btn');
        actionBtn.addEventListener('click', () => {
            alert('Скачивание: ' + item.filename);
        });

        tableBody.appendChild(tr);
    });
}
