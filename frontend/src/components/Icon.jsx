import React from 'react';

// Import all the SVG icons from assets with ?url suffix for Vite
import dashboardIcon from '../assets/SVG/dk_dashboard.svg?url';
import usersIcon from '../assets/SVG/dk_users.svg?url';
import chatIcon from '../assets/SVG/dk_chat.svg?url';
import bankIcon from '../assets/SVG/dk_bank.svg?url';
import settingsIcon from '../assets/SVG/dk_settings.svg?url';
import passwordIcon from '../assets/SVG/dk_password.svg?url';
import userAddIcon from '../assets/SVG/dk_users.svg?url'; // Using users icon for userAdd
import chatClearIcon from '../assets/SVG/dk_delete.svg?url'; // Using delete icon for chatClear
import checkmarkIcon from '../assets/SVG/dk_checkmark.svg?url';
import refreshIcon from '../assets/SVG/dk_refresh.svg?url';
import forwardIcon from '../assets/SVG/dk_forward.svg?url';
import lightThemeIcon from '../assets/SVG/dk_light_theme.svg?url';
import darkThemeIcon from '../assets/SVG/dk_dark_theme.svg?url';
import closeIcon from '../assets/SVG/dk_close.svg?url';
import enterIcon from '../assets/SVG/dk_enter.svg?url';
import waitIcon from '../assets/SVG/dk_wait.svg?url';
import deleteIcon from '../assets/SVG/dk_delete.svg?url';
import powerOffIcon from '../assets/SVG/dk_power_off.svg?url';

const Icon = ({
    name,
    size = 'default',
    className = '',
    style = {},
    onClick = null
}) => {
    const sizeClasses = {
        small: 'crash-pay-icon-small',
        default: 'crash-pay-icon',
        large: 'crash-pay-icon-large'
    };

    // Map icon names to imported assets
    const iconSources = {
        dashboard: dashboardIcon,
        users: usersIcon,
        chat: chatIcon,
        bank: bankIcon,
        settings: settingsIcon,
        password: passwordIcon,
        userAdd: userAddIcon,
        chatClear: chatClearIcon,
        checkmark: checkmarkIcon,
        refresh: refreshIcon,
        forward: forwardIcon,
        lightTheme: lightThemeIcon,
        darkTheme: darkThemeIcon,
        close: closeIcon,
        enter: enterIcon,
        wait: waitIcon,
        delete: deleteIcon,
        powerOff: powerOffIcon
    };

    const iconSrc = iconSources[name];

    if (!iconSrc) {
        console.warn(`Icon '${name}' not found`);
        return null;
    }

    return (
        <img
            src={iconSrc}
            alt={name}
            className={`${sizeClasses[size]} ${className}`}
            style={{
                ...style
            }}
            onClick={onClick}
        />
    );
};

export default Icon; 