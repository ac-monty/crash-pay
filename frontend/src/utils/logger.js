/* eslint-disable no-console */
// Lightweight logger utility so we don't sprinkle raw console.log everywhere.
// Usage: import { log } from './logger'; log('AccountsPanel mounted', { props });
// Can be replaced by a real logging lib later.

export function log(message, meta) {
    const timestamp = new Date().toISOString();
    if (meta !== undefined) {
        console.log(`[CP-LOG ${timestamp}] ${message}`, meta);
    } else {
        console.log(`[CP-LOG ${timestamp}] ${message}`);
    }
}

