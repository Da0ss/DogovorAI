/**
 * DogovorAI — Analytics Helper (Google Analytics 4 & PostHog)
 * =============================================================
 * Центральный модуль для отправки кастомных событий в GA4 и PostHog.
 *
 * Подключать ПОСЛЕ тегов GA4/GTM на каждой странице:
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

  // ── Инициализация PostHog ──────────────────────────────────────────────────
  (function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}var c=e;for(void 0!==a?c=e[a]=[]:a="posthog",c.people=c.people||[],c.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},c.people.toString=function(){return c.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures onSessionId".split(" "),n=0;n<o.length;n++)g(c,o[n]);e._i.push([i,s,a])},e.__SV=1.6,o=t.createElement("script"),o.type="text/javascript",o.async=!0,o.src="https://us.posthog.com/static/array.js",n=t.getElementsByTagName("script")[0],n.parentNode.insertBefore(o,n))}(document,window.posthog||[]);

  posthog.init('phc_nJvUqL8Gbc2WdsY5rfX5w8xuok5uVgMJc68zKLKN4nmk', {
    api_host: 'https://us.i.posthog.com',
    person_profiles: 'identified_only'
  });

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
    console.info('[Analytics] DebugView mode ON — события видны в GA4 & PostHog');
    _gtag('config', GA_MEASUREMENT_ID, { debug_mode: true });
  }

  // ── Восстановление user_id из localStorage при загрузке страницы ───────────
  (function _restoreUser() {
    try {
      var raw = localStorage.getItem('user');
      if (!raw) return;
      var user = JSON.parse(raw);
      if (user && user.id) {
        var uid = String(user.id);
        _gtag('config', GA_MEASUREMENT_ID, { user_id: uid });
        _gtag('set', 'user_properties', { user_id: uid });
        if (window.posthog) {
          window.posthog.identify(uid);
        }
        if (_debugMode) {
          console.info('[Analytics] Restored user_id from localStorage:', uid);
        }
      }
    } catch (e) {
      // ignore parse errors
    }
  })();

  // ── PUBLIC API ─────────────────────────────────────────────────────────────

  /**
   * Отправить произвольное GA4- и PostHog-событие.
   * @param {string} eventName  — название события (snake_case)
   * @param {Object} [params]   — параметры события
   */
  window.trackEvent = function (eventName, params) {
    try {
      var payload = Object.assign({}, params || {});
      if (_debugMode) {
        payload.debug_mode = true;
        console.info('[Analytics] trackEvent:', eventName, payload);
      }
      _gtag('event', eventName, payload);
      if (window.posthog) {
        window.posthog.capture(eventName, payload);
      }
    } catch (e) {
      console.warn('[Analytics] trackEvent failed:', e);
    }
  };

  /**
   * Установить user_id для текущей и последующих сессий.
   * Вызывать сразу после успешного входа или регистрации.
   * @param {string|number} userId
   */
  window.identifyUser = function (userId) {
    if (!userId) return;
    try {
      var uid = String(userId);
      _gtag('config', GA_MEASUREMENT_ID, { user_id: uid });
      _gtag('set', 'user_properties', { user_id: uid });
      if (window.posthog) {
        window.posthog.identify(uid);
      }
      if (_debugMode) {
        console.info('[Analytics] identifyUser:', uid);
      }
    } catch (e) {
      console.warn('[Analytics] identifyUser failed:', e);
    }
  };

  /**
   * Хелпер для быстрой отправки события ошибки.
   * @param {string} errorType    — тип/код ошибки
   * @param {string} [message]    — текст ошибки
   * @param {string} [page]       — страница/контекст
   */
  window.trackError = function (errorType, message, page) {
    window.trackEvent('error_event', {
      error_type: errorType || 'unknown',
      error_message: String(message || '').substring(0, 200),
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
    console.info('[Analytics] analytics_helper.js loaded with GA4 & PostHog.');
  }
})();

