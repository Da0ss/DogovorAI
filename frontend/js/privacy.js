/**
 * DogovorAI — Privacy Policy Modal
 * Показывает модал с политикой конфиденциальности при первом посещении.
 * Блокирует весь интерфейс до принятия условий.
 * Состояние хранится в localStorage под ключом 'dogovorai_privacy_accepted'.
 */
(function () {
    'use strict';

    const STORAGE_KEY = 'dogovorai_privacy_accepted';
    const POLICY_VERSION = '1.0'; // Смени версию, чтобы показать модал повторно

    // Если уже принято — ничего не делаем
    if (localStorage.getItem(STORAGE_KEY) === POLICY_VERSION) return;

    // ──────────────────────────────────────────────
    // 1. HTML разметка модала
    // ──────────────────────────────────────────────
    const policyHTML = `
      <h2>1. Общие положения</h2>
      <p>Настоящая Политика конфиденциальности регулирует порядок обработки и защиты персональных данных пользователей сервиса по анализу договоров, выявлению рисков и созданию договоров с учетом предложенных исправлений (далее — «Сервис»).</p>
      <p>Используя Сервис, пользователь подтверждает согласие с данной Политикой.</p>
      <hr>
      <h2>2. Собираемые данные</h2>
      <h3>2.1. Данные, предоставляемые пользователем</h3>
      <ul>
        <li>Загружаемые документы (договоры, соглашения и иные файлы)</li>
        <li>Текстовые данные, вводимые пользователем</li>
        <li>Контактные данные (при регистрации): email, имя</li>
      </ul>
      <h3>2.2. Автоматически собираемые данные</h3>
      <ul>
        <li>IP-адрес</li>
        <li>Тип устройства и браузера</li>
        <li>Логи действий в Сервисе</li>
        <li>Cookies и аналогичные технологии</li>
      </ul>
      <hr>
      <h2>3. Цели обработки данных</h2>
      <p>Персональные данные используются для:</p>
      <ul>
        <li>Анализа документов и выявления юридических рисков</li>
        <li>Генерации рекомендаций по улучшению договоров</li>
        <li>Создания новых договоров на основе пользовательских данных</li>
        <li>Улучшения качества работы Сервиса</li>
        <li>Обеспечения безопасности и предотвращения злоупотреблений</li>
      </ul>
      <hr>
      <h2>4. Обработка документов</h2>
      <ul>
        <li>Загруженные документы обрабатываются автоматически с использованием алгоритмов анализа текста и искусственного интеллекта</li>
        <li>Сервис не использует документы для иных целей без согласия пользователя</li>
        <li>Документы могут временно храниться для обеспечения работы функций Сервиса</li>
      </ul>
      <hr>
      <h2>5. Хранение и защита данных</h2>
      <ul>
        <li>Данные хранятся в защищенных инфраструктурах</li>
        <li>Применяются меры защиты: шифрование, контроль доступа, аудит действий</li>
        <li>Срок хранения данных определяется необходимостью оказания услуг либо требованиями законодательства</li>
      </ul>
      <hr>
      <h2>6. Передача данных третьим лицам</h2>
      <p>Сервис не передает персональные данные третьим лицам, за исключением случаев:</p>
      <ul>
        <li>Требований законодательства</li>
        <li>Необходимости выполнения функций Сервиса (например, облачные провайдеры)</li>
        <li>Получения явного согласия пользователя</li>
      </ul>
      <hr>
      <h2>7. Права пользователя</h2>
      <p>Пользователь имеет право:</p>
      <ul>
        <li>Запросить доступ к своим данным</li>
        <li>Требовать исправления или удаления данных</li>
        <li>Отозвать согласие на обработку</li>
        <li>Ограничить обработку данных</li>
      </ul>
      <hr>
      <h2>8. Использование cookies</h2>
      <p>Сервис может использовать cookies для:</p>
      <ul>
        <li>Аутентификации пользователей</li>
        <li>Сохранения пользовательских настроек</li>
        <li>Аналитики и улучшения работы</li>
      </ul>
      <p>Пользователь может отключить cookies в настройках браузера.</p>
      <hr>
      <h2>9. Ограничение ответственности</h2>
      <p>Сервис предоставляет результаты анализа в информационных целях и не является заменой юридической консультации. Пользователь самостоятельно принимает решения на основе предоставленных рекомендаций.</p>
      <hr>
      <h2>10. Изменения политики</h2>
      <p>Сервис оставляет за собой право изменять настоящую Политику. Обновленная версия вступает в силу с момента публикации.</p>
      <hr>
      <h2>11. Контактная информация</h2>
      <p>По вопросам обработки данных пользователь может обратиться:</p>
      <p>Email: <a href="mailto:damikserik@gmail.com">damikserik@gmail.com</a></p>
    `;

    // ──────────────────────────────────────────────
    // 2. Создаём DOM-элементы
    // ──────────────────────────────────────────────
    const overlay = document.createElement('div');
    overlay.id = 'privacyOverlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'ppTitle');

    overlay.innerHTML = `
      <div class="pp-card">

        <!-- Шапка -->
        <div class="pp-header">
          <div class="pp-header-top">
            <div class="pp-icon">🔐</div>
            <h1 class="pp-title" id="ppTitle">Политика конфиденциальности</h1>
          </div>
          <p class="pp-subtitle">Ознакомьтесь с условиями обработки данных перед использованием сервиса</p>
        </div>

        <!-- Прокручиваемый контент -->
        <div class="pp-body" id="ppBody">
          <div class="pp-content">${policyHTML}</div>
        </div>

        <!-- Подсказка «прокрутите вниз» -->
        <div class="pp-scroll-hint" id="ppScrollHint">
          <span class="pp-scroll-arrow">↓</span>
          Прокрутите вниз, чтобы ознакомиться со всем текстом
        </div>

        <!-- Подвал -->
        <div class="pp-footer">
          <label class="pp-checkbox-row" id="ppCheckboxRow" for="ppCheckbox">
            <input type="checkbox" id="ppCheckbox">
            <span class="pp-checkbox-box">
              <span class="pp-check-icon">✓</span>
            </span>
            <span class="pp-checkbox-text">
              Я ознакомился(-ась) с Политикой конфиденциальности и принимаю условия обработки персональных данных
            </span>
          </label>

          <div class="pp-actions">
            <button class="pp-btn-accept" id="ppAcceptBtn" disabled>
              Принять и продолжить →
            </button>
          </div>
        </div>
      </div>
    `;

    // Блокируем скролл страницы пока открыт модал
    document.body.style.overflow = 'hidden';
    document.body.appendChild(overlay);

    // ──────────────────────────────────────────────
    // 3. Логика взаимодействия
    // ──────────────────────────────────────────────
    const checkbox  = overlay.querySelector('#ppCheckbox');
    const acceptBtn = overlay.querySelector('#ppAcceptBtn');
    const body      = overlay.querySelector('#ppBody');
    const scrollHint = overlay.querySelector('#ppScrollHint');

    // Включаем кнопку при отметке чекбокса
    checkbox.addEventListener('change', () => {
        acceptBtn.disabled = !checkbox.checked;
    });

    // Скрываем подсказку прокрутки как только пользователь доскроллил до конца
    body.addEventListener('scroll', () => {
        const atBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 40;
        if (atBottom) {
            scrollHint.classList.add('hidden');
        }
    }, { passive: true });

    // Принятие условий
    acceptBtn.addEventListener('click', () => {
        if (!checkbox.checked) return;

        localStorage.setItem(STORAGE_KEY, POLICY_VERSION);

        // Анимация закрытия
        overlay.classList.add('pp-hiding');
        overlay.addEventListener('animationend', () => {
            overlay.remove();
            document.body.style.overflow = '';
        }, { once: true });
    });

    // Запрещаем закрытие по клику на фон
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            // Визуальная подсказка — «потрясение» карточки
            const card = overlay.querySelector('.pp-card');
            card.style.animation = 'none';
            card.offsetHeight; // reflow
            card.style.animation = 'ppShake 0.35s ease';
        }
    });

})();
