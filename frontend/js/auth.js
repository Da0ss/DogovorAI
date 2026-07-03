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
  let msgEl = document.querySelector('#message');
  if (!msgEl) {
    // Create message element if missing
    msgEl = document.createElement('div');
    msgEl.id = 'message';
    const form = document.querySelector('form');
    if (form) form.appendChild(msgEl);
  }
  if (msgEl) {
    msgEl.textContent = text;
    msgEl.className = `text-sm font-medium ${isError ? 'text-error' : 'text-secondary'} mt-4 block text-center`;
  } else {
    console.error('[Auth]', text);
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

// Expose on window so inline scripts (register.html) can call it
window.registerWithPassword = registerWithPassword;

// Initiate Google OAuth Login
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
    showAuthMessage('Google Login failed: ' + err.message);
  }
}

// Handle OAuth Callback (used in auth_callback.html)
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
  const path = window.location.pathname;

  // ----- Google OAuth Buttons -----
  // Matches buttons containing "Continue with Google" text (works with both img and SVG icons)
  document.querySelectorAll('button').forEach(btn => {
    if (btn.textContent.trim().includes('Google') && !btn.dataset.googleBound) {
      btn.dataset.googleBound = '1';
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        initGoogleLogin();
      });
    }
  });

  // ----- Login Page -----
  if (path.includes('/login')) {
    const emailInput = document.querySelector('#email');
    const passwordInput = document.querySelector('#password');
    const loginSubmitBtn = document.querySelector('form button[type="submit"]');

    if (loginSubmitBtn && emailInput && passwordInput) {
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
  }

  // ----- Register Page -----
  // Submit is handled by inline script in register.html which calls window.registerWithPassword()
  // No duplicate handler needed here.
});
