import React, { useState, useEffect } from 'react';
import './SharedStyles.css';
import PageWrapper from './PageWrapper';
import Icon from './Icon';
import { isAdminLoggedIn, getAdminToken, adminLogout } from '../utils/auth.js';

const UserManagement = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [editModalOpen, setEditModalOpen] = useState(false);
    const [currentEditingUser, setCurrentEditingUser] = useState(null);
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [savePasswordLoading, setSavePasswordLoading] = useState(false);
    const [tier, setTier] = useState('basic');
    const [rolesSel, setRolesSel] = useState(['customer']);
    const [tiers] = useState(['basic', 'premium', 'director']);
    const [allRoles] = useState(['customer', 'advisor', 'admin']);

    // Fetch users from API
    const fetchUsers = async () => {
        try {
            const token = getAdminToken();
            const headers = token ? { Authorization: `Bearer ${token}` } : {};
            const res = await fetch(`/api/users`, { headers });
            const data = await res.json();
            setUsers(data.users || []);
        } catch (err) {
            console.error('Failed to fetch users:', err);
        } finally {
            setLoading(false);
        }
    };

    // Refresh users with loading animation
    const refreshUsers = async () => {
        setIsRefreshing(true);
        try {
            await fetchUsers();
            // Add pulse animation
            const table = document.querySelector('.crash-pay-users-table-container');
            if (table) {
                table.classList.add('pulse');
                setTimeout(() => {
                    table.classList.remove('pulse');
                }, 1000);
            }
        } catch (err) {
            console.error('Failed to refresh users:', err);
        } finally {
            setTimeout(() => setIsRefreshing(false), 1500); // Keep loading state for visual feedback
        }
    };

    // Delete user with confirmation and animation
    const deleteUser = async (userId, buttonElement) => {
        if (!window.confirm(`Are you sure you want to delete user ${userId}? This action cannot be undone.`)) {
            return;
        }

        const row = buttonElement.closest('tr');
        const originalContent = buttonElement.innerHTML;

        // Show loading state
        buttonElement.innerHTML = '<div class="crash-pay-loading"></div>';
        buttonElement.disabled = true;

        try {
            const token = getAdminToken();
            const headers = token ? { Authorization: `Bearer ${token}` } : {};
            const res = await fetch(`/api/users/${userId}`, {
                method: 'DELETE',
                headers
            });

            if (res.ok) {
                // Add deletion animation
                row.classList.add('deleting');

                // Remove row after animation and update state
                setTimeout(() => {
                    setUsers(prevUsers => prevUsers.filter(user => user.id !== userId));
                }, 500);
            } else {
                throw new Error('Delete failed');
            }
        } catch (err) {
            console.error('Failed to delete user:', err);
            // Reset button on error
            buttonElement.innerHTML = originalContent;
            buttonElement.disabled = false;
            alert('Failed to delete user. Please try again.');
        }
    };

    // Open edit modal with current user data
    const editUser = (userObj) => {
        setCurrentEditingUser(userObj);
        setNewPassword('');
        setConfirmPassword('');

        // Pre-fill tier and roles based on user record (fallbacks if missing)
        setTier(userObj?.Tier?.name || 'basic');
        setRolesSel(userObj?.Roles?.map(r => r.name) || []);

        setEditModalOpen(true);

        // Focus for quicker typing
        setTimeout(() => {
            const passwordField = document.getElementById('newPassword');
            if (passwordField) passwordField.focus();
        }, 300);
    };

    // Close edit modal
    const closeEditModal = () => {
        setEditModalOpen(false);
        setCurrentEditingUser(null);
        setNewPassword('');
        setConfirmPassword('');
    };

    // Inline tier / role update
    const handleInlineUpdate = async (userId, newTier, newRoles) => {
        try {
            const payload = {
                userId,
                tierName: newTier,
                roles: newRoles,
            };
            const token = getAdminToken();
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers.Authorization = `Bearer ${token}`;
            await fetch(`/api/admin/change-user-password`, {
                method: 'POST',
                headers,
                body: JSON.stringify(payload)
            });
            // Update local state to reflect changes without refetching entire list
            setUsers(prev => prev.map(u => {
                if (u.id !== userId) return u;
                return {
                    ...u,
                    Tier: { name: newTier },
                    Roles: allRoles.filter(r => newRoles.includes(r)).map(r => ({ name: r }))
                };
            }));
        } catch (err) {
            console.error('Failed to update user inline:', err);
            alert('Failed to update user.');
        }
    };

    // Save changes (password optional)
    const savePassword = async (event) => {
        event.preventDefault();

        if (newPassword) {
            if (newPassword !== confirmPassword) {
                alert('Passwords do not match!');
                return;
            }
            if (newPassword.length < 6) {
                alert('Password must be at least 6 characters long!');
                return;
            }
        }

        setSavePasswordLoading(true);

        try {
            const payload = {
                userId: currentEditingUser.id,
                newPassword: newPassword || undefined,
                tierName: tier,
                roles: rolesSel
            };
            const token = getAdminToken();
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers.Authorization = `Bearer ${token}`;
            const res = await fetch(`/api/admin/change-user-password`, {
                method: 'POST',
                headers,
                body: JSON.stringify(payload)
            });

            const data = await res.json();

            if (data.ok) {
                // Refresh list to reflect new tier/roles
                await fetchUsers();

                // Show success state temporarily
                setTimeout(() => {
                    closeEditModal();
                    alert('User updated successfully!');
                }, 500);
            } else {
                throw new Error(data.error || 'Failed to change password');
            }
        } catch (err) {
            console.error('Failed to change password:', err);
            alert(`Failed to change password: ${err.message}`);
        } finally {
            setSavePasswordLoading(false);
        }
    };

    useEffect(() => {
        if (!isAdminLoggedIn()) {
            window.location.href = '/admin/login';
            return;
        }
        fetchUsers();
    }, []);

    // Close modal when clicking outside or pressing Escape
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                closeEditModal();
            }
        };

        const handleClickOutside = (e) => {
            if (e.target.classList.contains('crash-pay-modal-overlay')) {
                closeEditModal();
            }
        };

        if (editModalOpen) {
            document.addEventListener('keydown', handleKeyDown);
            document.addEventListener('click', handleClickOutside);
        }

        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            document.removeEventListener('click', handleClickOutside);
        };
    }, [editModalOpen]);

    if (loading) {
        return (
            <PageWrapper>
                <div className="crash-pay-page-container">
                    <div className="crash-pay-glass-card crash-pay-page-card">
                        <div style={{ textAlign: 'center', color: 'var(--text-light)' }}>
                            <div className="crash-pay-loading" style={{ margin: '0 auto 1rem' }}></div>
                            Loading users...
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
                <div className="crash-pay-users-page">
                    {/* Users Header */}
                    <div className="crash-pay-users-header crash-pay-rotating-border">
                        <h1 className="crash-pay-users-title">
                            <Icon name="users" size="large" />
                            User Management
                        </h1>
                        <div className="crash-pay-users-actions">
                            <button
                                className="crash-pay-refresh-btn"
                                onClick={refreshUsers}
                                disabled={isRefreshing}
                            >
                                <Icon name="refresh" size="default" />
                                {isRefreshing ? 'Refreshing...' : 'Refresh'}
                            </button>
                            <a className="crash-pay-back-btn" href="/admin/dashboard">
                                <Icon name="dashboard" size="default" />
                                Dashboard
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
                    </div>

                    {/* Users Table */}
                    <div className="crash-pay-users-table-container">
                        <table className="crash-pay-users-table">
                            <thead>
                                <tr>
                                    <th>User ID</th>
                                    <th>Name</th>
                                    <th>SSN</th>
                                    <th>Balance</th>
                                    <th>Tier</th>
                                    <th>Roles</th>
                                    <th>Created</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.length === 0 ? (
                                    <tr>
                                        <td colSpan="6" className="crash-pay-no-data">
                                            No users found. Generate some users from the dashboard.
                                        </td>
                                    </tr>
                                ) : (
                                    users.map((user) => (
                                        <tr key={user.id} data-user-id={user.id}>
                                            <td><span className="crash-pay-user-id">{user.id?.substring(0, 8) || 'N/A'}</span></td>
                                            <td><span className="crash-pay-user-name">{user.name}</span></td>
                                            <td><span className="crash-pay-user-ssn">{user.ssn}</span></td>
                                            <td><span className="crash-pay-user-balance">${user.balance?.toLocaleString() || '0.00'}</span></td>
                                            <td>
                                                <select value={user.Tier?.name || 'basic'} onChange={e => handleInlineUpdate(user.id, e.target.value, user.Roles?.map(r => r.name) || [])}>
                                                    {tiers.map(t => (
                                                        <option key={t} value={t}>{t}</option>
                                                    ))}
                                                </select>
                                            </td>
                                            <td>
                                                <select multiple value={user.Roles?.map(r => r.name) || []} onChange={e => {
                                                    const vals = Array.from(e.target.selectedOptions, o => o.value);
                                                    handleInlineUpdate(user.id, user.Tier?.name || 'basic', vals);
                                                }}>
                                                    {allRoles.map(r => (<option key={r} value={r}>{r}</option>))}
                                                </select>
                                            </td>
                                            <td><span className="crash-pay-user-created">{new Date(user.createdAt).toLocaleDateString()}</span></td>
                                            <td>
                                                <div className="crash-pay-action-buttons">
                                                    <button
                                                        className="crash-pay-action-btn edit"
                                                        onClick={() => editUser(user)}
                                                        title="Edit Password"
                                                    >
                                                        <Icon name="password" size="default" />
                                                    </button>
                                                    <button
                                                        className="crash-pay-action-btn delete"
                                                        onClick={(e) => deleteUser(user.id, e.target)}
                                                        title="Delete User"
                                                    >
                                                        <Icon name="chatClear" size="default" />
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </main>

            {/* Edit Password Modal */}
            {editModalOpen && (
                <div className="crash-pay-modal-overlay active">
                    <div className="crash-pay-modal crash-pay-rotating-border">
                        <div className="crash-pay-modal-header">
                            <h2 className="crash-pay-modal-title">
                                <Icon name="settings" size="default" />
                                Edit Password
                            </h2>
                            <button className="crash-pay-modal-close" onClick={closeEditModal}>
                                <Icon name="close" size="default" />
                            </button>
                        </div>
                        <form onSubmit={savePassword}>
                            <div className="crash-pay-form-group">
                                <label className="crash-pay-form-label">User</label>
                                <input
                                    type="text"
                                    className="crash-pay-form-input"
                                    value={`${currentEditingUser?.name} (${currentEditingUser?.id?.substring(0, 8)}...)`}
                                    readOnly
                                />
                            </div>
                            <div className="crash-pay-form-group">
                                <label className="crash-pay-form-label">New Password</label>
                                <input
                                    type="password"
                                    className="crash-pay-form-input"
                                    id="newPassword"
                                    placeholder="Enter new password"
                                    value={newPassword}
                                    onChange={(e) => setNewPassword(e.target.value)}
                                    // Only required when changing password
                                    required={Boolean(newPassword)}
                                />
                            </div>
                            <div className="crash-pay-form-group">
                                <label className="crash-pay-form-label">Confirm Password</label>
                                <input
                                    type="password"
                                    className="crash-pay-form-input"
                                    placeholder="Confirm new password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    required={Boolean(newPassword)}
                                />
                            </div>
                            <div className="crash-pay-form-group">
                                <label className="crash-pay-form-label">Tier</label>
                                <select className="crash-pay-form-input" value={tier} onChange={e => setTier(e.target.value)}>
                                    <option value="basic">basic</option>
                                    <option value="premium">premium</option>
                                    <option value="director">director</option>
                                </select>
                            </div>
                            <div className="crash-pay-form-group">
                                <label className="crash-pay-form-label">Roles</label>
                                <select multiple className="crash-pay-form-input" value={rolesSel} onChange={e => setRolesSel(Array.from(e.target.selectedOptions, o => o.value))}>
                                    <option value="customer">customer</option>
                                    <option value="advisor">advisor</option>
                                    <option value="admin">admin</option>
                                </select>
                            </div>
                            <div className="crash-pay-modal-actions">
                                <button type="button" className="crash-pay-btn crash-pay-btn-secondary" onClick={closeEditModal}>
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="crash-pay-btn crash-pay-btn-primary"
                                    disabled={savePasswordLoading}
                                >
                                    {savePasswordLoading ? (
                                        <>
                                            <div className="crash-pay-loading"></div>
                                            Saving...
                                        </>
                                    ) : (
                                        <>
                                            <Icon name="checkmark" size="small" />
                                            Save Password
                                        </>
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </PageWrapper>
    );
};

export default UserManagement; 