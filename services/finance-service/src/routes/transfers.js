import express from 'express';
import db from '../models/index.js';
import Sequelize from 'sequelize';

const router = express.Router();
const { Transfer, Account, Transaction, SavingsBucket, sequelize } = db;

router.post('/', async (req, res) => {
    const { fromAccountId, toAccountId, amount, description } = req.body;
    try {
        const amt = parseFloat(amount);
        if (Number.isNaN(amt) || amt <= 0) {
            return res.status(400).json({ error: 'Invalid amount' });
        }

        const result = await sequelize.transaction(async (t) => {
            const from = await Account.findByPk(fromAccountId, { transaction: t, lock: t.LOCK.UPDATE });
            const to = await Account.findByPk(toAccountId, { transaction: t, lock: t.LOCK.UPDATE });
            if (!from || !to) throw new Error('Account not found');
            if (parseFloat(from.balance) < amt) throw new Error('Insufficient funds');

            from.balance = parseFloat(from.balance) - amt;
            to.balance = parseFloat(to.balance) + amt;
            await from.save({ transaction: t });
            await to.save({ transaction: t });

            // Keep SavingsBucket in sync if a savings account is involved
            if (to.type === 'SAVINGS') {
                const bucket = await SavingsBucket.findOrCreate({ where: { userId: to.userId }, defaults: { balance: 0.0, apy: 2.5 }, transaction: t, lock: t.LOCK.UPDATE });
                const bucketInstance = Array.isArray(bucket) ? bucket[0] : bucket;
                bucketInstance.balance = parseFloat(bucketInstance.balance) + amt;
                await bucketInstance.save({ transaction: t });
            }
            if (from.type === 'SAVINGS') {
                const bucket = await SavingsBucket.findOne({ where: { userId: from.userId }, transaction: t, lock: t.LOCK.UPDATE });
                if (bucket) {
                    bucket.balance = parseFloat(bucket.balance) - amt;
                    await bucket.save({ transaction: t });
                }
            }

            const transfer = await Transfer.create({ fromAccountId, toAccountId, amount: amt, description, status: 'SETTLED' }, { transaction: t });

            // Create Transaction records for activity feed
            await Transaction.bulkCreate([
                {
                    userId: from.userId,
                    accountId: from.id,
                    accountType: from.type,
                    amount: -amt,
                    description: description || `Transfer to ${to.type}`,
                    status: 'SETTLED',
                },
                {
                    userId: to.userId,
                    accountId: to.id,
                    accountType: to.type,
                    amount: amt,
                    description: description || `Transfer from ${from.type}`,
                    status: 'SETTLED',
                },
            ], { transaction: t });

            return transfer;
        });

        res.status(201).json(result);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: err.message });
    }
});

export default router;