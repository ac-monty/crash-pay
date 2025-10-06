import express from 'express';
import db from '../models/index.js';

const router = express.Router();

/**
 * POST /admin/reset
 * Danger: drops all finance tables (accounts, transactions, transfers, etc.)
 * Intended for demo resets only – no auth.
 */
router.post('/reset', async (_req, res) => {
    try {
        await db.sequelize.truncate({ cascade: true, restartIdentity: true });
        res.json({ ok: true, message: 'Finance data wiped' });
    } catch (err) {
        console.error('[finance-admin-reset] error:', err);
        res.status(500).json({ ok: false, error: err.message });
    }
});

export default router;
