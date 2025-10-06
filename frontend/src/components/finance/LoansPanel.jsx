import React, { useEffect, useState } from 'react';
import '../SharedStyles.css';
import { getUser } from '../../utils/auth.js';
import { getLoans as apiGetLoans, repayLoan, createLoan } from '../../utils/financeApi.js';

export default function LoansPanel() {
    const [loans, setLoans] = useState([]);
    const [form, setForm] = useState({ amount: '', apr: '12.0' });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const refresh = async () => {
        try {
            const user = getUser();
            if (!user?.id) return;
            const { data } = await apiGetLoans(user.id);
            // Show only active loans so users can apply again once previous is paid
            setLoans((data || []).filter(l => l.status !== 'PAID'));
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => { refresh(); }, []);

    const repay = async (id) => {
        try {
            await repayLoan(id, 100);
            await refresh();
        } catch (e) {
            console.error(e);
        }
    };

    const applyForLoan = async () => {
        try {
            setLoading(true);
            setError('');
            const user = getUser();
            const principal = parseFloat(form.amount);
            const interestRate = parseFloat(form.apr);
            if (!user?.id || Number.isNaN(principal) || principal <= 0 || Number.isNaN(interestRate) || interestRate <= 0) {
                setError('Enter a valid amount and APR');
                setLoading(false);
                return;
            }
            await createLoan({ userId: user.id, principal, interestRate });
            await refresh();
            setForm({ amount: '', apr: form.apr });
        } catch (e) {
            console.error(e);
            setError('Loan application failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ padding: '2rem' }}>
            <div className="crash-pay-glass-card" style={{ padding: '2rem' }}>
                <h3 style={{ color: 'var(--text-light)', marginBottom: '1.5rem' }}>Loans</h3>
                {/* Application */}
                <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', marginBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <label htmlFor="loan-amount" style={{ color: 'var(--text-light)', marginBottom: '0.25rem', fontSize: '0.85rem' }}>Amount</label>
                        <input id="loan-amount" type="number" placeholder="Amount" value={form.amount} onChange={(e) => setForm(prev => ({ ...prev, amount: e.target.value }))}
                            style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }} />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <label htmlFor="loan-apr" style={{ color: 'var(--text-light)', marginBottom: '0.25rem', fontSize: '0.85rem' }}>APR %</label>
                        <input id="loan-apr" type="number" placeholder="APR %" value={form.apr} onChange={(e) => setForm(prev => ({ ...prev, apr: e.target.value }))}
                            style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }} />
                    </div>
                    <button onClick={applyForLoan} disabled={loading}
                        style={{ padding: '0.75rem 1.5rem', borderRadius: '8px', border: 'none', background: 'var(--accent-gold)', color: '#000', cursor: 'pointer' }}>
                        {loading ? 'Applying…' : 'Apply for Loan'}
                    </button>
                </div>
                {error && <p style={{ color: '#f87171', marginBottom: '1rem' }}>{error}</p>}
                {loans.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-light)' }}>
                        <p>No loans found.</p>
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        {loans.map((l) => (
                            <div key={l.id} style={{
                                padding: '1rem',
                                background: 'rgba(255, 255, 255, 0.05)',
                                borderRadius: '8px',
                                border: '1px solid var(--glass-border)',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center'
                            }}>
                                <div style={{ color: 'var(--text-light)' }}>
                                    <strong>${parseFloat(l.outstanding).toLocaleString()}</strong> at {l.interestRate}% — {l.status}
                                </div>
                                {l.status === 'ACTIVE' && (
                                    <button
                                        onClick={() => repay(l.id)}
                                        style={{
                                            padding: '0.5rem 1rem',
                                            borderRadius: '8px',
                                            border: 'none',
                                            background: 'var(--accent-gold)',
                                            color: '#000',
                                            cursor: 'pointer'
                                        }}
                                    >
                                        Repay $100
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
