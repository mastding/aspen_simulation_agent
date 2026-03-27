const TOKEN_KEY = 'aspen.auth.token';
const USER_KEY = 'aspen.auth.user';
const AUTH_EVENT_NAME = 'aspen:auth-changed';

function emitAuthChange(type, detail = {}) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(AUTH_EVENT_NAME, {
    detail: {
      type,
      ts: Date.now(),
      ...detail,
    },
  }));
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token || '');
}

export function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export function setUser(user) {
  const previousUser = getUser();
  localStorage.setItem(USER_KEY, JSON.stringify(user || null));
  emitAuthChange('user-set', {
    previousUserId: previousUser?.user_id || null,
    userId: user?.user_id || null,
  });
}

export function clearAuth() {
  const previousUser = getUser();
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  emitAuthChange('cleared', {
    previousUserId: previousUser?.user_id || null,
  });
}

export function isLoggedIn() {
  return !!getToken();
}

export function isAdmin() {
  const user = getUser();
  return user?.role === "admin";
}
