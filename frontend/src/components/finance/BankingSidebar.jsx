import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import './FinanceStyles.css';

export default function BankingSidebar({ onSidebarToggle }) {
    const location = useLocation();
    const [isCollapsed, setIsCollapsed] = useState(false);

    const isActive = (path) => location.pathname === path;

    const toggleSidebar = () => {
        setIsCollapsed(!isCollapsed);
        if (onSidebarToggle) {
            onSidebarToggle(!isCollapsed);
        }
    };

    return (
        <>
            <aside className={`banking-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
                <nav className="banking-sidebar-nav">
                    <Link to="/banking/dashboard" className={isActive('/banking/dashboard') ? 'active' : ''}>
                        {!isCollapsed && 'Overview'}
                    </Link>
                    <Link to="/banking/accounts" className={isActive('/banking/accounts') ? 'active' : ''}>
                        {!isCollapsed && 'Accounts'}
                    </Link>
                    <Link to="/banking/investing" className={isActive('/banking/investing') ? 'active' : ''}>
                        {!isCollapsed && 'Investing'}
                    </Link>
                    <Link to="/banking/loans" className={isActive('/banking/loans') ? 'active' : ''}>
                        {!isCollapsed && 'Loans'}
                    </Link>
                    <Link to="/banking/trading" className={isActive('/banking/trading') ? 'active' : ''}>
                        {!isCollapsed && 'Trading'}
                    </Link>
                </nav>
            </aside>

            <button
                className={`sidebar-toggle ${isCollapsed ? 'collapsed' : ''}`}
                onClick={toggleSidebar}
                title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
                {isCollapsed ? (
                    <svg viewBox="0 0 30 30">
                        <path d="M22.14,15l-11.2,11.2-3.08-2.94,8.26-8.26L7.86,6.74l3.08-2.94,11.2,11.2Z" />
                    </svg>
                ) : (
                    <svg viewBox="0 0 30 30">
                        <path d="M7.86,15L19.06,3.8l3.08,2.94-8.26,8.26,8.26,8.26-3.08,2.94L7.86,15Z" />
                    </svg>
                )}
            </button>
        </>
    );
}
