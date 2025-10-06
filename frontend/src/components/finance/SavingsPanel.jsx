import React, { useEffect, useState } from 'react';
import { log } from '../../utils/logger.js';
import '../SharedStyles.css';
import { getUser } from '../../utils/auth.js';
import { getAccounts as fetchAccounts, getSavings, depositSavings, withdrawSavings } from '../../utils/financeApi.js';

export default function SavingsPanel() {
    const [bucket, setBucket] = useState(null);
    const [amount, setAmount] = useState('');
    const [loading, setLoading] = useState(true);

    const fetchBucket = async () => {
        log('SavingsPanel: fetching bucket');
        try {
            const user = getUser();
            if (!user?.id) {
                setBucket({ balance: 0 });
                setLoading(false);
                return;
            }

            const [accRes, savRes] = await Promise.all([
                fetchAccounts(user.id),
                getSavings(user.id)
            ]);
            const savingsBal = parseFloat(savRes.data?.balance || 0);
            const sbAccount = (accRes.data || []).find((a) => a.type === 'SAVINGS');
            if (sbAccount) sbAccount.balance = savingsBal;
            setBucket({ balance: savingsBal });
        } catch (e) {
            console.error(e);
            setBucket({ balance: 0 });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchBucket(); }, []);

    const handleAction = async (action) => {
        try {
            const user = getUser();
            if (!user?.id) return;
            const amt = parseFloat(amount);
            if (Number.isNaN(amt) || amt <= 0) {
                alert('Enter a valid amount');
                return;
            }
            log(`SavingsPanel action: ${action}`, { amount: amt });
            if (action === 'deposit') {
                await depositSavings({ userId: user.id, amount: amt });
            } else {
                await withdrawSavings({ userId: user.id, amount: amt });
            }
            await fetchBucket();
            setAmount('');
        } catch (e) {
            alert(e.response?.data?.error || 'Operation failed');
            console.error(e);
        }
    };

    if (loading) {
        return (
            <div style={{ padding: '2rem' }}>
                <div className="crash-pay-glass-card" style={{ padding: '2rem' }}>
                    Loading savings…
                </div>
            </div>
        );
    }

    return (
        <div style={{ padding: '2rem' }}>
            <div className="crash-pay-glass-card" style={{ padding: '2rem' }}>
                <h3 style={{ color: 'var(--text-light)', marginBottom: '1.5rem' }}>Savings Bucket</h3>
                <p style={{ color: 'var(--text-light)', marginBottom: '1rem' }}>
                    Balance: ${parseFloat(bucket.balance || 0).toLocaleString()}
                </p>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <input
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        placeholder="Amount"
                        style={{
                            padding: '0.5rem',
                            borderRadius: '8px',
                            border: '1px solid var(--glass-border)',
                            background: 'var(--glass-bg)',
                            color: 'var(--text-light)',
                            flex: 1
                        }}
                    />
                    <button
                        onClick={() => handleAction('deposit')}
                        style={{
                            padding: '0.5rem 1rem',
                            borderRadius: '8px',
                            border: 'none',
                            background: 'var(--accent-gold)',
                            color: '#000',
                            cursor: 'pointer'
                        }}
                    >
                        Deposit
                    </button>
                    <button
                        onClick={() => handleAction('withdraw')}
                        style={{
                            padding: '0.5rem 1rem',
                            borderRadius: '8px',
                            border: 'none',
                            background: 'var(--primary-blue)',
                            color: 'white',
                            cursor: 'pointer'
                        }}
                    >
                        Withdraw
                    </button>
                </div>
            </div>
        </div>
    );
}
