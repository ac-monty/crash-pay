import React, { useState, useEffect } from 'react';
import { useNavigate, Outlet } from 'react-router-dom';
import BankingSidebar from './BankingSidebar';
import SharedLogo from '../SharedLogo';
import PageWrapper from '../PageWrapper';
import FloatingChatAssistant from '../FloatingChatAssistant';
import './FinanceStyles.css';

export default function BankingLayout() {
    const [user, setUser] = useState(null);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        const token = localStorage.getItem('bankingToken');
        const userData = localStorage.getItem('currentUser');

        if (!token || !userData) {
            navigate('/banking/login');
            return;
        }

        const parsedUser = JSON.parse(userData);
        setUser(parsedUser);
    }, [navigate]);

    const logout = () => {
        localStorage.removeItem('bankingToken');
        localStorage.removeItem('currentUser');
        // Ensure chat history does not leak between users
        localStorage.removeItem('bankingChatMessages');
        localStorage.removeItem('bankingChatSessionId');
        navigate('/banking/login');
        window.location.reload();
    };

    const handleSidebarToggle = (collapsed) => {
        setSidebarCollapsed(collapsed);
    };

    if (!user) {
        return (
            <PageWrapper showBackground={true}>
                <div className="crash-pay-glass-card">Loading...</div>
            </PageWrapper>
        );
    }

    return (
        <PageWrapper showBackground={true}>
            {/* Top Navigation */}
            <nav style={{
                background: 'var(--glass-bg)',
                backdropFilter: 'blur(20px)',
                border: 'none',
                borderBottom: '1px solid var(--glass-border)',
                padding: '1rem 2rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                zIndex: 100
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <SharedLogo size="small" showText={false} />
                    <span style={{
                        fontSize: '1.2rem',
                        fontWeight: '700',
                        color: 'var(--accent-gold)',
                        fontFamily: 'Inter, sans-serif'
                    }}>
                        CRASH PAY
                    </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <span style={{
                        color: 'var(--text-light)',
                        fontFamily: 'Inter, sans-serif',
                        fontSize: '0.9rem'
                    }}>
                        Welcome, {user?.name}
                    </span>
                    <button
                        onClick={logout}
                        style={{
                            background: 'linear-gradient(135deg, var(--primary-blue), var(--primary-blue-dark))',
                            border: 'none',
                            borderRadius: '8px',
                            color: 'white',
                            padding: '0.5rem 1rem',
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            fontWeight: '500',
                            transition: 'all 0.3s ease',
                            fontFamily: 'Inter, sans-serif'
                        }}
                    >
                        Sign Out
                    </button>
                </div>
            </nav>

            {/* Sidebar + Content Layout */}
            <div style={{ display: 'flex', position: 'relative' }}>
                <BankingSidebar onSidebarToggle={handleSidebarToggle} />
                <div className={`main-content-with-sidebar ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
                    <Outlet context={{ user }} />
                </div>
            </div>

            {/* Floating Chat Assistant - available on all banking pages */}
            <FloatingChatAssistant />
        </PageWrapper>
    );
}