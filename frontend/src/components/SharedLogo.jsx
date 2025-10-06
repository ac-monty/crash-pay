import React from 'react';
import './SharedStyles.css';
import logoBlack from '../assets/SVG/logo_black.svg?url';
import logoWhite from '../assets/SVG/logo_white.svg?url';
import logoFullBlack from '../assets/SVG/logo_full_black.svg?url';
import logoFullWhite from '../assets/SVG/logo_full_white.svg?url';

function SharedLogo({ size = 'medium', showText = true, clickable = false, onClick, theme = 'dark', showContainer = false }) {
    const logoSizes = {
        small: { width: 40, height: 40 },
        medium: { width: 80, height: 80 },
        large: { width: 120, height: 120 }
    };

    const currentSize = logoSizes[size];

    const logoStyle = {
        width: `${currentSize.width}px`,
        height: `${currentSize.height}px`,
        cursor: clickable ? 'pointer' : 'default'
    };

    const handleClick = () => {
        if (clickable && onClick) {
            onClick();
        }
    };

    // Choose the appropriate logo based on showText and theme
    const getLogoSrc = () => {
        if (showText) {
            return theme === 'light' ? logoFullWhite : logoFullBlack;
        } else {
            return theme === 'light' ? logoWhite : logoBlack;
        }
    };

    return (
        <div
            style={{
                textAlign: 'center',
                display: 'inline-block'
            }}
            onClick={handleClick}
        >
            {showText && !showContainer ? (
                // Use the full logo with integrated text - no container
                <img
                    src={getLogoSrc()}
                    alt="Crash Pay Logo"
                    style={logoStyle}
                    className="crash-pay-logo-image"
                />
            ) : (
                // Use logo with orange container (either shield-only or full logo)
                <div className="crash-pay-logo-container" style={logoStyle}>
                    <img
                        src={getLogoSrc()}
                        alt="Crash Pay Logo"
                        className="crash-pay-logo-image-contained"
                    />
                </div>
            )}
        </div>
    );
}

export default SharedLogo; 