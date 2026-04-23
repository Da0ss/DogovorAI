/**
 * DogovorAI — Paywall & Usage Limits Logic
 * Shared across index.html and contracts.html.
 *
 * Requires:
 *  - DOM elements: #usageBarContainer, #usageUsed, #usageLimit, #usageFill,
 *    #usagePlanBadge, #usageUpgradeWrap
 *  - DOM elements: #paywallModal, #paywallClose, #paywallSkip,
 *    #paywallUsed, #paywallLimit, #paywallMessage
 *  - Functions: isAuthenticated(), getAuthHeaders() — defined in page <script>
 */

// ============================================================
// PAYWALL STATE
// ============================================================
window._usageData = null;

// ============================================================
// LOAD USAGE INFO
// ============================================================

/**
 * Fetch current usage from the backend and update the UI bar.
 * Called on page load and after each analysis.
 */
async function loadUsageInfo() {
    // Only show usage bar for authenticated users
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
    } catch (e) {
        console.warn('Failed to load usage info:', e);
    }
}

/**
 * Update the usage bar UI with data from the server.
 */
function updateUsageBar(data) {
    const container = document.getElementById('usageBarContainer');
    if (!container) return;

    const used = data.used || 0;
    const limit = data.limit;
    const plan = data.plan || 'basic';
    const planName = data.plan_name || plan.charAt(0).toUpperCase() + plan.slice(1);

    // Show usage bar only for plans with limits
    if (limit === null || limit === undefined) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';

    // Update text
    const usedEl = document.getElementById('usageUsed');
    const limitEl = document.getElementById('usageLimit');
    const planBadge = document.getElementById('usagePlanBadge');

    if (usedEl) usedEl.textContent = used;
    if (limitEl) limitEl.textContent = limit;
    if (planBadge) planBadge.textContent = planName;

    // Update progress bar
    const fill = document.getElementById('usageFill');
    if (fill) {
        const pct = Math.min((used / limit) * 100, 100);
        fill.style.width = pct + '%';

        // Color coding
        fill.classList.remove('usage-warning', 'usage-full');
        if (pct >= 100) fill.classList.add('usage-full');
        else if (pct >= 66) fill.classList.add('usage-warning');
    }

    // Show upgrade button for basic plan
    const upgradeWrap = document.getElementById('usageUpgradeWrap');
    if (upgradeWrap) {
        upgradeWrap.style.display = (plan === 'basic') ? 'block' : 'none';
    }
}

// ============================================================
// PAYWALL MODAL
// ============================================================

/**
 * Show the paywall modal with usage stats.
 * @param {number} used - analyses used
 * @param {number} limit - plan limit
 * @param {string} message - optional custom message
 */
function showPaywall(used, limit, message) {
    const modal = document.getElementById('paywallModal');
    if (!modal) return;

    const usedEl = document.getElementById('paywallUsed');
    const limitEl = document.getElementById('paywallLimit');
    const msgEl = document.getElementById('paywallMessage');

    if (usedEl) usedEl.textContent = used || 0;
    if (limitEl) limitEl.textContent = limit || 3;
    if (msgEl && message) msgEl.textContent = message;

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

/**
 * Hide the paywall modal.
 */
function hidePaywall() {
    const modal = document.getElementById('paywallModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

/**
 * Handle a 402 error from the analysis API.
 * Shows the paywall modal with usage stats.
 * @param {Object} detail — error detail from API
 */
function handleLimitError(detail) {
    const used = detail.used || 0;
    const limit = detail.limit || 3;
    const message = detail.message ||
        'Лимит бесплатных анализов исчерпан. Приобретите подписку для продолжения.';

    showPaywall(used, limit, message);

    // Also update the bar
    updateUsageBar({
        used: used,
        limit: limit,
        plan: detail.plan || 'basic',
        plan_name: 'Basic',
    });
}

// ============================================================
// INIT
// ============================================================

document.addEventListener('DOMContentLoaded', function () {
    // Load usage info on page load
    loadUsageInfo();

    // Close paywall buttons
    const closeBtn = document.getElementById('paywallClose');
    const skipBtn = document.getElementById('paywallSkip');

    if (closeBtn) closeBtn.addEventListener('click', hidePaywall);
    if (skipBtn) skipBtn.addEventListener('click', hidePaywall);

    // Close on overlay click
    const modal = document.getElementById('paywallModal');
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal) hidePaywall();
        });
    }

    // ESC key to close
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') hidePaywall();
    });
});
