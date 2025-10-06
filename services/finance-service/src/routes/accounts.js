import express from 'express';
import db from '../models/index.js';

const router = express.Router();
const { Account } = db;

router.get('/', async (req, res) => {
    try {
        const where = {};
        if (req.query.userId) {
            const userId = String(req.query.userId);
            // Guard: userId must be a UUID. If not, return empty result to avoid DB cast errors.
            const uuidV4Regex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
            if (!uuidV4Regex.test(userId)) {
                return res.json([]);
            }
            where.userId = userId;
        }
        const accounts = await Account.findAll({ where });
        res.json(accounts);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch accounts' });
    }
});

router.post('/', async (req, res) => {
    try {
        const created = await Account.create(req.body);
        res.status(201).json(created);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: 'Invalid payload', details: err.message });
    }
});

router.get('/:id', async (req, res) => {
    try {
        const account = await Account.findByPk(req.params.id);
        if (!account) return res.status(404).json({ error: 'Not found' });
        res.json(account);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch account' });
    }
});

router.put('/:id', async (req, res) => {
    try {
        const account = await Account.findByPk(req.params.id);
        if (!account) return res.status(404).json({ error: 'Not found' });
        await account.update(req.body);
        res.json(account);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: 'Update failed', details: err.message });
    }
});

router.delete('/:id', async (req, res) => {
    try {
        const deleted = await Account.destroy({ where: { id: req.params.id } });
        res.json({ deleted });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Deletion failed' });
    }
});

export default router;