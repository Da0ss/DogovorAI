const API_BASE = '/api/auth';
const LOGIN_URL = `${API_BASE}/login`;
const loginForm = document.querySelector('#loginForm');
const loginButton = document.querySelector('#loginButton');
const loginSpinner = document.querySelector('#loginSpinner');
const messageElement = document.querySelector('#message');

// Auth utilities
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

function logout() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  window.location.href = '/app';
}

function getAuthHeaders() {
  const token = localStorage.getItem('access_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function setLoading(button, spinner, isLoading) {
  if (isLoading) {
    button.classList.add('loading');
    button.setAttribute('disabled', 'disabled');
  } else {
    button.classList.remove('loading');
    button.removeAttribute('disabled');
  }
}

function showMessage(text, type = 'error') {
  messageElement.textContent = text;
  messageElement.className = `message ${type}`;
}

async function handleLogin(event) {
  event.preventDefault();

  const email = loginForm.email.value.trim();
  const password = loginForm.password.value;

  if (!email || !password) {
    showMessage('Пожалуйста, заполните все поля.');
    return;
  }

  setLoading(loginButton, loginSpinner, true);
  showMessage('', '');

  try {
    const response = await fetch(LOGIN_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();
    if (!response.ok) {
      showMessage(data.detail || 'Не удалось войти. Проверьте email и пароль.');
      return;
    }

    // Save auth data
    saveAuthData(data);

    showMessage('Вход выполнен успешно! Перенаправление...', 'success');

    // Redirect to main page after short delay
    setTimeout(() => {
      window.location.href = '/app';
    }, 1000);

  } catch (error) {
    showMessage('Ошибка подключения. Попробуйте позже.');
  } finally {
    setLoading(loginButton, loginSpinner, false);
  }
}

loginForm.addEventListener('submit', handleLogin);

// Check if already authenticated
if (isAuthenticated()) {
  window.location.href = '/app';
}
