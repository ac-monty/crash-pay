import express from 'express';
import db from '../models/index.js';

const router = express.Router();
const { SavingsBucket, Account, Transaction } = db;

router.get('/', async (req, res) => {
    try {
        const buckets = await SavingsBucket.findAll();
        res.json(buckets);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch savings buckets' });
    }
});

router.get('/:userId', async (req, res) => {
    try {
        const bucket = await SavingsBucket.findOne({ where: { userId: req.params.userId } });
        if (!bucket) {
            // Create default bucket if none exists
            const newBucket = await SavingsBucket.create({
                userId: req.params.userId,
                balance: 0.00,
                apy: 2.5
            });
            return res.json(newBucket);
        }
        res.json(bucket);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch savings bucket' });
    }
});

router.post('/deposit', async (req, res) => {
    const { userId, amount } = req.body;
    try {
        const amt = parseFloat(amount);
        if (Number.isNaN(amt) || amt <= 0) return res.status(400).json({ error: 'Invalid amount' });

        const result = await db.sequelize.transaction(async (t) => {
            // 1) lock checking account
            const checking = await db.Account.findOne({ where: { userId, type: 'CHECKING' }, lock: t.LOCK.UPDATE, transaction: t });
            if (!checking) throw new Error('Checking account not found');
            if (parseFloat(checking.balance) < amt) throw new Error('Insufficient checking balance');

            // 2) deduct from checking
            checking.balance = parseFloat(checking.balance) - amt;
            await checking.save({ transaction: t });

            // 3) get/create savings bucket
            const [bucket, created] = await SavingsBucket.findOrCreate({ where: { userId }, defaults: { balance: 0.0, apy: 2.5 }, lock: t.LOCK.UPDATE, transaction: t });
            bucket.balance = parseFloat(bucket.balance) + amt;
            await bucket.save({ transaction: t });

            // 4) ensure savings account exists and mirrors bucket balance
            const [savingsAcc] = await db.Account.findOrCreate({ where: { userId, type: 'SAVINGS' }, defaults: { balance: 0 }, lock: t.LOCK.UPDATE, transaction: t });
            savingsAcc.balance = bucket.balance;
            await savingsAcc.save({ transaction: t });

            // 5) create transaction feed entry (Account = SAVINGS)
            await Transaction.create({
                userId,
                accountId: savingsAcc.id,
                accountType: savingsAcc.type,
                amount: amt,
                description: 'Savings Deposit',
                status: 'SETTLED'
            }, { transaction: t });

            return { bucket, checking, savingsAcc };
        });

        res.json(result.bucket);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: err.message });
    }
});

router.post('/withdraw', async (req, res) => {
    const { userId, amount } = req.body;
    try {
        const amt = parseFloat(amount);
        if (Number.isNaN(amt) || amt <= 0) return res.status(400).json({ error: 'Invalid amount' });

        const result = await db.sequelize.transaction(async (t) => {
            // 1) savings bucket
            const bucket = await SavingsBucket.findOne({ where: { userId }, lock: t.LOCK.UPDATE, transaction: t });
            if (!bucket) throw new Error('Bucket not found');
            if (parseFloat(bucket.balance) < amt) throw new Error('Insufficient savings balance');

            bucket.balance = parseFloat(bucket.balance) - amt;
            await bucket.save({ transaction: t });

            // 2) checking account
            const checking = await db.Account.findOne({ where: { userId, type: 'CHECKING' }, lock: t.LOCK.UPDATE, transaction: t });
            if (!checking) throw new Error('Checking account not found');
            checking.balance = parseFloat(checking.balance) + amt;
            await checking.save({ transaction: t });

            // 3) update savings account mirror
            const savingsAcc = await db.Account.findOne({ where: { userId, type: 'SAVINGS' }, lock: t.LOCK.UPDATE, transaction: t });
            if (savingsAcc) {
                savingsAcc.balance = bucket.balance;
                await savingsAcc.save({ transaction: t });
            }

            // 4) create transaction feed entry (Account = CHECKING for inflow)
            await Transaction.create({
                userId,
                accountId: checking.id,
                accountType: checking.type,
                amount: -amt,
                description: 'Savings Withdrawal',
                status: 'SETTLED'
            }, { transaction: t });

            return { bucket, checking };
        });

        res.json(result.bucket);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: err.message });
    }
});

export default router;