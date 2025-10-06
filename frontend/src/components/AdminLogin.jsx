import React, { useState } from 'react';
import PageWrapper from './PageWrapper';
import Icon from './Icon';
import './SharedStyles.css';
import { setAdminToken, setAdminUser, isAdminLoggedIn } from '../utils/auth.js';

export default function AdminLogin() {
    const [form, setForm] = useState({ username: '', password: '' });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const res = await fetch('/api/admin/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form)
            });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || 'Login failed');
            }
            if (data.token) {
                setAdminToken(data.token);
                setAdminUser({ username: form.username, role: 'admin' });
                window.location.href = '/admin/dashboard';
            } else {
                throw new Error('Missing token in response');
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <PageWrapper showBackground={true}>
            <div className="crash-pay-page-container">
                <div className="crash-pay-glass-card crash-pay-page-card" style={{ maxWidth: '420px' }}>
                    <h1 className="crash-pay-page-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Icon name="dashboard" size="large" /> Admin Login
                    </h1>
                    <form onSubmit={handleSubmit} className="crash-pay-form">
                        <div className="crash-pay-form-group">
                            <label className="crash-pay-form-label">Username</label>
                            <input
                                type="text"
                                className="crash-pay-form-input"
                                value={form.username}
                                onChange={(e) => setForm({ ...form, username: e.target.value })}
                                autoFocus
                                required
                            />
                        </div>
                        <div className="crash-pay-form-group">
                            <label className="crash-pay-form-label">Password</label>
                            <input
                                type="password"
                                className="crash-pay-form-input"
                                value={form.password}
                                onChange={(e) => setForm({ ...form, password: e.target.value })}
                                required
                            />
                        </div>
                        {error && (
                            <div className="crash-pay-error" style={{ marginTop: '0.5rem' }}>
                                {error}
                            </div>
                        )}
                        <div className="crash-pay-form-actions">
                            <button type="submit" className="crash-pay-btn crash-pay-btn-primary" disabled={loading}>
                                {loading ? (
                                    <>
                                        <div className="crash-pay-loading"></div>
                                        Signing in...
                                    </>
                                ) : (
                                    <>
                                        <Icon name="enter" size="default" />
                                        Sign In
                                    </>
                                )}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </PageWrapper>
    );
}


