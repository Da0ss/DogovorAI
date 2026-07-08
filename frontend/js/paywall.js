/**
 * DogovorAI — Paywall & Usage Limits Logic
 * Shared across index.html and contracts.html.
 *
 * Requires DOM elements:
 *  - #usageBarContainer, #usageUsed, #usageLimit, #usageFill,
 *    #usagePlanBadge, #usageUpgradeWrap, #usageResetDate (optional)
 *  - #paywallModal, #paywallClose, #paywallSkip,
 *    #paywallUsed, #paywallLimit, #paywallMessage
 *  - #analyzeBtn OR #startAnalyzeBtn (upload button to lock)
 *
 * Expects helpers: isAuthenticated(), getAuthHeaders()
 */

// ─── State ───────────────────────────────────────────────────────────────────
window._usageData = null;

// ─── Load & refresh usage info ───────────────────────────────────────────────

/**
 * Fetch current usage from the backend and update all UI elements.
 * Called on page load and after every successful analysis.
 */
async function loadUsageInfo() {
    if (typeof isAuthenticated !== 'function' || !isAuthenticated()) {
        const bar = document.getElementById('usageBarContainer');
        if (bar) bar.style.display = 'none';
        return;
    }

    try {
        const headers = typeof getAuthHeaders === 'function' ? getAuthHeaders() : {};
        const resp = await fetch('/api/usage/me', { headers });
        if (!resp.ok) return;

        const data = await resp.json();
        window._usageData = data;
        updateUsageBar(data);
        _updateAnalyzeButton(data);
    } catch (e) {
        console.warn('Failed to load usage info:', e);
    }
}

// ─── Update usage bar UI ─────────────────────────────────────────────────────

/**
 * Render the usage bar + reset date from server data.
 * @param {Object} data — response from /api/usage/me
 */
function updateUsageBar(data) {
    const container = document.getElementById('usageBarContainer');
    if (!container) return;

    const used     = data.used  ?? 0;
    const limit    = data.limit;           // null = unlimited
    const plan     = data.plan  || 'basic';
    const planName = data.plan_name || plan.charAt(0).toUpperCase() + plan.slice(1);
    const resetAt  = data.reset_at || null;
    const exceeded = data.exceeded || (limit !== null && used >= limit);

    // Hide bar for unlimited plans
    if (limit === null || limit === undefined) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';

    // Text counters
    const usedEl    = document.getElementById('usageUsed');
    const limitEl   = document.getElementById('usageLimit');
    const planBadge = document.getElementById('usagePlanBadge');
    const resetEl   = document.getElementById('usageResetDate');

    if (usedEl)    usedEl.textContent  = used;
    if (limitEl)   limitEl.textContent = limit;
    if (planBadge) planBadge.textContent = planName;

    // Reset date
    if (resetEl && resetAt) {
        try {
            const d = new Date(resetAt);
            resetEl.textContent = `Сброс: ${d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}`;
            resetEl.style.display = 'inline';
        } catch (_) { resetEl.style.display = 'none'; }
    } else if (resetEl) {
        resetEl.style.display = 'none';
    }

    // Progress bar
    const fill = document.getElementById('usageFill');
    if (fill) {
        const pct = Math.min(Math.round((used / limit) * 100), 100);
        fill.style.width = pct + '%';
        fill.classList.remove('usage-warning', 'usage-full');
        if (pct >= 100)      fill.classList.add('usage-full');
        else if (pct >= 66)  fill.classList.add('usage-warning');
    }

    // Upgrade button
    const upgradeWrap = document.getElementById('usageUpgradeWrap');
    if (upgradeWrap) {
        upgradeWrap.style.display = (plan === 'basic' || exceeded) ? 'block' : 'none';
    }

    // Limit-exceeded banner (inline, above upload zone)
    _renderLimitBanner(used, limit, resetAt, exceeded);
}

// ─── Inline limit-exceeded banner ────────────────────────────────────────────

