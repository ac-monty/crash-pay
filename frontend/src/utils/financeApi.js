import axios from 'axios';
import { getToken, logout } from './auth.js';
import { log } from './logger.js';

const api = axios.create({ baseURL: '/api', withCredentials: true });

// ────────────────────────────────────────────────────────────
// Request interceptor – inject JWT when present
// ────────────────────────────────────────────────────────────
api.interceptors.request.use((config) => {
    log(`API Request → ${config.method?.toUpperCase()} ${config.url}`, config.data);
    const token = getToken();
    if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// ────────────────────────────────────────────────────────────
// Response interceptor – when we hit 401 clear token and bounce to login
// ────────────────────────────────────────────────────────────
api.interceptors.response.use(
    (response) => {
        log(`API Response ← ${response.config.url} ${response.status}`);
        return response;
    },
    (error) => {
        if (error.response && error.response.status === 401) {
            // Token is invalid or expired – wipe and redirect
            logout();
            if (typeof window !== 'undefined') {
                window.location.href = '/banking/login';
            }
        }
        return Promise.reject(error);
    }
);

// Accounts
export const getAccounts = (userId) => api.get('/accounts', { params: { userId } });
export const getAllAccounts = () => api.get('/accounts');

// Users (search)
export const searchUsers = (name) => api.get('/users', { params: { name } });

// Transfers
export const createTransfer = (payload) => api.post('/transfers', payload);

// Savings
export const getSavings = (userId) => api.get(`/savings/${userId}`);
export const depositSavings = (payload) => api.post('/savings/deposit', payload);
export const withdrawSavings = (payload) => api.post('/savings/withdraw', payload);

// Credit Score
export const getCreditScore = (userId) => api.get(`/credit-score/${userId}`);

// Transactions
export const getTransactions = (userId) => api.get('/transactions', { params: { userId } });

// Loans
export const getLoans = (userId) => api.get('/loans', { params: { userId } });
export const repayLoan = (loanId, amount) => api.post(`/loans/${loanId}/repay`, { amount });
export const createLoan = (payload) => api.post('/loans', payload);

// Trading
export const createOrder = (payload) => api.post('/trading/orders', payload);
export const cancelOrder = (orderId) => api.put(`/trading/orders/${orderId}/cancel`);
export const getPositions = () => api.get('/trading/positions');
export const getOrders = () => api.get('/trading/orders');

export default api;
