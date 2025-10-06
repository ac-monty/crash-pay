import React, { useState, useEffect } from 'react';
import './SharedStyles.css';
import PageWrapper from './PageWrapper';
import Icon from './Icon';
import { isAdminLoggedIn, getAdminToken, adminLogout } from '../utils/auth.js';

const AdminDashboard = () => {
    const [stats, setStats] = useState({
        totalUsers: 1247,
        totalTransactions: 8429,
        systemUptime: '99.9%',
        timestamp: new Date().toISOString()
    });
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [clearing, setClearing] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [userCount, setUserCount] = useState(10);

    // LLM Model Selector State
    const [availableModels, setAvailableModels] = useState({});
    const [currentModel, setCurrentModel] = useState({});
    const [selectedProvider, setSelectedProvider] = useState('');
    const [selectedModel, setSelectedModel] = useState('');
    const [switching, setSwitching] = useState(false);

    // Fetch stats from API
    const fetchStats = async () => {
        try {
            const token = getAdminToken();
            const headers = token ? { Authorization: `Bearer ${token}` } : {};
            const res = await fetch(`/api/admin/stats`, { headers });
            const data = await res.json();
            if (data.ok) {
                setStats(data.stats);
            }
        } catch (err) {
            console.error('Failed to fetch stats:', err);
            // Keep default stats
        } finally {
            setLoading(false);
        }
    };

    // Fetch available models and current model
    const fetchLLMData = async () => {
        try {
            const token = getAdminToken();
            const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};
            // Fetch available models
            const modelsRes = await fetch(`/api/llm/available-models`, {
                headers: authHeaders
            });
            const modelsData = await modelsRes.json();
            setAvailableModels(modelsData.available_models || modelsData.providers || {});

            // Fetch current model
            const currentRes = await fetch(`/api/llm/current-model`, {
                headers: authHeaders
            });
            const currentData = await currentRes.json();
            setCurrentModel(currentData);
            setSelectedProvider(currentData.provider || '');
            setSelectedModel(currentData.friendly_name || currentData.api_model || '');
        } catch (err) {
            console.error('Failed to fetch LLM data:', err);
        }
    };

    // Handle provider selection
    const handleProviderChange = (provider) => {
        setSelectedProvider(provider);
        setSelectedModel(''); // Reset model selection
    };

    // Handle model switching
    const switchModel = async (buttonElement) => {
        if (!selectedProvider || !selectedModel) {
            alert('Please select both a provider and model');
            return;
        }

        const originalContent = buttonElement.innerHTML;
        setSwitching(true);

        // Show loading state
        buttonElement.innerHTML = '<div class="crash-pay-loading"></div>Switching Model...';
        buttonElement.disabled = true;

        try {
            const token = getAdminToken();
            const headers = token ? { Authorization: `Bearer ${token}` } : {};
            const res = await fetch(`/api/llm/switch-model?provider=${encodeURIComponent(selectedProvider)}&model=${encodeURIComponent(selectedModel)}&validate=true`, {
                method: 'POST',
                headers
            });
            const data = await res.json();

            if (res.ok && data.success === true) {
                // Show success state
                buttonElement.classList.add('crash-pay-success-state');
                buttonElement.innerHTML = `
                    <svg class="crash-pay-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20,6 9,17 4,12"/>
                    </svg>
                    Model Switched!
                `;

                // Update current model info
                await fetchLLMData();

                // Reset button after 3 seconds
                setTimeout(() => {
                    buttonElement.classList.remove('crash-pay-success-state');
                    buttonElement.innerHTML = originalContent;
                    buttonElement.disabled = false;
                }, 3000);
            } else {
                throw new Error(data.error || data.detail || 'Failed to switch model');
            }
        } catch (err) {
            console.error('Failed to switch model:', err);
            alert(`Failed to switch model: ${err.message}`);
            // Reset button on error
            buttonElement.innerHTML = originalContent;
            buttonElement.disabled = false;
        } finally {
            setSwitching(false);
        }
    };

    // Generate users with loading animation and success feedback
    const generateUsers = async (buttonElement) => {
        if (!userCount || userCount < 1 || userCount > 100) {
            alert('Please enter a valid number of users (1-100)');
            return;
        }

        const originalContent = buttonElement.innerHTML;
        setGenerating(true);

        // Show loading state
        buttonElement.innerHTML = '<div class="crash-pay-loading"></div>Generating Users...';
        buttonElement.disabled = true;

        try {
            const token = getAdminToken();
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers.Authorization = `Bearer ${token}`;
            const res = await fetch(`/api/admin/generate-users`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ userCount: parseInt(userCount) })
            });
            const data = await res.json();

            if (data.ok) {
                // Show success state
                buttonElement.classList.add('crash-pay-success-state');
                buttonElement.innerHTML = `
                    <svg class="crash-pay-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20,6 9,17 4,12"/>
                    </svg>
                    Generated ${userCount} Users!
                `;

                // Update stats
                await fetchStats();

                // Reset button after 3 seconds
                setTimeout(() => {
                    buttonElement.classList.remove('crash-pay-success-state');
                    buttonElement.innerHTML = originalContent;
                    buttonElement.disabled = false;
                }, 3000);
            } else {
                throw new Error(data.error || 'Failed to generate users');
            }
        } catch (err) {
            console.error('Failed to generate users:', err);
            alert(`Failed to generate users: ${err.message}`);
            // Reset button on error
            buttonElement.innerHTML = originalContent;
            buttonElement.disabled = false;
        } finally {
            setGenerating(false);
        }
    };

    // Clear conversations with confirmation and loading animation
    const clearConversations = async (buttonElement) => {
        if (!window.confirm('Are you sure you want to clear all conversations? This action cannot be undone.')) {
            return;
        }

        const originalContent = buttonElement.innerHTML;
        setClearing(true);

        // Show loading state
        buttonElement.innerHTML = '<div class="crash-pay-loading"></div>Clearing Conversations...';
        buttonElement.disabled = true;

        try {
            const token = getAdminToken();
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers.Authorization = `Bearer ${token}`;
            const res = await fetch(`/api/admin/clear-chat-sessions`, {
                method: 'POST',
                headers
            });
            const data = await res.json();

            if (data.ok) {
                // Show success state
                buttonElement.classList.add('crash-pay-success-state');
                buttonElement.innerHTML = `
                    <svg class="crash-pay-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20,6 9,17 4,12"/>
                    </svg>
                    Conversations Cleared!
                `;

                // Reset button after 3 seconds
                setTimeout(() => {
                    buttonElement.classList.remove('crash-pay-success-state');
                    buttonElement.innerHTML = originalContent;
                    buttonElement.disabled = false;
                }, 3000);
            } else {
                throw new Error(data.error || 'Failed to clear conversations');
            }
        } catch (err) {
            console.error('Failed to clear conversations:', err);
            alert(`Failed to clear conversations: ${err.message}`);
            // Reset button on error
            buttonElement.innerHTML = originalContent;
            buttonElement.disabled = false;
        } finally {
            setClearing(false);
        }
    };

    // ────────────────────────────────────────────────────────────
    // System Reset – wipe data
    // ────────────────────────────────────────────────────────────
    const resetSystem = async (buttonElement) => {
        if (!window.confirm('This will delete ALL users, accounts and transactions. Continue?')) return;
        const originalContent = buttonElement.innerHTML;
        setResetting(true);
        buttonElement.innerHTML = '<div class="crash-pay-loading"></div>Resetting…';
        buttonElement.disabled = true;
        try {
            const token = getAdminToken();
            const headers = token ? { Authorization: `Bearer ${token}` } : {};
            const res = await fetch(`/api/admin/reset`, { method: 'POST', headers });
            const data = await res.json();
            if (res.ok && data.ok) {
                buttonElement.classList.add('crash-pay-success-state');
                buttonElement.innerHTML = `<svg class="crash-pay-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20,6 9,17 4,12"/></svg> System Reset!`;
                await fetchStats();
                setTimeout(() => { buttonElement.classList.remove('crash-pay-success-state'); buttonElement.innerHTML = originalContent; buttonElement.disabled = false; }, 3000);
            } else { throw new Error(data.error || 'Reset failed'); }
        } catch (err) {
            console.error('Reset failed:', err);
            alert(`Reset failed: ${err.message}`);
            buttonElement.innerHTML = originalContent;
            buttonElement.disabled = false;
        } finally {
            setResetting(false);
        }
    };

    useEffect(() => {
        if (!isAdminLoggedIn()) {
            window.location.href = '/admin/login';
            return;
        }
        fetchStats();
        fetchLLMData();
    }, []);

    // Get available models for selected provider
    const getAvailableModelsForProvider = (provider) => {
        if (!provider || !availableModels[provider]) return [];
        const providerData = availableModels[provider];
        const reasoning = providerData.reasoning || {};
        const oneShot = providerData.one_shot || {};
        // Deduplicate models to prevent React key warnings
        return [...new Set([...Object.keys(reasoning), ...Object.keys(oneShot)])];
    };

    if (loading) {
        return (
            <PageWrapper>
                <div className="crash-pay-page-container">
                    <div className="crash-pay-glass-card crash-pay-page-card">
                        <div style={{ textAlign: 'center', color: 'var(--text-light)' }}>
                            <div className="crash-pay-loading" style={{ margin: '0 auto 1rem' }}></div>
                            Loading dashboard...
                        </div>
                    </div>
                </div>
            </PageWrapper>
        );
    }

    return (
        <PageWrapper showBackground={true}>
            {/* Main Content */}
            <main className="crash-pay-main-content">
                <div className="crash-pay-dashboard">
                    {/* Dashboard Header */}
                    <div className="crash-pay-dashboard-header crash-pay-rotating-border">
                        <h1 className="crash-pay-dashboard-title">
                            Admin Dashboard
                        </h1>
                        <div className="crash-pay-users-actions">
                            <a className="crash-pay-back-btn" href="/admin/users">
                                <Icon name="users" size="default" />
                                Users
                            </a>
                            <button
                                className="crash-pay-refresh-btn"
                                onClick={() => { adminLogout(); window.location.href = '/admin/login'; }}
                                title="Log out admin"
                            >
                                <Icon name="powerOff" size="default" />
                                Logout
                            </button>
                        </div>
                        <div className="crash-pay-dashboard-stats">
                            <div className="crash-pay-quick-stat">
                                <div className="crash-pay-quick-stat-value">{stats.totalUsers?.toLocaleString() || '1,247'}</div>
                                <div className="crash-pay-quick-stat-label">Total Users</div>
                            </div>
                            <div className="crash-pay-quick-stat">
                                <div className="crash-pay-quick-stat-value">{stats.totalTransactions?.toLocaleString() || '8,429'}</div>
                                <div className="crash-pay-quick-stat-label">Total Transactions</div>
                            </div>
                            <div className="crash-pay-quick-stat">
                                <div className="crash-pay-quick-stat-value">{stats.systemUptime || '99.9%'}</div>
                                <div className="crash-pay-quick-stat-label">System Uptime</div>
                            </div>
                        </div>
                    </div>

                    {/* Action Cards */}
                    <div className="crash-pay-action-cards">
                        {/* LLM Model Selector Card */}
                        <div className="crash-pay-action-card">
                            <div className="crash-pay-action-card-icon">
                                <Icon name="settings" size="large" />
                            </div>
                            <h3>LLM Model Configuration</h3>
                            <p>Dynamically switch between different LLM providers and models for the chat agent. Changes take effect immediately without service restart.</p>

                            <div className="crash-pay-input-group">
                                <label className="crash-pay-input-label">Current Model</label>
                                <div className="crash-pay-info-value" style={{
                                    padding: '8px 12px',
                                    backgroundColor: 'rgba(var(--accent-color-rgb), 0.1)',
                                    borderRadius: '6px',
                                    marginBottom: '16px'
                                }}>
                                    {currentModel.provider?.toUpperCase()} - {currentModel.friendly_name || currentModel.api_model}
                                </div>
                            </div>

                            <div className="crash-pay-input-group">
                                <label className="crash-pay-input-label">Select Provider</label>
                                <select
                                    className="crash-pay-input-field"
                                    value={selectedProvider}
                                    onChange={(e) => handleProviderChange(e.target.value)}
                                    disabled={switching}
                                >
                                    <option value="">Choose a provider...</option>
                                    {Object.keys(availableModels).map(provider => (
                                        <option key={provider} value={provider}>
                                            {provider.charAt(0).toUpperCase() + provider.slice(1)}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="crash-pay-input-group">
                                <label className="crash-pay-input-label">Select Model</label>
                                <select
                                    className="crash-pay-input-field"
                                    value={selectedModel}
                                    onChange={(e) => setSelectedModel(e.target.value)}
                                    disabled={!selectedProvider || switching}
                                >
                                    <option value="">Choose a model...</option>
                                    {getAvailableModelsForProvider(selectedProvider).map(model => (
                                        <option key={model} value={model}>
                                            {model}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <button
                                className="crash-pay-action-button"
                                onClick={(e) => switchModel(e.target)}
                                disabled={switching || !selectedProvider || !selectedModel}
                            >
                                <Icon name="settings" size="default" />
                                Switch Model
                            </button>

                            <div className="crash-pay-card-info">
                                <div className="crash-pay-info-row">
                                    <span className="crash-pay-info-label">Available Providers:</span>
                                    <span className="crash-pay-info-value">{Object.keys(availableModels).length}</span>
                                </div>
                                <div className="crash-pay-info-row">
                                    <span className="crash-pay-info-label">Total Models:</span>
                                    <span className="crash-pay-info-value">
                                        {Object.values(availableModels).reduce((total, provider) => {
                                            const reasoning = Object.keys(provider.reasoning || {}).length;
                                            const oneShot = Object.keys(provider.one_shot || {}).length;
                                            return total + reasoning + oneShot;
                                        }, 0)}
                                    </span>
                                </div>
                                <div className="crash-pay-info-row">
                                    <span className="crash-pay-info-label">Function Calling:</span>
                                    <span className="crash-pay-info-value">
                                        {currentModel.supports_function_calling ? '✅ Enabled' : '❌ Disabled'}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Generate Users Card */}
                        <div className="crash-pay-action-card">
                            <div className="crash-pay-action-card-icon">
                                <Icon name="userAdd" size="large" />
                            </div>
                            <h3>Generate Users</h3>
                            <p>Create sample user accounts with random data for testing and demonstration purposes. This will populate the system with realistic user profiles.</p>

                            <div className="crash-pay-input-group">
                                <label className="crash-pay-input-label">Number of Users</label>
                                <input
                                    type="number"
                                    className="crash-pay-input-field"
                                    placeholder="Enter number of users"
                                    value={userCount}
                                    onChange={(e) => setUserCount(e.target.value)}
                                    min="1"
                                    max="100"
                                />
                            </div>

                            <button
                                className="crash-pay-action-button"
                                onClick={(e) => generateUsers(e.target)}
                                disabled={generating}
                            >
                                <Icon name="userAdd" size="default" />
                                Generate Users
                            </button>

                            <div className="crash-pay-card-info">
                                <div className="crash-pay-info-row">
                                    <span className="crash-pay-info-label">Current Users:</span>
                                    <span className="crash-pay-info-value">{stats.totalUsers?.toLocaleString() || '1,247'}</span>
                                </div>
                                <div className="crash-pay-info-row">
                                    <span className="crash-pay-info-label">Last Updated:</span>
                                    <span className="crash-pay-info-value">
                                        {stats.timestamp ? new Date(stats.timestamp).toLocaleString().replace(',', '') : '2025-06-07 14:32'}
                                    </span>
                                </div>
                                <div className="crash-pay-info-row">
                                    <span className="crash-pay-info-label"></span>
                                    <a href="/admin/users" className="crash-pay-view-link">
                                        View All Users
                                        <Icon name="forward" size="small" />
                                    </a>
                                </div>
                            </div>
                        </div>

                        {/* Clear Conversations Card */}
                        <div className="crash-pay-action-card">
                            <div className="crash-pay-action-card-icon">
                                <Icon name="chatClear" size="large" />
                            </div>
                            <h3>Clear Conversations</h3>
                            <p>Remove all chat conversations and message history from the system. This action will permanently delete all stored conversation data.</p>
                            <button
                                className="crash-pay-action-button"
                                onClick={(e) => clearConversations(e.target)}
                                disabled={clearing}
                            >
                                <Icon name="chatClear" size="default" />
                                Clear Conversations
                            </button>
                        </div>

                        {/* Reset System Card */}
                        <div className="crash-pay-action-card">
                            <div className="crash-pay-action-card-icon">
                                <Icon name="delete" size="large" />
                            </div>
                            <h3>Reset Demo Data</h3>
                            <p>Completely wipe all users, accounts and transactions then start fresh. Intended for lab resets.</p>
                            <button
                                className="crash-pay-action-button"
                                onClick={(e) => resetSystem(e.target)}
                                disabled={resetting}
                            >
                                <Icon name="delete" size="default" />
                                Reset System
                            </button>
                        </div>
                    </div>
                </div>
            </main>
        </PageWrapper>
    );
};

export default AdminDashboard;