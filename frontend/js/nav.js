/**
 * DogovorAI — Shared Navigation Component
 * Renders the consistent header/navbar across all pages.
 * Usage: Add <div id="nav-root"></div> at top of <body>, then include this script.
 * Or call Nav.init() after DOM is ready.
 */
(function() {
    'use strict';

    // ─── Inject mobile nav styles ────────────────────────────────────────────────
    const _navStyles = document.createElement('style');
    _navStyles.textContent = `
        .nav-mobile-toggle {
            display: none;
            flex-direction: column;
            gap: 5px;
            background: none;
            border: none;
            cursor: pointer;
            padding: 8px;
        }
        .nav-mobile-toggle span {
            display: block;
            width: 22px;
            height: 2px;
            background: var(--text-secondary);
            border-radius: 2px;
            transition: all 0.3s ease;
        }
        .nav-mobile-toggle.open span:nth-child(1) { transform: rotate(45deg) translate(5px, 5px); }
        .nav-mobile-toggle.open span:nth-child(2) { opacity: 0; }
        .nav-mobile-toggle.open span:nth-child(3) { transform: rotate(-45deg) translate(5px, -5px); }
        .nav-mobile-overlay {
            position: fixed;
            top: 65px;
            left: 0;
            right: 0;
            background: rgba(8,11,20,0.98);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid rgba(255,255,255,0.08);
            z-index: 99;
            padding: 16px 0 24px;
        }
        .nav-mobile-menu {
            display: flex;
            flex-direction: column;
            gap: 4px;
            padding: 0 24px;
        }
        .nav-mobile-menu .nav-link {
            display: block;
            padding: 12px 0;
            font-size: 16px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .nav-mobile-auth {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 16px;
        }
        .nav-mobile-btn {
            display: block;
            padding: 14px;
            text-align: center;
            border-radius: 12px;
            font-weight: 600;
            text-decoration: none;
            font-size: 15px;
            font-family: var(--font);
            cursor: pointer;
            border: none;
            background: var(--accent-indigo, #4f46e5);
            color: white;
            transition: all 0.2s;
        }
        .nav-mobile-btn.secondary {
            background: rgba(255,255,255,0.06);
            color: var(--text-primary, #f0f4ff);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .nav-mobile-btn.danger {
            background: rgba(239,68,68,0.12);
            color: #f87171;
            border: 1px solid rgba(239,68,68,0.25);
        }
        @media (max-width: 768px) {
            .nav-mobile-toggle { display: flex; }
            #app-nav .nav-link, #app-nav .nav-auth { display: none !important; }
        }
    `;
    document.head.appendChild(_navStyles);

    // ─── Nav Component ───────────────────────────────────────────────────────────
    const Nav = {
        /**
         * Determines which nav link should be active based on current path
         */
        getActivePath() {
            const path = window.location.pathname;
            if (path === '/app' || path === '/app/') return 'analyze';
            if (path.startsWith('/app/contracts')) return 'contracts';
            if (path.startsWith('/app/history')) return 'history';
            if (path.startsWith('/app/profile')) return 'profile';
            return '';
        },

        /**
         * Renders the nav HTML into #nav-root or prepends to body
         */
        render() {
            const active = this.getActivePath();
            const navLink = (href, label, key) => {
                const isActive = active === key;
                return `<a href="${href}" class="nav-link${isActive ? ' nav-link-active' : ''}">${label}</a>`;
            };

            const html = `
<header class="header" id="app-header">
    <div class="container">
        <div class="logo">
            <a href="/app" style="display:flex;align-items:center;gap:10px;text-decoration:none;color:inherit;">
                <span class="logo-icon">⚖️</span>
                <span class="logo-text">Dogovor<span class="logo-accent">AI</span></span>
            </a>
        </div>
        <nav class="nav" id="app-nav">
            ${navLink('/app', 'Анализ', 'analyze')}
            ${navLink('/app/history', 'История', 'history')}

            <!-- Logged-OUT state -->
            <div class="nav-auth nav-auth-logged-out">
                <a href="/app/login" class="nav-button nav-button-secondary">Войти</a>
                <a href="/app/register" class="nav-button">Регистрация</a>
            </div>

            <!-- Logged-IN state -->
            <div class="nav-auth nav-auth-logged-in" style="display:none; position:relative;">
                <button class="user-avatar-btn" id="userAvatarBtn" aria-label="Профиль пользователя">
                    <img class="user-avatar-img" id="userAvatarImg" src="" alt="" style="display:none;">
                    <div class="user-avatar-placeholder" id="userAvatarPlaceholder">
                        <span id="userInitial">?</span>
                    </div>
                </button>
                <div class="user-dropdown" id="userDropdown">
                    <div class="user-dropdown-header">
                        <div class="dropdown-name" id="dropdownName">Пользователь</div>
                        <div class="dropdown-plan" id="dropdownPlan">Basic</div>
                    </div>
                    <div class="user-dropdown-divider"></div>
                    <a href="/app/profile" class="user-dropdown-item">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                        Мой профиль
                    </a>
                    <a href="/app/profile#subscription" class="user-dropdown-item">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></svg>
                        Подписка
                    </a>
                    <div class="user-dropdown-divider"></div>
                    <button class="user-dropdown-item user-dropdown-logout" id="navLogoutBtn">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>
                        Выйти
                    </button>
                </div>
            </div>
        </nav>

        <!-- Mobile menu toggle -->
        <button class="nav-mobile-toggle" id="navMobileToggle" aria-label="Меню">
            <span></span><span></span><span></span>
        </button>
    </div>

    <!-- Mobile nav overlay -->
    <div class="nav-mobile-overlay" id="navMobileOverlay" style="display:none;">
        <nav class="nav-mobile-menu">
            ${navLink('/app', 'Анализ', 'analyze')}
            ${navLink('/app/history', 'История', 'history')}
            <div class="nav-mobile-auth nav-mobile-logged-out">
                <a href="/app/login" class="nav-mobile-btn secondary">Войти</a>
                <a href="/app/register" class="nav-mobile-btn">Регистрация</a>
            </div>
            <div class="nav-mobile-auth nav-mobile-logged-in" style="display:none;">
                <a href="/app/profile" class="nav-mobile-btn secondary">Профиль</a>
                <button class="nav-mobile-btn danger" id="navMobileLogout">Выйти</button>
            </div>
        </nav>
    </div>
</header>`;

            // Insert the header
            let root = document.getElementById('nav-root');
            if (root) {
                root.outerHTML = html;
            } else {
                document.body.insertAdjacentHTML('afterbegin', html);
            }

            // Wire up interactions
            this.setupInteractions();

            // Update auth state
            if (typeof isAuthenticated === 'function') {
                this.updateAuthState();
            } else {
                // Wait for auth-guard.js to load
                document.addEventListener('DOMContentLoaded', () => this.updateAuthState());
            }
        },

        updateAuthState() {
            try {
                if (typeof isAuthenticated !== 'function') return;
                const authed = isAuthenticated();
                const user = typeof getUser === 'function' ? getUser() : null;

                const loggedOut = document.querySelectorAll('.nav-auth-logged-out, .nav-mobile-logged-out');
                const loggedIn = document.querySelectorAll('.nav-auth-logged-in, .nav-mobile-logged-in');

                loggedOut.forEach(el => el.style.display = authed ? 'none' : 'flex');
                loggedIn.forEach(el => el.style.display = authed ? 'flex' : 'none');

                if (authed && user) {
                    const name = user.full_name || user.email || 'Пользователь';
                    const plan = (user.plan || 'basic');
                    const planLabel = plan.charAt(0).toUpperCase() + plan.slice(1);

                    const dn = document.getElementById('dropdownName');
                    const dp = document.getElementById('dropdownPlan');
                    if (dn) dn.textContent = name;
                    if (dp) dp.textContent = `Тариф: ${planLabel}`;

                    const avatarImg = document.getElementById('userAvatarImg');
                    const avatarPlaceholder = document.getElementById('userAvatarPlaceholder');
                    const userInitial = document.getElementById('userInitial');

                    if (user.avatar_url && avatarImg) {
                        avatarImg.src = user.avatar_url;
                        avatarImg.style.display = 'block';
                        if (avatarPlaceholder) avatarPlaceholder.style.display = 'none';
                    } else {
                        if (avatarImg) avatarImg.style.display = 'none';
                        if (avatarPlaceholder) avatarPlaceholder.style.display = 'flex';
                        if (userInitial) userInitial.textContent = name[0].toUpperCase();
                    }
                }
            } catch(e) {
                console.warn('[Nav] Could not update auth state:', e);
            }
        },

        setupInteractions() {
            // ── Dropdown toggle ──────────────────────────────────────────────────
            const avatarBtn = document.getElementById('userAvatarBtn');
            const dropdown = document.getElementById('userDropdown');

            if (avatarBtn && dropdown) {
                avatarBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    dropdown.classList.toggle('open');
                });
                document.addEventListener('click', () => dropdown.classList.remove('open'));
                dropdown.addEventListener('click', (e) => e.stopPropagation());
            }

            // ── Logout ───────────────────────────────────────────────────────────
            const logoutBtn = document.getElementById('navLogoutBtn');
            const mobileLogout = document.getElementById('navMobileLogout');
            const doLogout = async () => {
                try {
                    const headers = typeof getAuthHeaders === 'function' ? getAuthHeaders() : {};
                    await fetch('/api/auth/logout', { method: 'POST', headers });
                } catch(_) {}
                localStorage.clear();
                window.location.href = '/app/login';
            };
            if (logoutBtn) logoutBtn.addEventListener('click', doLogout);
            if (mobileLogout) mobileLogout.addEventListener('click', doLogout);

            // ── Mobile toggle ────────────────────────────────────────────────────
            const mobileToggle = document.getElementById('navMobileToggle');
            const mobileOverlay = document.getElementById('navMobileOverlay');

            if (mobileToggle && mobileOverlay) {
                mobileToggle.addEventListener('click', () => {
                    const isOpen = mobileOverlay.style.display !== 'none';
                    mobileOverlay.style.display = isOpen ? 'none' : 'block';
                    mobileToggle.classList.toggle('open', !isOpen);
                });
            }

            // ── Scroll-aware header opacity ──────────────────────────────────────
            const header = document.getElementById('app-header');
            if (header) {
                let lastScroll = 0;
                window.addEventListener('scroll', () => {
                    const scrollY = window.scrollY;
                    if (scrollY > 60) {
                        header.style.background = 'rgba(13, 20, 36, 0.95)';
                    } else {
                        header.style.background = 'rgba(13, 20, 36, 0.75)';
                    }
                    lastScroll = scrollY;
                }, { passive: true });
            }
        },

        init() {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.render());
            } else {
                this.render();
            }
        }
    };

    // ── Auto-initialize ──────────────────────────────────────────────────────────
    Nav.init();

    // Expose globally for manual auth state refresh (e.g. after login)
    window.NavComponent = Nav;
})();