function _renderLimitBanner(used, limit, resetAt, exceeded) {
    const bannerId = 'usageLimitBanner';

    // Remove old banner
    const old = document.getElementById(bannerId);
    if (old) old.remove();

    if (!exceeded) return;

    // Find insertion point (above uploadCard or analyzeDropZone)
    const anchor = document.getElementById('uploadCard')
                || document.getElementById('analyzeDropZone')
                || document.getElementById('usageBarContainer');
    if (!anchor) return;

    let resetText = '';
    if (resetAt) {
        try {
            const d = new Date(resetAt);
            resetText = `Лимит обновится ${d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}.`;
        } catch (_) {}
    }

    const banner = document.createElement('div');
    banner.id = bannerId;
    banner.innerHTML = `
      <div style="
        margin: 16px 0;
        padding: 16px 20px;
        background: linear-gradient(135deg, rgba(239,68,68,0.12), rgba(249,115,22,0.08));
        border: 1px solid rgba(239,68,68,0.35);
        border-radius: 14px;
        display: flex;
        align-items: center;
        gap: 14px;
        font-family: 'Inter', sans-serif;
      ">
        <span style="font-size:1.4rem;flex-shrink:0;">🚫</span>
        <div style="flex:1">
          <div style="font-weight:700;color:#fca5a5;font-size:0.9rem;margin-bottom:3px;">
            Лимит анализов исчерпан (${used}/${limit})
          </div>
          <div style="font-size:0.8rem;color:rgba(252,165,165,0.75);">
            ${resetText} Перейдите на Pro или Max для продолжения.
          </div>
        </div>
        <a href="/app/profile#subscription"
           style="
             flex-shrink:0;
             padding:8px 16px;
             background:linear-gradient(135deg,#ef4444,#f97316);
             border-radius:10px;
             color:white;
             font-size:0.8rem;
             font-weight:700;
             text-decoration:none;
             transition:opacity 0.2s;
           "
           onmouseover="this.style.opacity='.85'"
           onmouseout="this.style.opacity='1'">
          Upgrade →
        </a>
      </div>`;

    anchor.parentNode.insertBefore(banner, anchor);
}

// ─── Lock / unlock analyze button ────────────────────────────────────────────

function _updateAnalyzeButton(data) {
    const exceeded = data.exceeded || (data.limit !== null && data.used >= data.limit);
    const btns = ['analyzeBtn', 'startAnalyzeBtn'].map(id => document.getElementById(id)).filter(Boolean);

    btns.forEach(btn => {
        if (exceeded) {
            btn.disabled = true;
            if (!btn.dataset.originalTitle) btn.dataset.originalTitle = btn.title || '';
            btn.title = `Лимит исчерпан (${data.used}/${data.limit}). Оформите подписку.`;
            btn.style.opacity = '0.45';
            btn.style.cursor  = 'not-allowed';
        } else {
            btn.disabled = false;
            btn.title    = btn.dataset.originalTitle || '';
            btn.style.opacity = '';
            btn.style.cursor  = '';
        }
    });
}

// ─── Paywall modal ────────────────────────────────────────────────────────────

/**
 * Show the paywall modal with usage stats.
 */
function showPaywall(used, limit, message, resetAt) {
    const modal = document.getElementById('paywallModal');
    if (!modal) return;

    const usedEl  = document.getElementById('paywallUsed');
    const limitEl = document.getElementById('paywallLimit');
    const msgEl   = document.getElementById('paywallMessage');
    const rstEl   = document.getElementById('paywallReset');

    if (usedEl)  usedEl.textContent  = used  ?? 0;
    if (limitEl) limitEl.textContent = limit ?? 3;
    if (msgEl && message) msgEl.textContent = message;

    if (rstEl && resetAt) {
        try {
            const d = new Date(resetAt);
            rstEl.textContent = `Лимит обновится ${d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}`;
            rstEl.style.display = 'block';
        } catch (_) { rstEl.style.display = 'none'; }
    } else if (rstEl) {
        rstEl.style.display = 'none';
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // GA4: трекинг начала платежного флоу
    if (typeof trackEvent === 'function') {
      trackEvent('payment_started', {
        transaction_id: 'paywall_' + Date.now(),
        value: 0,
        currency: 'KZT'
      });
    }
}

function hidePaywall() {
    const modal = document.getElementById('paywallModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

/**
 * Handle 402 limit_exceeded error from analysis API.
 */
function handleLimitError(detail) {
    const used    = detail.used    ?? 0;
    const limit   = detail.limit   ?? 3;
    const resetAt = detail.reset_at || (window._usageData && window._usageData.reset_at) || null;
    const message = detail.message ||
        'Лимит бесплатных анализов исчерпан. Приобретите подписку для продолжения.';

    showPaywall(used, limit, message, resetAt);

    updateUsageBar({
        used,
        limit,
        plan:      detail.plan || 'basic',
        plan_name: 'Basic',
        reset_at:  resetAt,
        exceeded:  true,
    });

    _updateAnalyzeButton({ used, limit: limit, exceeded: true });
}

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    loadUsageInfo();

    const closeBtn = document.getElementById('paywallClose');
    const skipBtn  = document.getElementById('paywallSkip');

    if (closeBtn) closeBtn.addEventListener('click', hidePaywall);
    if (skipBtn)  skipBtn.addEventListener('click',  hidePaywall);

    const modal = document.getElementById('paywallModal');
    if (modal) {
        modal.addEventListener('click', e => { if (e.target === modal) hidePaywall(); });
    }

    document.addEventListener('keydown', e => { if (e.key === 'Escape') hidePaywall(); });
});
