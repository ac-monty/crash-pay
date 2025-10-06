import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { isLoggedIn } from '../utils/auth.js';

// Simple guard around protected banking routes
export default function PrivateRoute() {
    const location = useLocation();
    return isLoggedIn() ? (
        <Outlet />
    ) : (
        <Navigate to="/banking/login" replace state={{ from: location }} />
    );
}
