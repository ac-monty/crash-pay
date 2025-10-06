import React, { useEffect, useState } from 'react';
import '../SharedStyles.css';
import { getUser } from '../../utils/auth.js';
import { getAccounts as fetchAccounts, getTransactions as fetchTransactions, createTransfer } from '../../utils/financeApi.js';

export default function AccountsPanel() {
    const [accounts, setAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [transactions, setTransactions] = useState([]);
    const [form, setForm] = useState({ fromAccountId: '', toAccountId: '', amount: '', description: '' });
    const [txLoading, setTxLoading] = useState(false);
    const [transferError, setTransferError] = useState('');

    // External transfer form
    const [extForm, setExtForm] = useState({ fromAccountId: '', toAccountId: '', amount: '', description: '' });
    const [extLoading, setExtLoading] = useState(false);
    const [extError, setExtError] = useState('');

    // Recipient by name search
    const [recipientMode, setRecipientMode] = useState('ACCOUNT'); // ACCOUNT | NAME
    const [searchName, setSearchName] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [selectedRecipient, setSelectedRecipient] = useState(null);

    useEffect(() => {
        const loadAccounts = async () => {
            try {
                const user = getUser();
                if (!user?.id) {
                    console.error('No current user found in storage');
                    setLoading(false);
                    return;
                }

                const { data } = await fetchAccounts(user.id);
                setAccounts(data || []);
                if (!extForm.fromAccountId && (data || []).length > 0) {
                    setExtForm(prev => ({ ...prev, fromAccountId: data[0].id }));
                }

                // Load transactions for user
                const txRes = await fetchTransactions(user.id);
                setTransactions(txRes.data || []);

            } catch (err) {
                console.error('Failed to fetch accounts', err);
            } finally {
                setLoading(false);
            }
        };

        loadAccounts();
    }, []);

    useEffect(() => {
        // Debounced search when recipientMode === 'NAME'
        if (recipientMode !== 'NAME') return;
        const term = searchName.trim();
        if (term.length < 3) { setSearchResults([]); return; }
        const handle = setTimeout(async () => {
            try {
                const { searchUsers } = await import('../../utils/financeApi.js');
                const resp = await searchUsers(term);
                setSearchResults(resp.data?.users || []);
            } catch (err) {
                console.error('User search failed', err);
            }
        }, 300);
        return () => clearTimeout(handle);
    }, [searchName, recipientMode]);

    if (loading) {
        return (
            <div style={{ padding: '2rem' }}>
                <div className="crash-pay-glass-card" style={{ padding: '2rem' }}>
                    Loading accounts…
                </div>
            </div>
        );
    }

    return (
        <div style={{ padding: '2rem' }}>
            {/* ──────────────────────────────────────────────────────────── */}
            {/* Accounts Table                                                */}
            {/* ──────────────────────────────────────────────────────────── */}
            <div className="crash-pay-glass-card" style={{ padding: '2rem' }}>
                <h3 style={{ color: 'var(--text-light)', marginBottom: '1.5rem' }}>Accounts</h3>
                {accounts.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-light)' }}>
                        <p>No accounts found.</p>
                        <p style={{ fontSize: '0.9rem', opacity: 0.7, marginTop: '0.5rem' }}>
                            Accounts will be created automatically when you generate users from the admin panel.
                        </p>
                    </div>
                ) : (
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr>
                                    <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--accent-gold)' }}>ID</th>
                                    <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--accent-gold)' }}>Type</th>
                                    <th style={{ padding: '1rem', textAlign: 'right', color: 'var(--accent-gold)' }}>Balance</th>
                                    <th style={{ padding: '1rem', textAlign: 'center', color: 'var(--accent-gold)' }}>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {accounts.map((a) => (
                                    <tr key={a.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                                        <td style={{ padding: '1rem', color: 'var(--text-light)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                <span>{a.id}</span>
                                                <button
                                                    onClick={() => navigator.clipboard.writeText(a.id)}
                                                    style={{
                                                        background: 'transparent',
                                                        border: '1px solid var(--glass-border)',
                                                        color: 'var(--accent-gold)',
                                                        padding: '0.25rem 0.5rem',
                                                        borderRadius: '4px',
                                                        fontSize: '0.75rem',
                                                        cursor: 'pointer'
                                                    }}
                                                    title="Copy full account ID"
                                                >
                                                    Copy
                                                </button>
                                            </div>
                                        </td>
                                        <td style={{ padding: '1rem', color: 'var(--text-light)' }}>{a.type}</td>
                                        <td style={{ padding: '1rem', textAlign: 'right', color: 'var(--text-light)' }}>
                                            ${parseFloat(a.balance).toLocaleString()}
                                        </td>
                                        <td style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-light)' }}>{a.status}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* ──────────────────────────────────────────────────────────── */}
            {/* Transfer Form                                                 */}
            {/* ──────────────────────────────────────────────────────────── */}
            {accounts.length > 0 && (
                <div className="crash-pay-glass-card" style={{ padding: '2rem', marginTop: '2rem' }}>
                    <h3 style={{ color: 'var(--text-light)', marginBottom: '1.5rem' }}>Make a Transfer</h3>

                    {transferError && (
                        <p style={{ color: '#f87171', marginBottom: '1rem' }}>{transferError}</p>
                    )}

                    <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))' }}>
                        {/* From account */}
                        <select
                            value={form.fromAccountId}
                            onChange={(e) => setForm(prev => ({ ...prev, fromAccountId: e.target.value }))}
                            style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }}
                        >
                            <option value="">Select From Account</option>
                            {accounts.map(a => (
                                <option key={a.id} value={a.id}>{`${a.type} (${a.id.slice(0, 8)})`}</option>
                            ))}
                        </select>

                        {/* To account */}
                        <select
                            value={form.toAccountId}
                            onChange={(e) => setForm(prev => ({ ...prev, toAccountId: e.target.value }))}
                            style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }}
                        >
                            <option value="">Select To Account</option>
                            {accounts.map(a => (
                                <option key={a.id} value={a.id}>{`${a.type} (${a.id.slice(0, 8)}) - $${parseFloat(a.balance).toLocaleString()}`}</option>
                            ))}
                        </select>

                        {/* Amount */}
                        <input
                            type="number"
                            placeholder="Amount"
                            value={form.amount}
                            onChange={(e) => setForm(prev => ({ ...prev, amount: e.target.value }))}
                            style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }}
                        />

                        {/* Description */}
                        <input
                            type="text"
                            placeholder="Description"
                            value={form.description}
                            onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                            style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }}
                        />

                        <button
                            onClick={async () => {
                                try {
                                    setTxLoading(true);
                                    setTransferError('');
                                    const { fromAccountId, toAccountId, amount, description } = form;
                                    if (!fromAccountId || !toAccountId || !amount) {
                                        setTransferError('Please fill all fields');
                                        setTxLoading(false);
                                        return;
                                    }

                                    await createTransfer({ fromAccountId, toAccountId, amount: parseFloat(amount), description });

                                    // Reload accounts + transactions
                                    const user = getUser();
                                    const accRes = await fetchAccounts(user.id);
                                    setAccounts(accRes.data || []);
                                    const txRes = await fetchTransactions(user.id);
                                    setTransactions(txRes.data || []);

                                    // Clear form
                                    setForm({ fromAccountId: '', toAccountId: '', amount: '', description: '' });
                                } catch (e) {
                                    console.error('Transfer failed', e);
                                    setTransferError('Transfer failed');
                                } finally {
                                    setTxLoading(false);
                                }
                            }}
                            style={{ padding: '0.75rem 1.5rem', borderRadius: '8px', border: 'none', background: 'var(--accent-gold)', color: '#000', cursor: 'pointer' }}
                            disabled={txLoading}
                        >
                            {txLoading ? 'Processing…' : 'Send'}
                        </button>
                    </div>
                </div>
            )}

            {/* ──────────────────────────────────────────────────────────── */}
            {/* External Client Transfer                                     */}
            <div className="crash-pay-glass-card" style={{ padding: '2rem', marginTop: '2rem' }}>
                <h3 style={{ color: 'var(--text-light)', marginBottom: '1.5rem' }}>Account-to-Account Transfer (other client)</h3>

                {/* Recipient mode toggle */}
                <div style={{ marginBottom: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <label style={{ color: 'var(--text-light)', display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                        <input type="radio" value="ACCOUNT" checked={recipientMode === 'ACCOUNT'} onChange={() => setRecipientMode('ACCOUNT')} />
                        Via Account ID
                    </label>
                    <label style={{ color: 'var(--text-light)', display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                        <input type="radio" value="NAME" checked={recipientMode === 'NAME'} onChange={() => setRecipientMode('NAME')} />
                        Via Client Name
                    </label>
                </div>

                {extError && (
                    <p style={{ color: '#f87171', marginBottom: '1rem' }}>{extError}</p>
                )}

                <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))' }}>
                    {/* From account */}
                    <select
                        value={extForm.fromAccountId}
                        onChange={(e) => setExtForm(prev => ({ ...prev, fromAccountId: e.target.value }))}
                        style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }}
                    >
                        <option value="">Select From Account</option>
                        {accounts.map(a => (
                            <option key={a.id} value={a.id}>{`${a.type} (${a.id.slice(0, 8)})`}</option>
                        ))}
                    </select>

                    {/* Recipient input – conditional */}
                    {recipientMode === 'ACCOUNT' ? (
                        <input
                            type="text"
                            placeholder="Recipient Account ID"
                            value={extForm.toAccountId}
                            onChange={(e) => setExtForm(prev => ({ ...prev, toAccountId: e.target.value.trim() }))}
                            style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }}
                        />
                    ) : (
                        <div style={{ position: 'relative' }}>
                            <input
                                type="text"
                                placeholder="Search Client Name…"
                                value={searchName}
                                onChange={(e) => {
                                    setSearchName(e.target.value);
                                    setSelectedRecipient(null);
                                }}
                                style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }}
                            />
                            {searchResults.length > 0 && (
                                <ul style={{ position: 'absolute', top: '110%', left: 0, right: 0, background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: '8px', maxHeight: '200px', overflowY: 'auto', zIndex: 10 }}>
                                    {searchResults.map(u => (
                                        <li
                                            key={u.id}
                                            onClick={async () => {
                                                setSelectedRecipient(u);
                                                setSearchName(u.name);
                                                setSearchResults([]);
                                                try {
                                                    const { getAccounts } = await import('../../utils/financeApi.js');
                                                    const accResp = await getAccounts(u.id);
                                                    const userAccs = accResp.data || [];
                                                    if (userAccs.length === 0) {
                                                        setExtError('Recipient has no active accounts');
                                                    } else {
                                                        setExtError('');
                                                        setExtForm(prev => ({ ...prev, toAccountId: userAccs[0].id }));
                                                    }
                                                } catch (accErr) {
                                                    console.error('Failed to fetch recipient accounts', accErr);
                                                }
                                            }}
                                            style={{ padding: '0.5rem 0.75rem', cursor: 'pointer', color: 'var(--text-light)' }}
                                        >
                                            {u.name}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    )}

                    {/* Amount */}
                    <input
                        type="number"
                        placeholder="Amount"
                        value={extForm.amount}
                        onChange={(e) => setExtForm(prev => ({ ...prev, amount: e.target.value }))}
                        style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }}
                    />
                    {/* Description */}
                    <input
                        type="text"
                        placeholder="Description"
                        value={extForm.description}
                        onChange={(e) => setExtForm(prev => ({ ...prev, description: e.target.value }))}
                        style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--glass-bg)', color: 'var(--text-light)', border: '1px solid var(--glass-border)' }}
                    />
                    <button
                        onClick={async () => {
                            try {
                                setExtLoading(true);
                                setExtError('');
                                const { fromAccountId, toAccountId, amount, description } = extForm;
                                if (!fromAccountId || !toAccountId || !amount) {
                                    setExtError('Please fill all fields');
                                    setExtLoading(false);
                                    return;
                                }
                                await createTransfer({ fromAccountId, toAccountId, amount: parseFloat(amount), description });
                                const user = getUser();
                                const accRes = await fetchAccounts(user.id);
                                setAccounts(accRes.data || []);
                                const txRes = await fetchTransactions(user.id);
                                setTransactions(txRes.data || []);
                                setExtForm({ fromAccountId: '', toAccountId: '', amount: '', description: '' });
                            } catch (e) {
                                console.error('External transfer failed', e);
                                setExtError('Transfer failed');
                            } finally {
                                setExtLoading(false);
                            }
                        }}
                        style={{ padding: '0.75rem 1.5rem', borderRadius: '8px', border: 'none', background: 'var(--accent-gold)', color: '#000', cursor: 'pointer' }}
                        disabled={extLoading}
                    >
                        {extLoading ? 'Processing…' : 'Send'}
                    </button>
                </div>
            </div>

            {/* Transactions Table                                           */}
            {/* ──────────────────────────────────────────────────────────── */}
            <div className="crash-pay-glass-card" style={{ padding: '2rem', marginTop: '2rem' }}>
                <h3 style={{ color: 'var(--text-light)', marginBottom: '1.5rem' }}>Transactions</h3>
                {transactions.length === 0 ? (
                    <p style={{ color: 'var(--text-light)' }}>No transactions found.</p>
                ) : (
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr>
                                    <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--accent-gold)' }}>Date</th>
                                    <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--accent-gold)' }}>Description</th>
                                    <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--accent-gold)' }}>Account</th>
                                    <th style={{ padding: '1rem', textAlign: 'right', color: 'var(--accent-gold)' }}>Amount</th>
                                    <th style={{ padding: '1rem', textAlign: 'center', color: 'var(--accent-gold)' }}>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {transactions.map(tx => (
                                    <tr key={tx.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                                        <td style={{ padding: '1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>{new Date(tx.createdAt).toLocaleDateString()}</td>
                                        <td style={{ padding: '1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>{tx.description}</td>
                                        <td style={{ padding: '1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>
                                            {tx.accountType
                                                ? (String(tx.accountType).toLowerCase() === 'checking'
                                                    ? 'Checking'
                                                    : String(tx.accountType).toLowerCase() === 'savings'
                                                        ? 'Savings'
                                                        : tx.accountType)
                                                : '—'}
                                        </td>
                                        <td style={{ padding: '1rem', textAlign: 'right', color: tx.amount >= 0 ? '#4ade80' : '#f87171', fontWeight: '600', fontSize: '0.9rem' }}>
                                            {tx.amount >= 0 ? '+' : ''}${parseFloat(tx.amount).toLocaleString()}
                                        </td>
                                        <td style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-light)', fontSize: '0.9rem' }}>{tx.status}</td>
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
