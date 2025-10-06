import express from 'express';
import db from '../models/index.js';

const router = express.Router();
const { CreditScore } = db;

router.get('/:userId', async (req, res) => {
    try {
        const score = await CreditScore.findOrCreate({ where: { userId: req.params.userId } });
        res.json(score[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch credit score' });
    }
});

export default router;