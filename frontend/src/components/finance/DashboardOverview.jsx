import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getAccounts, getSavings } from '../../utils/financeApi.js';

export default function DashboardOverview() {
    const { user } = useOutletContext();
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [totalBalance, setTotalBalance] = useState(user?.balance || 0);

    useEffect(() => {
        if (user?.id) {
            fetchTransactions(user.id);
            fetchTotalBalance(user.id);
        }
    }, [user]);

    const fetchTotalBalance = async (userId) => {
        try {
            const [accRes, savRes] = await Promise.all([
                getAccounts(userId),
                getSavings(userId)
            ]);
            const accTotal = (accRes.data || []).reduce((sum, a) => sum + parseFloat(a.balance), 0);
            const savingsBal = parseFloat(savRes.data?.balance || 0);
            setTotalBalance(accTotal + savingsBal);
        } catch (e) {
            console.error('Failed to fetch balances', e);
        }
    };

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

    if (loading) {
        return <div style={{ padding: '2rem' }}>Loading dashboard...</div>;
    }

    return (
        <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
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
                        ${totalBalance.toLocaleString()}
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
                            <strong style={{ color: 'var(--accent-gold)' }}>Account ID:</strong> {user?.id}
                        </p>
                    </div>
                </div>
            </div>

            {/* Recent Transactions */}
            <div style={{
                background: 'var(--glass-bg)',
                backdropFilter: 'blur(20px)',
                border: '1px solid var(--glass-border)',
                borderRadius: '24px',
                boxShadow: 'var(--shadow-intense)',
                padding: '2rem'
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
                    <div style={{
                        textAlign: 'center',
                        padding: '3rem',
                        color: 'rgba(248, 250, 252, 0.6)',
                        fontFamily: 'Inter, sans-serif'
                    }}>
                        <div style={{ marginBottom: '1rem' }}>
                            <svg
                                viewBox="0 0 30 30"
                                style={{
                                    width: '3rem',
                                    height: '3rem',
                                    fill: 'var(--accent-gold)'
                                }}
                            >
                                <path d="M26.2,23.4l-4.2,2.8v-1.4h-6.65l2.8-2.8h3.85v-1.4l4.2,2.8Z" />
                                <path d="M3.8,6.6l4.2-2.8v1.4h6.65l-2.8,2.8h-3.85v1.4l-4.2-2.8Z" />
                                <path d="M17.44,3.8L3.8,17.44l8.76,8.76,13.64-13.64L17.44,3.8ZM5.75,17.44l11.69-11.69,6.82,6.82-11.69,11.69-6.82-6.82Z" />
                                <path d="M9.64,17.44l-.98.98,2.93,2.93.98-.98,1.04.97,3.84-3.89c-.62.62-1.48,1.01-2.44,1.01-1.9,0-3.45-1.54-3.45-3.45,0-.95.39-1.81,1.01-2.44l-3.89,3.84.97,1.04Z" />
                                <path d="M21.33,11.6l-2.93-2.93-.98.98-1.02-.98-3.84,3.89c.62-.62,1.48-1.01,2.44-1.01,1.9,0,3.45,1.54,3.45,3.45,0,.95-.39,1.81-1.01,2.44l3.89-3.84-.98-.98.98-1.02Z" />
                            </svg>
                        </div>
                        <h3 style={{ color: 'var(--accent-gold)', marginBottom: '0.5rem' }}>No Transactions Yet</h3>
                        <p>No transactions found for your account. Contact the admin to generate sample transactions or start using your account.</p>
                    </div>
                ) : (
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr>
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
                                        textAlign: 'left',
                                        color: 'var(--accent-gold)',
                                        fontSize: '0.9rem',
                                        fontWeight: '600'
                                    }}>
                                        Account
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
                                            color: 'var(--text-light)',
                                            fontSize: '0.9rem'
                                        }}>
                                            {tx.accountType
                                                ? (String(tx.accountType).toLowerCase() === 'checking'
                                                    ? 'Checking'
                                                    : String(tx.accountType).toLowerCase() === 'savings'
                                                        ? 'Savings'
                                                        : tx.accountType)
                                                : '—'}
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
    );
}