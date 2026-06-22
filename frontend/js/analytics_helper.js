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

  // Состояние инициализации
  var _isInitialized = false;
  var _config = null;
  var _queue = [];
  var _debugMode = false;

  // Определение режима отладки (?ga_debug в URL)
  try {
    _debugMode = new URLSearchParams(window.location.search).has('ga_debug');
  } catch (e) {
    // ignore
  }

  // Безопасная обёртка для работы с dataLayer
  function _gtag() {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(arguments);
  }

  // Запуск загрузки настроек
  fetch('/api/config/analytics')
    .then(function (response) {
      if (!response.ok) {
        throw new Error('HTTP error ' + response.status);
      }
      return response.json();
    })
    .then(function (configData) {
      initAnalytics(configData);
    })
    .catch(function (error) {
      console.warn('[Analytics] Failed to fetch config, falling back to default keys:', error);
      // Дефолтные значения для обратной совместимости
      initAnalytics({
        posthog_api_key: 'phc_nJvUqL8Gbc2WdsY5rfX5w8xuok5uVgMJc68zKLKN4nmk',
        posthog_host: 'https://us.i.posthog.com',
        ga_measurement_id: 'G-G6SYPHRVJL',
        gtm_id: 'GTM-KSV7XQ6S'
      });
    });

  // Функция инициализации трекеров
  function initAnalytics(configData) {
    _config = configData;

    if (_debugMode) {
      console.info('[Analytics] Инициализация аналитики с конфигом:', _config);
    }

    // 1. Инициализация PostHog
    if (_config.posthog_api_key) {
      (function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}var c=e;for(void 0!==a?c=e[a]=[]:a="posthog",c.people=c.people||[],c.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},c.people.toString=function(){return c.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures onSessionId".split(" "),n=0;n<o.length;n++)g(c,o[n]);e._i.push([i,s,a])},e.__SV=1.6,o=t.createElement("script"),o.type="text/javascript",o.async=!0,o.src=_config.posthog_host + "/static/array.js",n=t.getElementsByTagName("script")[0],n.parentNode.insertBefore(o,n))}(document,window.posthog||[]);

      window.posthog.init(_config.posthog_api_key, {
        api_host: _config.posthog_host,
        person_profiles: 'identified_only'
      });
    }

    // 2. Инициализация Google Analytics 4 (gtag.js)
    if (_config.ga_measurement_id) {
      // Динамическая вставка скрипта
      var gaScript = document.createElement('script');
      gaScript.async = true;
      gaScript.src = 'https://www.googletagmanager.com/gtag/js?id=' + _config.ga_measurement_id;
      document.head.appendChild(gaScript);

      _gtag('js', new Date());
      var gaParams = {};
      if (_debugMode) {
        gaParams.debug_mode = true;
      }
      _gtag('config', _config.ga_measurement_id, gaParams);
    }

    // 3. Инициализация Google Tag Manager (GTM)
    if (_config.gtm_id) {
      (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
      new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
      j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
      'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
      })(window,document,'script','dataLayer',_config.gtm_id);
    }

    // Восстановление user_id из localStorage
    _restoreUser();

    // Пометка об успешной инициализации
    _isInitialized = true;

    // Выполнение накопившихся в очереди событий
    if (_debugMode && _queue.length > 0) {
      console.info('[Analytics] Выполнение событий из очереди:', _queue.length);
    }
    while (_queue.length > 0) {
      var task = _queue.shift();
      try {
        task();
      } catch (err) {
        console.error('[Analytics] Ошибка выполнения отложенного события:', err);
      }
    }

    if (_debugMode) {
      console.info('[Analytics] Инициализация завершена успешно.');
    }
  }

  // Внутренняя функция авторизации/восстановления пользователя
  function _restoreUser() {
    try {
      var raw = localStorage.getItem('user');
      if (!raw) return;
      var user = JSON.parse(raw);
      if (user && user.id) {
        var uid = String(user.id);
        if (_config && _config.ga_measurement_id) {
          _gtag('config', _config.ga_measurement_id, { user_id: uid });
          _gtag('set', 'user_properties', { user_id: uid });
        }
        if (window.posthog) {
          window.posthog.identify(uid);
        }
        if (_debugMode) {
          console.info('[Analytics] Restored user_id from localStorage:', uid);
        }
      }
    } catch (e) {
      // ignore
    }
  }

  // ── PUBLIC API ─────────────────────────────────────────────────────────────

  /**
   * Отправить произвольное GA4- и PostHog-событие.
   * @param {string} eventName  — название события (snake_case)
   * @param {Object} [params]   — параметры события
   */
  window.trackEvent = function (eventName, params) {
    var runTrack = function () {
      try {
        var payload = Object.assign({}, params || {});
        if (_debugMode) {
          payload.debug_mode = true;
          console.info('[Analytics] trackEvent:', eventName, payload);
        }
        if (_config && _config.ga_measurement_id) {
          _gtag('event', eventName, payload);
        }
        if (window.posthog) {
          window.posthog.capture(eventName, payload);
        }
      } catch (e) {
        console.warn('[Analytics] trackEvent failed:', e);
      }
    };

    if (!_isInitialized) {
      _queue.push(runTrack);
    } else {
      runTrack();
    }
  };

  /**
   * Установить user_id для текущей и последующих сессий.
   * Вызывать сразу после успешного входа или регистрации.
   * @param {string|number} userId
   */
  window.identifyUser = function (userId) {
    if (!userId) return;
    
    var runIdentify = function () {
      try {
        var uid = String(userId);
        if (_config && _config.ga_measurement_id) {
          _gtag('config', _config.ga_measurement_id, { user_id: uid });
          _gtag('set', 'user_properties', { user_id: uid });
        }
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

    if (!_isInitialized) {
      _queue.push(runIdentify);
    } else {
      runIdentify();
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
    console.info('[Analytics] analytics_helper.js loaded.');
  }
})();
