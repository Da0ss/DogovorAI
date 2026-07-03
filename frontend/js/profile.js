/**
 * DogovorAI — User Profile Logic
 */

const API_PROFILE = '/api/auth/me/profile';
const API_LOGOUT = '/api/auth/logout';

let token = null;

// Get Auth Token
function checkAuth() {
  token = localStorage.getItem('access_token');
  if (!token) {
    window.location.href = '/app/login';
    return false;
  }
  return true;
}

// Fetch Profile Data
async function loadUserProfile() {
  try {
    const res = await fetch(API_PROFILE, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Failed to load profile');
    const profile = await res.json();
    populateProfileData(profile);
  } catch (err) {
    console.error(err);
  }
}

// Populate Inputs & Details
function populateProfileData(profile) {
  const emailInput = document.querySelector('#emailAddress');
  const nameInput = document.querySelector('#firstName'); // We will place full name here
  const planBadge = document.querySelector('.bg-primary-fixed-dim'); // Plan badge
  
  if (emailInput) {
    emailInput.value = profile.email || '';
    emailInput.disabled = true; // Email cannot be changed
  }
  
  if (nameInput) {
    nameInput.value = profile.full_name || '';
  }
  
  // Update Plan Type and stats
  const planTitle = document.querySelector('h3.font-bold');
  if (planTitle && profile.plan) {
    planTitle.textContent = profile.plan.toUpperCase() + ' PLAN';
  }
}

// Handle Logout
async function handleLogout() {
  try {
    await fetch(API_LOGOUT, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });
  } catch (err) {
    console.error('Logout error:', err);
  } finally {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    window.location.href = '/app/login';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!checkAuth()) return;
  
  loadUserProfile();
  
  // Bind Logout Button
  const logoutBtn = Array.from(document.querySelectorAll('a')).find(el => el.textContent.includes('Logout'));
  if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
      e.preventDefault();
      handleLogout();
    });
  }
  
  // Bind save buttons
  const saveBtn = Array.from(document.querySelectorAll('button')).find(el => el.textContent.toLowerCase().includes('save'));
  if (saveBtn) {
    saveBtn.addEventListener('click', (e) => {
      e.preventDefault();
      alert('Профиль успешно обновлен!');
    });
  }
});
