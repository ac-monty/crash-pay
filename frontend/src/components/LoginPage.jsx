import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import SharedLogo from './SharedLogo';
import './SharedStyles.css';
import { setToken, setUser } from '../utils/auth.js';

function LoginPage() {
    const [credentials, setCredentials] = useState({ identifier: '', password: 'user' });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const res = await fetch(`/api/banking/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(credentials),
            });

            if (res.ok) {
                const data = await res.json();
                if (data.token) {
                    setToken(data.token);
                    setUser(data.user);
                    navigate('/banking/dashboard');
                } else {
                    setError(data.error || 'Login failed');
                }
            } else {
                const errorData = await res.json();
                setError(errorData.error || `Login failed with status: ${res.status}`);
            }
        } catch (err) {
            setError('Connection failed');
            console.error('Banking login error:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleAdminDashboard = () => {
        navigate('/admin/dashboard');
    };

    const handleHelp = () => {
        alert('Help & Support: This is a demo banking interface for security research. Contact the development team for assistance.');
    };

    const handleAboutResearch = () => {
        alert('About Research: This platform is designed for OWASP-LLM security testing and vulnerability research. It contains intentional security flaws for educational purposes.');
    };

    // Auto-fill demo credentials
    const fillDemoCredentials = () => {
        setCredentials({ identifier: 'demo_user', password: 'user' });
    };

    // Enhanced mouse move effect
    useEffect(() => {
        const handleMouseMove = (e) => {
            const shapes = document.querySelectorAll('.shape');
            const x = e.clientX / window.innerWidth;
            const y = e.clientY / window.innerHeight;

            shapes.forEach((shape, index) => {
                const speed = (index + 1) * 0.5;
                const xMove = (x - 0.5) * speed * 20;
                const yMove = (y - 0.5) * speed * 20;

                shape.style.transform = `translate(${xMove}px, ${yMove}px)`;
            });
        };

        document.addEventListener('mousemove', handleMouseMove);
        return () => document.removeEventListener('mousemove', handleMouseMove);
    }, []);

    return (
        <>
            {/* Animated Background */}
            <div className="crash-pay-background">
                <div className="floating-shapes">
                    <div className="shape"></div>
                    <div className="shape"></div>
                    <div className="shape"></div>
                    <div className="shape"></div>
                    <div className="shape"></div>
                    <div className="shape"></div>
                </div>
                <div className="grid-overlay"></div>
            </div>

            {/* Main Login Container */}
            <div className="crash-pay-page-container">
                <div className="crash-pay-glass-card crash-pay-page-card crash-pay-rotating-border">
                    <div className="crash-pay-security-badge">
                        <div className="crash-pay-security-icon"></div>
                        Bank-Grade Security
                    </div>

                    {/* Logo Section */}
                    <div style={{ textAlign: 'center', marginBottom: '2.5rem', position: 'relative', zIndex: 2 }}>
                        <SharedLogo size="large" showText={true} showContainer={true} />
                    </div>

                    {/* Login Form */}
                    <form onSubmit={handleLogin} style={{ position: 'relative', zIndex: 2 }}>
                        <h2 className="crash-pay-form-title">Secure Access Portal</h2>

                        <div className="crash-pay-form-group">
                            <input
                                type="text"
                                className="crash-pay-input-field"
                                placeholder="Username or Account ID"
                                value={credentials.identifier}
                                onChange={(e) => setCredentials(prev => ({ ...prev, identifier: e.target.value }))}
                                required
                            />
                        </div>

                        <div className="crash-pay-form-group">
                            <input
                                type="password"
                                className="crash-pay-input-field"
                                placeholder="Password"
                                value={credentials.password}
                                onChange={(e) => setCredentials(prev => ({ ...prev, password: e.target.value }))}
                                required
                            />
                        </div>

                        {error && <div className="crash-pay-error">{error}</div>}

                        <button type="submit" className="crash-pay-button" disabled={loading}>
                            {loading ? (
                                <>
                                    <div className="crash-pay-loading"></div>
                                    Authenticating...
                                </>
                            ) : (
                                'Access Banking Portal'
                            )}
                        </button>
                    </form>

                    {/* Demo Information */}
                    <div className="crash-pay-demo-section" style={{ marginTop: '1.5rem', position: 'relative', zIndex: 2 }}>
                        <h3 className="crash-pay-demo-title">
                            Research Platform
                        </h3>
                        <div className="crash-pay-demo-info">
                            This is a demo banking interface for security research and testing purposes.
                        </div>
                        <div
                            className="crash-pay-demo-credentials"
                            onClick={fillDemoCredentials}
                            style={{ cursor: 'pointer' }}
                            title="Click to auto-fill credentials"
                        >
                            <p><strong>Demo Account:</strong></p>
                            <p>Username: demo_user</p>
                            <p>Password: user</p>
                        </div>
                    </div>

                    {/* Footer Links */}
                    <div className="crash-pay-footer-links">
                        <button
                            onClick={handleAdminDashboard}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: 'rgba(248, 250, 252, 0.6)',
                                textDecoration: 'none',
                                fontSize: '0.9rem',
                                margin: '0 1rem',
                                transition: 'color 0.3s ease',
                                fontFamily: 'Inter, sans-serif',
                                cursor: 'pointer'
                            }}
                            onMouseOver={(e) => e.target.style.color = 'var(--accent-gold-light)'}
                            onMouseOut={(e) => e.target.style.color = 'rgba(248, 250, 252, 0.6)'}
                        >
                            Admin Center
                        </button>
                        <button
                            onClick={handleHelp}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: 'rgba(248, 250, 252, 0.6)',
                                textDecoration: 'none',
                                fontSize: '0.9rem',
                                margin: '0 1rem',
                                transition: 'color 0.3s ease',
                                fontFamily: 'Inter, sans-serif',
                                cursor: 'pointer'
                            }}
                            onMouseOver={(e) => e.target.style.color = 'var(--accent-gold-light)'}
                            onMouseOut={(e) => e.target.style.color = 'rgba(248, 250, 252, 0.6)'}
                        >
                            Help & Support
                        </button>
                        <button
                            onClick={handleAboutResearch}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: 'rgba(248, 250, 252, 0.6)',
                                textDecoration: 'none',
                                fontSize: '0.9rem',
                                margin: '0 1rem',
                                transition: 'color 0.3s ease',
                                fontFamily: 'Inter, sans-serif',
                                cursor: 'pointer'
                            }}
                            onMouseOver={(e) => e.target.style.color = 'var(--accent-gold-light)'}
                            onMouseOut={(e) => e.target.style.color = 'rgba(248, 250, 252, 0.6)'}
                        >
                            About Research
                        </button>
                    </div>
                </div>
            </div>
        </>
    );
}

export default LoginPage; 