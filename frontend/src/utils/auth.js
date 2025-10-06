// Centralised auth utilities for the vulnerable Crash-Pay frontend
// NOTE: this is still intentionally simple (no refresh-token flow) but
// grants us one place to change storage keys / logic later.

export const TOKEN_KEY = 'bankingToken';
export const USER_KEY = 'currentUser';
export const ADMIN_TOKEN_KEY = 'adminToken';
export const ADMIN_USER_KEY = 'adminUser';

// ────────────────────────────────────────────────────────────
// Token helpers
// ────────────────────────────────────────────────────────────
export function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
}

export function isLoggedIn() {
    return !!getToken();
}

// ────────────────────────────────────────────────────────────
// User helpers (kept in localStorage for the lab)
// ────────────────────────────────────────────────────────────
export function getUser() {
    const raw = localStorage.getItem(USER_KEY);
    try {
        return raw ? JSON.parse(raw) : null;
    } catch (_) {
        return null;
    }
}

export function setUser(userObj) {
    if (userObj) localStorage.setItem(USER_KEY, JSON.stringify(userObj));
}

export function clearUser() {
    localStorage.removeItem(USER_KEY);
}

export function logout() {
    clearToken();
    clearUser();
    // Clear chat data so that messages are not shared across users
    localStorage.removeItem('bankingChatMessages');
    localStorage.removeItem('bankingChatSessionId');
}

// ────────────────────────────────────────────────────────────
// Admin token helpers
// ────────────────────────────────────────────────────────────
export function getAdminToken() {
    return localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function setAdminToken(token) {
    if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken() {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function isAdminLoggedIn() {
    return !!getAdminToken();
}

export function getAdminUser() {
    const raw = localStorage.getItem(ADMIN_USER_KEY);
    try {
        return raw ? JSON.parse(raw) : null;
    } catch (_) {
        return null;
    }
}

export function setAdminUser(userObj) {
    if (userObj) localStorage.setItem(ADMIN_USER_KEY, JSON.stringify(userObj));
}

export function clearAdminUser() {
    localStorage.removeItem(ADMIN_USER_KEY);
}

// Convenience helper to fully log out an admin session
export function adminLogout() {
    clearAdminToken();
    clearAdminUser();
}
