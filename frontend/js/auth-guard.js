/**
 * DogovorAI — Auth Guard
 * Централизованный модуль авторизации.
 *
 * Экспортирует глобальные хелперы:
 *  - isAuthenticated()   → boolean
 *  - getAuthHeaders()    → { Authorization: 'Bearer ...' }
 *  - getUser()           → parsed user object | null
 *  - requireAuth()       → редирект на /app/login если не авторизован
 *  - logout()            → очистка сессии + редирект
 *
 * Подключать ПЕРВЫМ скриптом на всех защищённых страницах.
 */

// ─── Хелперы ─────────────────────────────────────────────────────────────────

function isAuthenticated() {
    return !!localStorage.getItem('access_token');
}

function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function getUser() {
    try {
        const raw = localStorage.getItem('user');
        return raw ? JSON.parse(raw) : null;
    } catch (_) {
        return null;
    }
}

// ─── Auth Guard ───────────────────────────────────────────────────────────────

/**
 * Немедленно редиректит на страницу логина если пользователь не вошёл.
 * Сохраняет текущий URL чтобы вернуться после авторизации.
 */
function requireAuth() {
    if (!isAuthenticated()) {
        const returnTo = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.replace(`/app/login?next=${returnTo}`);
    }
}

// ─── Logout ───────────────────────────────────────────────────────────────────

async function logout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST', headers: getAuthHeaders() });
    } catch (_) {}
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    window.location.href = '/app/login';
}

// ─── Навигация: обновить кнопки входа/выхода ─────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    const user = getUser();
    const authed = isAuthenticated();

    // Показываем/скрываем кнопку выхода и имя пользователя в хедере
    const logoutBtns = document.querySelectorAll('[data-action="logout"]');
    logoutBtns.forEach(btn => {
        btn.style.display = authed ? 'inline-flex' : 'none';
        btn.addEventListener('click', logout);
    });

    // Показываем имя в хедере
    const userNames = document.querySelectorAll('[data-user-name]');
    userNames.forEach(el => {
        if (authed && user) {
            el.textContent = user.full_name || user.email || '';
            el.style.display = '';
        } else {
            el.style.display = 'none';
        }
    });
});
