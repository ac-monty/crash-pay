import React from 'react';
import './SharedStyles.css';

function PageWrapper({ children, showBackground = false, className = '' }) {
    return (
        <>
            {showBackground && (
                <div className="crash-pay-background">
                    <div className="floating-shapes">
                        <div className="shape"></div>
                        <div className="shape"></div>
                        <div className="shape"></div>
                        <div className="shape"></div>
                        <div className="shape"></div>
                        <div className="shape"></div>
                    </div>
                    <div className="grid-overlay"></div>
                </div>
            )}
            <div className={className} style={{ position: 'relative', zIndex: 1 }}>
                {children}
            </div>
        </>
    );
}

export default PageWrapper; 