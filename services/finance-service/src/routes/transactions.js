import express from 'express';
import db from '../models/index.js';

const router = express.Router();
const { Transaction, Account } = db;

// GET /transactions
router.get('/', async (req, res) => {
    try {
        const where = {};
        if (req.query.userId) {
            where.userId = req.query.userId;
        }
        const txns = await Transaction.findAll({ where });
        res.json(txns);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch transactions' });
    }
});

// GET /transactions/:id
router.get('/:id', async (req, res) => {
    try {
        const txn = await Transaction.findByPk(req.params.id);
        if (!txn) return res.status(404).json({ error: 'Not found' });
        res.json(txn);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch transaction' });
    }
});

// POST /transactions
router.post('/', async (req, res) => {
    try {
        const { userId, amount, description, status, accountId, accountType } = req.body || {};

        // Strict validation – no assumptions
        if (!userId || !accountId || !accountType) {
            return res.status(400).json({
                error: 'Missing required fields',
                details: 'userId, accountId and accountType are required'
            });
        }

        // Verify account exists and belongs to the user, and type matches
        const account = await Account.findByPk(accountId);
        if (!account) {
            return res.status(400).json({ error: 'Invalid accountId', details: 'Account not found' });
        }
        if (String(account.userId) !== String(userId)) {
            return res.status(400).json({ error: 'Account mismatch', details: 'Account does not belong to userId' });
        }
        const normalizedType = String(accountType).toUpperCase();
        if (String(account.type).toUpperCase() !== normalizedType) {
            return res.status(400).json({
                error: 'accountType mismatch',
                details: `Provided accountType '${accountType}' does not match account record '${account.type}'`
            });
        }

        const created = await Transaction.create({
            userId,
            accountId,
            accountType: account.type,
            amount,
            description,
            status,
        });
        res.status(201).json(created);
    } catch (err) {
        console.error('[transactions:create] error:', err);
        res.status(400).json({ error: 'Invalid payload', details: err.message });
    }
});

// PUT /transactions/:id
router.put('/:id', async (req, res) => {
    try {
        const txn = await Transaction.findByPk(req.params.id);
        if (!txn) return res.status(404).json({ error: 'Not found' });
        await txn.update(req.body);
        res.json(txn);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: 'Update failed', details: err.message });
    }
});

// DELETE /transactions/:id
router.delete('/:id', async (req, res) => {
    try {
        const deleted = await Transaction.destroy({ where: { id: req.params.id } });
        res.json({ deleted });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Deletion failed' });
    }
});

export default router;