import React, { useEffect, useState } from 'react';
import '../SharedStyles.css';

export default function TradingPanel() {
    const [symbol, setSymbol] = useState('AAPL');
    const [qty, setQty] = useState('1');
    const [side, setSide] = useState('BUY');
    const [positions, setPositions] = useState([]);

    const refresh = async () => {
        try {
            const token = localStorage.getItem('bankingToken');
            if (!token) return;

            const response = await fetch('/api/trading/positions', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                setPositions(data);
            }
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => { refresh(); }, []);

    const submit = async () => {
        try {
            const token = localStorage.getItem('bankingToken');
            const user = JSON.parse(localStorage.getItem('currentUser') || '{}');

            const response = await fetch('/api/trading/orders', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    userId: user.id,
                    symbol,
                    quantity: parseFloat(qty),
                    price: 100,
                    side
                })
            });

            if (response.ok) {
                await refresh();
            }
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div style={{ padding: '2rem' }}>
            <div className="crash-pay-glass-card" style={{ padding: '2rem' }}>
                <h3 style={{ color: 'var(--text-light)', marginBottom: '1.5rem' }}>Trading</h3>

                <div style={{ marginBottom: '2rem' }}>
                    <h4 style={{ color: 'var(--text-light)', marginBottom: '1rem' }}>Place Order</h4>
                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
                        <select
                            value={side}
                            onChange={(e) => setSide(e.target.value)}
                            style={{
                                padding: '0.5rem',
                                borderRadius: '8px',
                                border: '1px solid var(--glass-border)',
                                background: 'var(--glass-bg)',
                                color: 'var(--text-light)'
                            }}
                        >
                            <option value="BUY">BUY</option>
                            <option value="SELL">SELL</option>
                        </select>
                        <input
                            value={symbol}
                            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                            placeholder="Symbol"
                            style={{
                                padding: '0.5rem',
                                borderRadius: '8px',
                                border: '1px solid var(--glass-border)',
                                background: 'var(--glass-bg)',
                                color: 'var(--text-light)',
                                width: '100px'
                            }}
                        />
                        <input
                            value={qty}
                            onChange={(e) => setQty(e.target.value)}
                            type="number"
                            placeholder="Qty"
                            style={{
                                padding: '0.5rem',
                                borderRadius: '8px',
                                border: '1px solid var(--glass-border)',
                                background: 'var(--glass-bg)',
                                color: 'var(--text-light)',
                                width: '80px'
                            }}
                        />
                        <button
                            onClick={submit}
                            style={{
                                padding: '0.5rem 1rem',
                                borderRadius: '8px',
                                border: 'none',
                                background: 'var(--accent-gold)',
                                color: '#000',
                                cursor: 'pointer'
                            }}
                        >
                            Submit Order
                        </button>
                    </div>
                </div>

                <h4 style={{ color: 'var(--text-light)', marginBottom: '1rem' }}>Positions</h4>
                {positions.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-light)' }}>
                        <p>No positions found.</p>
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {positions.map((p) => (
                            <div key={p.id} style={{
                                padding: '1rem',
                                background: 'rgba(255, 255, 255, 0.05)',
                                borderRadius: '8px',
                                border: '1px solid var(--glass-border)',
                                color: 'var(--text-light)'
                            }}>
                                <strong>{p.symbol}</strong>: {parseFloat(p.shares).toLocaleString()} shares @ ${parseFloat(p.avgPrice).toFixed(2)}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
