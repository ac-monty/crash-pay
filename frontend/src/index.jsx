import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App.jsx';
import ErrorBoundary from './components/ErrorBoundary';


console.log('🏦 Crash Pay Frontend - Loading...');

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);

/*
 * Graceful service worker registration with error handling
 * Won't break the app if service worker fails
 */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((registration) => {
        console.log('✅ SW registered:', registration.scope);
      })
      .catch((error) => {
        // Fail silently in production, log in development
        if (process.env.NODE_ENV === 'development') {
          console.log('ℹ️ SW registration failed (expected in dev):', error.message);
        }
        // Don't break the app - just continue without service worker
      });
  });
} else {
  console.log('ℹ️ Service workers not supported in this browser');
}

// Add global error handler to prevent app crashes
window.addEventListener('error', (event) => {
  console.warn('🔧 Global error caught (handled gracefully):', event.error);
  // Don't prevent default - let React error boundary handle it
});

window.addEventListener('unhandledrejection', (event) => {
  console.warn('🔧 Unhandled promise rejection caught:', event.reason);
  // Prevent unhandled rejections from crashing the app
  event.preventDefault();
});

console.log('🚀 Crash Pay Frontend - Ready!');