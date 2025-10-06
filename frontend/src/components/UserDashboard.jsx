import React, { useState, useEffect } from 'react';
import BankingSidebar from './finance/BankingSidebar';
import { useNavigate } from 'react-router-dom';
import SharedLogo from './SharedLogo';
import PageWrapper from './PageWrapper';
import FloatingChatAssistant from './FloatingChatAssistant';
import './SharedStyles.css';

function UserDashboard() {
    const [user, setUser] = useState(null);
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);
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
        fetchTransactions(parsedUser.id);
    }, [navigate]);

    const fetchTransactions = async (userId) => {
        try {
            const res = await fetch(`/api/banking/transactions/${userId}`);
            const data = await res.json();
            if (data.ok) {
                setTransactions(data.transactions);
            }
        } catch (err) {
            console.error('Failed to fetch transactions:', err);
        } finally {
            setLoading(false);
        }
    };

    const logout = () => {
        localStorage.removeItem('bankingToken');
        localStorage.removeItem('currentUser');
        // Remove any persisted chat messages/session
        localStorage.removeItem('bankingChatMessages');
        localStorage.removeItem('bankingChatSessionId');
        navigate('/banking/login');
        window.location.reload();
    };

    if (loading) {
        return (
            <PageWrapper showBackground={true}>
                <div className="crash-pay-page-container">
                    <div className="crash-pay-page-card" style={{
                        background: 'var(--glass-bg)',
                        backdropFilter: 'blur(20px)',
                        border: '1px solid var(--glass-border)',
                        borderRadius: '24px',
                        boxShadow: 'var(--shadow-intense)',
                        padding: '3rem',
                        width: '100%',
                        maxWidth: '450px',
                        position: 'relative'
                    }}>
                        <div style={{ textAlign: 'center', color: 'var(--text-light)' }}>
                            <div className="crash-pay-loading" style={{ margin: '0 auto 1rem' }}></div>
                            Loading your account...
                        </div>
                    </div>
                </div>
            </PageWrapper>
        );
    }

    return (
        <PageWrapper showBackground={true}>
            {/* Navigation */}
            <nav style={{
                background: 'var(--glass-bg)',
                backdropFilter: 'blur(20px)',
                border: 'none',
                borderBottom: '1px solid var(--glass-border)',
                padding: '1rem 2rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                position: 'sticky',
                top: 0,
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
                        onMouseOver={(e) => {
                            e.target.style.background = 'linear-gradient(135deg, var(--accent-gold), var(--accent-gold-light))';
                            e.target.style.transform = 'translateY(-1px)';
                        }}
                        onMouseOut={(e) => {
                            e.target.style.background = 'linear-gradient(135deg, var(--primary-blue), var(--primary-blue-dark))';
                            e.target.style.transform = 'translateY(0)';
                        }}
                    >
                        Sign Out
                    </button>
                </div>
            </nav>

            {/* Dashboard Content */}
            <div style={{ display: 'flex' }}>
                <BankingSidebar onLogout={logout} />
                <div style={{ flex: 1, padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
                    {/* Account Summary Cards */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                        gap: '2rem',
                        marginBottom: '3rem'
                    }}>
                        {/* Balance Card */}
                        <div style={{
                            padding: '2rem',
                            background: 'var(--glass-bg)',
                            backdropFilter: 'blur(20px)',
                            border: '1px solid var(--glass-border)',
                            borderRadius: '24px',
                            boxShadow: 'var(--shadow-intense)',
                            position: 'relative'
                        }}>
                            <div className="crash-pay-security-badge" style={{ top: '1rem', right: '1rem' }}>
                                <div className="crash-pay-security-icon"></div>
                                Secured
                            </div>
                            <h2 style={{
                                color: 'var(--text-light)',
                                fontSize: '1.2rem',
                                marginBottom: '1rem',
                                fontFamily: 'Inter, sans-serif'
                            }}>
                                Account Balance
                            </h2>
                            <div style={{
                                fontSize: '2.5rem',
                                fontWeight: 'bold',
                                color: 'var(--accent-gold)',
                                marginBottom: '0.5rem',
                                fontFamily: 'Inter, sans-serif'
                            }}>
                                ${user?.balance?.toLocaleString()}
                            </div>
                            <p style={{
                                color: 'rgba(248, 250, 252, 0.7)',
                                fontSize: '0.9rem',
                                fontFamily: 'Inter, sans-serif'
                            }}>
                                Available Balance
                            </p>
                        </div>

                        {/* Account Info Card */}
                        <div style={{
                            padding: '2rem',
                            background: 'var(--glass-bg)',
                            backdropFilter: 'blur(20px)',
                            border: '1px solid var(--glass-border)',
                            borderRadius: '24px',
                            boxShadow: 'var(--shadow-intense)',
                            position: 'relative'
                        }}>
                            <h3 style={{
                                color: 'var(--text-light)',
                                fontSize: '1.2rem',
                                marginBottom: '1rem',
                                fontFamily: 'Inter, sans-serif'
                            }}>
                                Account Information
                            </h3>
                            <div style={{ color: 'rgba(248, 250, 252, 0.8)', lineHeight: '1.6', fontFamily: 'Inter, sans-serif' }}>
                                <p style={{ marginBottom: '0.5rem' }}>
                                    <strong style={{ color: 'var(--accent-gold)' }}>Account Holder:</strong> {user?.name}
                                </p>
                                <p style={{ marginBottom: '0.5rem' }}>
                                    <strong style={{ color: 'var(--accent-gold)' }}>SSN:</strong> {user?.ssn}
                                </p>
                                <p>
                                    <strong style={{ color: 'var(--accent-gold)' }}>Account ID:</strong> {user?.id?.substring(0, 8)}...
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Transactions Section */}
                    <div style={{
                        padding: '2rem',
                        background: 'var(--glass-bg)',
                        backdropFilter: 'blur(20px)',
                        border: '1px solid var(--glass-border)',
                        borderRadius: '24px',
                        boxShadow: 'var(--shadow-intense)',
                        position: 'relative'
                    }}>
                        <h2 style={{
                            color: 'var(--text-light)',
                            fontSize: '1.5rem',
                            marginBottom: '1.5rem',
                            fontFamily: 'Inter, sans-serif'
                        }}>
                            Recent Transactions
                        </h2>

                        {transactions.length === 0 ? (
                            <div className="crash-pay-demo-section">
                                <div className="crash-pay-demo-title">
                                    📊 No Transactions Yet
                                </div>
                                <div className="crash-pay-demo-info">
                                    No transactions found for your account. Contact the admin to generate sample transactions or start using your account.
                                </div>
                            </div>
                        ) : (
                            <div style={{ overflowX: 'auto' }}>
                                <table style={{
                                    width: '100%',
                                    borderCollapse: 'collapse',
                                    fontFamily: 'Inter, sans-serif'
                                }}>
                                    <thead>
                                        <tr style={{ borderBottom: '1px solid var(--glass-border)' }}>
                                            <th style={{
                                                padding: '1rem',
                                                textAlign: 'left',
                                                color: 'var(--accent-gold)',
                                                fontSize: '0.9rem',
                                                fontWeight: '600'
                                            }}>
                                                Date
                                            </th>
                                            <th style={{
                                                padding: '1rem',
                                                textAlign: 'left',
                                                color: 'var(--accent-gold)',
                                                fontSize: '0.9rem',
                                                fontWeight: '600'
                                            }}>
                                                Description
                                            </th>
                                            <th style={{
                                                padding: '1rem',
                                                textAlign: 'right',
                                                color: 'var(--accent-gold)',
                                                fontSize: '0.9rem',
                                                fontWeight: '600'
                                            }}>
                                                Amount
                                            </th>
                                            <th style={{
                                                padding: '1rem',
                                                textAlign: 'center',
                                                color: 'var(--accent-gold)',
                                                fontSize: '0.9rem',
                                                fontWeight: '600'
                                            }}>
                                                Status
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {transactions.map((tx) => (
                                            <tr key={tx.id} style={{
                                                borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                                                transition: 'background 0.3s ease'
                                            }}>
                                                <td style={{
                                                    padding: '1rem',
                                                    color: 'var(--text-light)',
                                                    fontSize: '0.9rem'
                                                }}>
                                                    {new Date(tx.createdAt).toLocaleDateString()}
                                                </td>
                                                <td style={{
                                                    padding: '1rem',
                                                    color: 'var(--text-light)',
                                                    fontSize: '0.9rem'
                                                }}>
                                                    {tx.description}
                                                </td>
                                                <td style={{
                                                    padding: '1rem',
                                                    textAlign: 'right',
                                                    color: tx.amount >= 0 ? '#4ade80' : '#f87171',
                                                    fontWeight: '600',
                                                    fontSize: '0.9rem'
                                                }}>
                                                    {tx.amount >= 0 ? '+' : ''}${tx.amount}
                                                </td>
                                                <td style={{ padding: '1rem', textAlign: 'center' }}>
                                                    <span style={{
                                                        padding: '0.25rem 0.75rem',
                                                        borderRadius: '12px',
                                                        fontSize: '0.8rem',
                                                        fontWeight: '500',
                                                        background: tx.status.toLowerCase() === 'settled' ? 'rgba(34, 197, 94, 0.1)' :
                                                            tx.status.toLowerCase() === 'pending' ? 'rgba(245, 158, 11, 0.1)' :
                                                                'rgba(220, 38, 38, 0.1)',
                                                        color: tx.status.toLowerCase() === 'settled' ? '#4ade80' :
                                                            tx.status.toLowerCase() === 'pending' ? '#fbbf24' :
                                                                '#f87171',
                                                        border: `1px solid ${tx.status.toLowerCase() === 'settled' ? 'rgba(34, 197, 94, 0.3)' :
                                                            tx.status.toLowerCase() === 'pending' ? 'rgba(245, 158, 11, 0.3)' :
                                                                'rgba(220, 38, 38, 0.3)'}`
                                                    }}>
                                                        {tx.status}
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Floating Chat Assistant */}
            <FloatingChatAssistant />
        </PageWrapper>
    );
}

export default UserDashboard; 