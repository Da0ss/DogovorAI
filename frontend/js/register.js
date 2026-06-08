/**
 * DogovorAI — Registration Page Logic
 * Handles email/password registration, email verification, and Google OAuth registration.
 * Enforces mandatory Terms of Service consent for ALL registration methods.
 */

const API_BASE = '/api/auth';
const REGISTER_URL = `${API_BASE}/register`;
const VERIFY_URL = `${API_BASE}/verify`;
const GOOGLE_AUTH_URL = `${API_BASE}/google`;

const registerForm = document.querySelector('#registerForm');
const verifyForm = document.querySelector('#verifyForm');
const messageBox = document.querySelector('#message');
const registerButton = document.querySelector('#registerButton');
const verifyButton = document.querySelector('#verifyButton');
const registerSpinner = document.querySelector('#registerSpinner');
const verifySpinner = document.querySelector('#verifySpinner');
const googleRegisterBtn = document.querySelector('#googleRegisterBtn');

let registeredEmail = '';

// ============================================================
// UI Helpers
// ============================================================

function setMessage(text, type = 'success') {
  if (!text) {
    messageBox.textContent = '';
    messageBox.className = 'message';
    return;
  }

  messageBox.textContent = text;
  messageBox.className = `message ${type}`;
}

function setLoading(button, spinner, isLoading) {
  if (isLoading) {
    button.classList.add('loading');
    button.disabled = true;
    spinner.style.display = 'inline-block';
  } else {
    button.classList.remove('loading');
    button.disabled = false;
    spinner.style.display = 'none';
  }
}

function validateEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function validatePassword(value) {
  return value.trim().length >= 6;
}

function parseJsonResponse(response) {
  return response.text().then((text) => {
    try {
      return text ? JSON.parse(text) : {};
    } catch (error) {
      return { detail: text || 'Неизвестная ошибка' };
    }
  });
}

/**
 * Check if the terms consent checkbox is checked.
 * If not, show a shake animation and an error message.
 * Returns true if consent is given, false otherwise.
 */
function requireConsent() {
  const termsConsent = document.querySelector('#termsConsent');
  if (!termsConsent) return true; // no checkbox = no gate

  if (termsConsent.checked) return true;

  // Show error message
  setMessage('Пожалуйста, примите Условия использования и Политику конфиденциальности для продолжения.', 'error');

  // Shake animation on the checkbox row
  const consentRow = termsConsent.closest('.flex.items-start') || termsConsent.parentElement;
  if (consentRow) {
    consentRow.classList.add('consent-shake');
    // Also highlight the checkbox border
    termsConsent.style.outline = '2px solid #ba1a1a';
    termsConsent.style.outlineOffset = '1px';

    setTimeout(() => {
      consentRow.classList.remove('consent-shake');
      termsConsent.style.outline = '';
      termsConsent.style.outlineOffset = '';
    }, 800);
  }

  return false;
}

// ============================================================
// Email/Password Registration
// ============================================================

async function handleRegister(event) {
  event.preventDefault();
  setMessage('');

  const email = registerForm.email.value.trim();
  const password = registerForm.password.value;
  const confirmPassword = registerForm.confirmPassword ? registerForm.confirmPassword.value : password;

  if (!validateEmail(email)) {
    setMessage('Введите корректный email.', 'error');
    return;
  }

  if (!validatePassword(password)) {
    setMessage('Пароль должен содержать минимум 6 символов.', 'error');
    return;
  }

  if (password !== confirmPassword) {
    setMessage('Пароли не совпадают.', 'error');
    return;
  }

  if (!requireConsent()) return;

  setLoading(registerButton, registerSpinner, true);

  try {
    const response = await fetch(REGISTER_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ email, password, consent: true })
    });

    const data = await parseJsonResponse(response);

    if (!response.ok) {
      const message = data.detail || 'Не удалось зарегистрировать пользователя.';
      setMessage(message, 'error');
      return;
    }

    registeredEmail = email;
    setMessage('Код отправлен. Введите его для подтверждения.', 'success');
    registerForm.classList.add('hidden');
    verifyForm.classList.remove('hidden');

    // Hide Google button and divider after registration
    const googleBtn = document.getElementById('googleRegisterBtn');
    const divider = document.querySelector('.divider');
    if (googleBtn) googleBtn.style.display = 'none';
    if (divider) divider.style.display = 'none';

  } catch (error) {
    setMessage('Сеть недоступна. Попробуйте позже.', 'error');
  } finally {
    setLoading(registerButton, registerSpinner, false);
  }
}

// ============================================================
// Email Verification
// ============================================================

async function handleVerify(event) {
  event.preventDefault();
  setMessage('');

  const code = verifyForm.verifyCode.value.trim();
  const email = registeredEmail || registerForm.email.value.trim();

  if (!email || !validateEmail(email)) {
    setMessage('Невозможно подтвердить: некорректный email.', 'error');
    return;
  }

  if (!/^\d{6}$/.test(code)) {
    setMessage('Код должен содержать ровно 6 цифр.', 'error');
    return;
  }

  setLoading(verifyButton, verifySpinner, true);

  try {
    const response = await fetch(VERIFY_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ email, code })
    });

    const data = await parseJsonResponse(response);

    if (!response.ok) {
      const message = data.detail || 'Не удалось подтвердить код.';
      setMessage(message, 'error');
      return;
    }

    setMessage('Аккаунт подтвержден успешно. Перенаправление...', 'success');
    verifyForm.classList.add('hidden');

    // Redirect to login page after successful verification
    setTimeout(() => {
      window.location.href = '/app/login';
    }, 1500);
  } catch (error) {
    setMessage('Сеть недоступна. Попробуйте позже.', 'error');
  } finally {
    setLoading(verifyButton, verifySpinner, false);
  }
}

// ============================================================
// Google OAuth Registration
// ============================================================

async function handleGoogleRegister() {
  setMessage('');

  if (!requireConsent()) return;

  googleRegisterBtn.setAttribute('disabled', 'disabled');
  setMessage('Перенаправление на Google...', 'success');

  try {
    // Send consent=true to backend so it's validated server-side too
    const response = await fetch(`${GOOGLE_AUTH_URL}?consent=true`);
    const data = await parseJsonResponse(response);

    if (!response.ok) {
      setMessage(data.detail || 'Не удалось начать регистрацию через Google.', 'error');
      googleRegisterBtn.removeAttribute('disabled');
      return;
    }

    if (data.url) {
      // Redirect to Google OAuth consent screen
      window.location.href = data.url;
    } else {
      setMessage('Ошибка: не получен URL для авторизации.', 'error');
      googleRegisterBtn.removeAttribute('disabled');
    }

  } catch (error) {
    console.error('Google register error:', error);
    setMessage('Ошибка подключения к серверу. Попробуйте позже.', 'error');
    googleRegisterBtn.removeAttribute('disabled');
  }
}

// ============================================================
// Event Listeners
// ============================================================

registerForm.addEventListener('submit', handleRegister);
verifyForm.addEventListener('submit', handleVerify);
googleRegisterBtn.addEventListener('click', handleGoogleRegister);
