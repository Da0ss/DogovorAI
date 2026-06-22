/**
 * DogovorAI — Google Analytics 4 Helper
 * ==========================================
 * Центральный модуль для отправки кастомных событий в GA4.
 *
 * Подключать ПОСЛЕ тега gtag.js на каждой странице:
 *   <script src="/static/js/analytics_helper.js"></script>
 *
 * Экспортирует глобальные функции:
 *   - trackEvent(eventName, params)  → отправить произвольное событие
 *   - identifyUser(userId)           → установить user_id для текущей сессии
 *   - trackError(errorType, message) → хелпер для error_event
 */

(function () {
  'use strict';

  const GA_MEASUREMENT_ID = 'G-G6SYPHRVJL';

  // ── Безопасная обёртка над gtag ────────────────────────────────────────────
  function _gtag() {
    if (typeof gtag === 'function') {
      gtag.apply(null, arguments);
    } else {
      // gtag ещё не загрузился — ставим в очередь dataLayer
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push(arguments);
    }
  }

  // ── Определяем режим отладки (DebugView) ───────────────────────────────────
  // Активируется при наличии ?ga_debug в URL.
  var _debugMode = (function () {
    try {
      return new URLSearchParams(window.location.search).has('ga_debug');
    } catch (e) {
      return false;
    }
  })();

  if (_debugMode) {
    console.info('[GA4] DebugView mode ON — события видны в GA4 → DebugView');
    _gtag('config', GA_MEASUREMENT_ID, { debug_mode: true });
  }

  // ── Восстановление user_id из localStorage при загрузке страницы ───────────
  (function _restoreUser() {
    try {
      var raw = localStorage.getItem('user');
      if (!raw) return;
      var user = JSON.parse(raw);
      if (user && user.id) {
        _gtag('config', GA_MEASUREMENT_ID, { user_id: String(user.id) });
        _gtag('set', 'user_properties', { user_id: String(user.id) });
        if (_debugMode) {
          console.info('[GA4] Restored user_id from localStorage:', user.id);
        }
      }
    } catch (e) {
      // ignore parse errors
    }
  })();

  // ── PUBLIC API ─────────────────────────────────────────────────────────────

  /**
   * Отправить произвольное GA4-событие.
   * @param {string} eventName  — название события (snake_case)
   * @param {Object} [params]   — дополнительные параметры события
   *
   * @example
   *   trackEvent('feature_usage', { feature_name: 'contract_analysis' });
   */
  window.trackEvent = function (eventName, params) {
    try {
      var payload = Object.assign({}, params || {});
      if (_debugMode) {
        payload.debug_mode = true;
        console.info('[GA4] trackEvent:', eventName, payload);
      }
      _gtag('event', eventName, payload);
    } catch (e) {
      console.warn('[GA4] trackEvent failed:', e);
    }
  };

  /**
   * Установить user_id для текущей и последующих GA4-сессий.
   * Вызывать сразу после успешного входа или регистрации.
   * @param {string|number} userId
   *
   * @example
   *   identifyUser('abc-123');
   */
  window.identifyUser = function (userId) {
    if (!userId) return;
    try {
      var uid = String(userId);
      _gtag('config', GA_MEASUREMENT_ID, { user_id: uid });
      _gtag('set', 'user_properties', { user_id: uid });
      if (_debugMode) {
        console.info('[GA4] identifyUser:', uid);
      }
    } catch (e) {
      console.warn('[GA4] identifyUser failed:', e);
    }
  };

  /**
   * Хелпер для быстрой отправки события ошибки.
   * @param {string} errorType    — тип/код ошибки (напр. 'analysis_failed')
   * @param {string} [message]    — текст ошибки
   * @param {string} [page]       — страница/контекст (напр. 'index')
   *
   * @example
   *   trackError('analysis_failed', error.message, 'index');
   */
  window.trackError = function (errorType, message, page) {
    window.trackEvent('error_event', {
      error_type: errorType || 'unknown',
      error_message: String(message || '').substring(0, 200), // GA4 limit
      error_page: page || window.location.pathname,
    });
  };

  // ── Глобальный перехват необработанных ошибок ──────────────────────────────
  window.addEventListener('unhandledrejection', function (e) {
    window.trackError(
      'unhandled_promise_rejection',
      e.reason instanceof Error ? e.reason.message : String(e.reason)
    );
  });

  window.addEventListener('error', function (e) {
    if (e && e.message) {
      window.trackError('js_error', e.message, e.filename || window.location.pathname);
    }
  });

  if (_debugMode) {
    console.info('[GA4] analytics_helper.js loaded. ID:', GA_MEASUREMENT_ID);
  }
})();
