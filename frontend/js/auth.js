/**
 * DogovorAI — Authentication Logic
 */

const API_AUTH = '/api/auth';

// Helper to save session details
function saveAuthData(data) {
  if (data.session) {
    localStorage.setItem('access_token', data.session.access_token);
    localStorage.setItem('refresh_token', data.session.refresh_token);
  }
  if (data.user) {
    localStorage.setItem('user', JSON.stringify(data.user));
  }
}

// Helper to get Redirect Next url
function getNextUrl() {
  const params = new URLSearchParams(window.location.search);
  const next = params.get('next');
  return (next && next.startsWith('/')) ? next : '/app';
}

// Display error or status message
function showAuthMessage(text, isError = true) {
  const msgEl = document.querySelector('#message');
  if (msgEl) {
    msgEl.textContent = text;
    msgEl.className = `text-sm font-medium ${isError ? 'text-error' : 'text-secondary'} mt-4 block text-center`;
  } else {
    // Fallback if message element not found, search for common placeholders or log
    console.error(text);
  }
}

// Login with email and password
async function loginWithPassword(email, password) {
  try {
    const res = await fetch(`${API_AUTH}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Неверный email или пароль.');
    }
    saveAuthData(data);
    return data;
  } catch (err) {
    showAuthMessage(err.message);
    throw err;
  }
}

// Register with email and password
async function registerWithPassword(email, password, consent = true, recaptchaToken = null) {
  try {
    const res = await fetch(`${API_AUTH}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, consent, recaptcha_token: recaptchaToken })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Ошибка регистрации.');
    }
    saveAuthData(data);
    return data;
  } catch (err) {
    showAuthMessage(err.message);
    throw err;
  }
}

// Expose on window so inline scripts can call it
window.registerWithPassword = registerWithPassword;

// Initiate Google Login
async function initGoogleLogin() {
  try {
    const res = await fetch(`${API_AUTH}/google`);
    const data = await res.json();
    if (data.url) {
      if (data.code_verifier) {
        document.cookie = `sb-code-verifier=${data.code_verifier}; path=/; max-age=3600; SameSite=Lax; Secure`;
      }
      window.location.href = data.url;
    } else {
      throw new Error('OAuth URL not returned from server');
    }
  } catch (err) {
    showAuthMessage('Google Login failed to initialize: ' + err.message);
  }
}

// Handle OAuth Callback
async function handleOAuthCallback() {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');
  const error = urlParams.get('error');

  if (error) {
    showAuthMessage(`OAuth Error: ${error}`);
    setTimeout(() => { window.location.href = '/app/login'; }, 3000);
    return;
  }

  if (!code) {
    showAuthMessage('Code parameter is missing.');
    setTimeout(() => { window.location.href = '/app/login'; }, 3000);
    return;
  }

  try {
    const res = await fetch(`${API_AUTH}/google/callback?code=${code}`);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'OAuth callback processing failed.');
    }
    saveAuthData(data);
    window.location.href = '/app';
  } catch (err) {
    showAuthMessage(err.message);
    setTimeout(() => { window.location.href = '/app/login'; }, 4000);
  }
}

// Hook up event listeners on page load
document.addEventListener('DOMContentLoaded', () => {
  // Inject message container dynamically if missing
  const form = document.querySelector('form');
  if (form && !document.querySelector('#message')) {
    const msgDiv = document.createElement('div');
    msgDiv.id = 'message';
    form.appendChild(msgDiv);
  }

  // Bind Google OAuth Buttons
  const googleBtns = document.querySelectorAll('button img[alt="Google Logo"], button img[alt="Google"]');
  googleBtns.forEach(btn => {
    const parentBtn = btn.closest('button');
    if (parentBtn) {
      parentBtn.addEventListener('click', (e) => {
        e.preventDefault();
        initGoogleLogin();
      });
    }
  });

  // Handle Sign In (Login Page)
  const emailInput = document.querySelector('#email');
  const passwordInput = document.querySelector('#password');
  const loginSubmitBtn = document.querySelector('form button[type="submit"]');

  if (loginSubmitBtn && emailInput && passwordInput && window.location.pathname.includes('/login')) {
    loginSubmitBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const email = emailInput.value.trim();
      const password = passwordInput.value;

      if (!email || !password) {
        showAuthMessage('Пожалуйста, заполните все поля.');
        return;
      }

      loginSubmitBtn.disabled = true;
      const originalText = loginSubmitBtn.innerHTML;
      loginSubmitBtn.innerHTML = 'Вход...';

      try {
        await loginWithPassword(email, password);
        window.location.href = getNextUrl();
      } catch (err) {
        loginSubmitBtn.disabled = false;
        loginSubmitBtn.innerHTML = originalText;
      }
    });
  }

  // Handle Sign Up (Register Page)
  const regEmailInput = document.querySelector('#email');
  const regPasswordInput = document.querySelector('#password');
  const consentCheckbox = document.querySelector('input[type="checkbox"]');
  const registerSubmitBtn = document.querySelector('form button[type="submit"]');

  if (registerSubmitBtn && regEmailInput && regPasswordInput && window.location.pathname.includes('/register')) {
    registerSubmitBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const email = regEmailInput.value.trim();
      const password = regPasswordInput.value;
      const consent = consentCheckbox ? consentCheckbox.checked : true;

      if (!email || !password) {
        showAuthMessage('Пожалуйста, заполните все поля.');
        return;
      }

      if (!consent) {
        showAuthMessage('Вы должны согласиться с условиями использования.');
        return;
      }

      registerSubmitBtn.disabled = true;
      const originalText = registerSubmitBtn.innerHTML;
      registerSubmitBtn.innerHTML = 'Регистрация...';

      try {
        await registerWithPassword(email, password, consent);
        window.location.href = '/app';
      } catch (err) {
        registerSubmitBtn.disabled = false;
        registerSubmitBtn.innerHTML = originalText;
      }
    });
  }
});
