/**
 * DogovorAI — Auth Guard
 * Protects private pages by checking the access token.
 */

(function () {
  const token = localStorage.getItem('access_token');
  const currentPath = window.location.pathname;

  // Paths that require authentication
  const privatePaths = [
    '/app',
    '/app/profile',
    '/app/history',
    '/app/metrics',
    '/app/pricing'
  ];

  const isPrivate = privatePaths.some(path => currentPath === path || currentPath.startsWith(path + '/'));

  if (isPrivate && !token) {
    // Redirect to login page
    window.location.href = `/app/login?next=${encodeURIComponent(currentPath)}`;
  }
})();
