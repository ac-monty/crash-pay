import React from 'react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        // Update state so the next render will show the fallback UI
        return { hasError: true };
    }

    componentDidCatch(error, errorInfo) {
        // Log error details but don't break the app
        console.warn('🔧 App Error Caught (handled gracefully):', error);
        console.warn('Error Info:', errorInfo);

        this.setState({
            error: error,
            errorInfo: errorInfo
        });

        // Optionally report to a monitoring service (but not APM to avoid loops)
        // this.reportErrorToService(error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
    }

    render() {
        if (this.state.hasError) {
            // Graceful fallback UI
            return (
                <div style={{
                    padding: '2rem',
                    margin: '2rem',
                    border: '2px solid #f59e0b',
                    borderRadius: '8px',
                    backgroundColor: '#1e293b',
                    color: '#f8fafc',
                    fontFamily: 'Inter, sans-serif'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1rem' }}>
                        <span style={{ fontSize: '2rem', marginRight: '0.5rem' }}>⚠️</span>
                        <h2 style={{ margin: 0, color: '#f59e0b' }}>Oops! Something went wrong</h2>
                    </div>

                    <p style={{ marginBottom: '1rem', color: '#cbd5e1' }}>
                        Don't worry - this is likely a minor issue. The application is still functional.
                    </p>

                    <div style={{ marginBottom: '1rem' }}>
                        <button
                            onClick={this.handleReset}
                            style={{
                                padding: '0.5rem 1rem',
                                backgroundColor: '#f59e0b',
                                color: '#1e293b',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontWeight: '600',
                                marginRight: '0.5rem'
                            }}
                        >
                            🔄 Try Again
                        </button>

                        <button
                            onClick={() => window.location.href = '/banking/login'}
                            style={{
                                padding: '0.5rem 1rem',
                                backgroundColor: '#1e40af',
                                color: '#f8fafc',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontWeight: '600'
                            }}
                        >
                            🏦 Go to Banking
                        </button>
                    </div>

                    {process.env.NODE_ENV === 'development' && this.state.error && (
                        <details style={{ marginTop: '1rem' }}>
                            <summary style={{ cursor: 'pointer', color: '#f59e0b' }}>
                                🔍 Error Details (Development Mode)
                            </summary>
                            <pre style={{
                                backgroundColor: '#0f172a',
                                padding: '1rem',
                                borderRadius: '4px',
                                fontSize: '0.8rem',
                                color: '#cbd5e1',
                                overflow: 'auto',
                                marginTop: '0.5rem'
                            }}>
                                {this.state.error && this.state.error.toString()}
                                <br />
                                {this.state.errorInfo.componentStack}
                            </pre>
                        </details>
                    )}
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary; 