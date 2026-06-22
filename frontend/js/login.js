/**
 * DogovorAI — Login Page Logic
 * Handles passwordless OTP login and Google OAuth login.
 */

const API_BASE = '/api/auth';
const OTP_SEND_URL = `${API_BASE}/otp/send`;
const OTP_VERIFY_URL = `${API_BASE}/otp/verify`;
const GOOGLE_AUTH_URL = `${API_BASE}/google`;

// Form Elements
const step1Form = document.querySelector('#loginStep1Form');
const step2Form = document.querySelector('#loginStep2Form');
const getOtpBtn = document.querySelector('#getOtpButton');
const verifyOtpBtn = document.querySelector('#verifyOtpButton');
const otpSpinner = document.querySelector('#otpSpinner');
const verifySpinner = document.querySelector('#verifySpinner');
const changeEmailBtn = document.querySelector('#changeEmailBtn');
const displayEmail = document.querySelector('#displayEmail');

// UI Elements
const googleLoginBtn = document.querySelector('#googleLoginBtn');
const messageElement = document.querySelector('#message');
const divider = document.querySelector('.divider');

let currentEmail = '';

// ============================================================
// Redirect helpers
// ============================================================

/** Куда редиректить после успешного входа */
function getNextUrl() {
  const params = new URLSearchParams(window.location.search);
  const next = params.get('next');
  return (next && next.startsWith('/')) ? next : '/app';
}

// ============================================================
// Auth utilities
// ============================================================

function saveAuthData(data) {
  if (data.session) {
    localStorage.setItem('access_token', data.session.access_token);
    localStorage.setItem('refresh_token', data.session.refresh_token);
  }
  if (data.user) {
    localStorage.setItem('user', JSON.stringify(data.user));
  }
}

function isAuthenticated() {
  return !!localStorage.getItem('access_token');
}

function setLoading(button, spinner, isLoading) {
  if (isLoading) {
    button.classList.add('loading');
    button.setAttribute('disabled', 'disabled');
    if (spinner) spinner.style.display = 'inline-block';
  } else {
    button.classList.remove('loading');
    button.removeAttribute('disabled');
    if (spinner) spinner.style.display = 'none';
  }
}

function showMessage(text, type = 'error') {
  if (!text) {
    messageElement.textContent = '';
    messageElement.className = 'message';
    return;
  }
  messageElement.textContent = text;
  messageElement.className = `message ${type}`;
}

// ============================================================
// Passwordless OTP Login (Step 1: Send Code)
// ============================================================

async function handleSendOtp(event) {
  event.preventDefault();

  const email = step1Form.email.value.trim();

  if (!email) {
    showMessage('Пожалуйста, введите ваш email.');
    return;
  }

  setLoading(getOtpBtn, otpSpinner, true);
  showMessage('', '');

  try {
    const response = await fetch(OTP_SEND_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });

    const data = await response.json();
    if (!response.ok) {
      showMessage(data.detail || 'Не удалось отправить код.');
      return;
    }

    // Move to step 2
    currentEmail = email;
    displayEmail.textContent = email;
    step1Form.classList.add('hidden');
    step2Form.classList.remove('hidden');

    // Hide Google button and divider to keep UI clean during OTP
    if (googleLoginBtn) googleLoginBtn.style.display = 'none';
    if (divider) divider.style.display = 'none';

    showMessage('Код успешно отправлен!', 'success');

  } catch (error) {
    showMessage('Ошибка подключения. Попробуйте позже.');
  } finally {
    setLoading(getOtpBtn, otpSpinner, false);
  }
}

// ============================================================
// Passwordless OTP Login (Step 2: Verify Code)
// ============================================================

async function handleVerifyOtp(event) {
  event.preventDefault();

  const code = step2Form.code.value.trim();

  if (!code || code.length !== 6) {
    showMessage('Введите 6-значный код.');
    return;
  }

  setLoading(verifyOtpBtn, verifySpinner, true);
  showMessage('', '');

  try {
    const response = await fetch(OTP_VERIFY_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: currentEmail, code })
    });

    const data = await response.json();
    if (!response.ok) {
        showMessage(data.detail || 'Неверный код. Попробуйте снова.');
        return;
    }

    // Save auth data
    saveAuthData(data);

    // GA4: идентификация пользователя и трекинг входа
    const userId = data.user && data.user.id ? data.user.id : null;
    if (userId && typeof identifyUser === 'function') identifyUser(userId);
    if (typeof trackEvent === 'function') {
      trackEvent('login', { method: 'email', user_id: userId || 'unknown' });
    }

    showMessage('Вход выполнен успешно! Перенаправление...', 'success');

    setTimeout(() => {
      window.location.href = getNextUrl();
    }, 1000);

  } catch (error) {
    showMessage('Ошибка подключения. Попробуйте позже.');
  } finally {
    setLoading(verifyOtpBtn, verifySpinner, false);
  }
}

function handleChangeEmail() {
    step2Form.classList.add('hidden');
    step1Form.classList.remove('hidden');
    step2Form.reset();
    showMessage('');

    if (googleLoginBtn) googleLoginBtn.style.display = 'flex';
    if (divider) divider.style.display = 'flex';
}

// ============================================================
// Google OAuth Login
// ============================================================

async function handleGoogleLogin() {
  googleLoginBtn.setAttribute('disabled', 'disabled');
  showMessage('Перенаправление на Google...', 'success');
  // GA4: трекинг начала входа через Google
  if (typeof trackEvent === 'function') trackEvent('login', { method: 'google' });

  try {
    const response = await fetch(GOOGLE_AUTH_URL);
    const data = await response.json();

    if (!response.ok) {
      showMessage(data.detail || 'Не удалось начать авторизацию через Google.');
      googleLoginBtn.removeAttribute('disabled');
      return;
    }

    if (data.url) {
      window.location.href = data.url;
    } else {
      showMessage('Ошибка: не получен URL для авторизации.');
      googleLoginBtn.removeAttribute('disabled');
    }

  } catch (error) {
    console.error('Google login error:', error);
    showMessage('Ошибка подключения к серверу. Попробуйте позже.');
    googleLoginBtn.removeAttribute('disabled');
  }
}

// ============================================================
// Event Listeners
// ============================================================

if (step1Form) step1Form.addEventListener('submit', (e) => safeSubmit(handleSendOtp, e));
if (step2Form) step2Form.addEventListener('submit', (e) => safeSubmit(handleVerifyOtp, e));
if (changeEmailBtn) changeEmailBtn.addEventListener('click', handleChangeEmail);
if (googleLoginBtn) googleLoginBtn.addEventListener('click', (e) => safeSubmit(handleGoogleLogin, e));

// Если уже авторизован — редирект на целевую страницу
if (isAuthenticated()) {
  window.location.replace(getNextUrl());
}
