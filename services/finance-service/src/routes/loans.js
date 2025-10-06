import express from 'express';
import db from '../models/index.js';

const router = express.Router();
const { Loan, Account, Transaction } = db;

router.get('/', async (req, res) => {
    try {
        const where = {};
        if (req.query.userId) {
            where.userId = req.query.userId;
        }
        const loans = await Loan.findAll({ where });
        res.json(loans);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Unable to fetch loans' });
    }
});

// Create a loan and fund user's checking (minus origination fee)
router.post('/', async (req, res) => {
    try {
        const { userId, principal, interestRate } = req.body;
        const p = parseFloat(principal);
        const apr = parseFloat(interestRate);
        if (!userId || Number.isNaN(p) || p <= 0 || Number.isNaN(apr) || apr <= 0) {
            return res.status(400).json({ error: 'Invalid payload' });
        }

        const result = await db.sequelize.transaction(async (t) => {
            // 1) Create loan with outstanding == principal
            const loan = await Loan.create({ userId, principal: p, outstanding: p, interestRate: apr, status: 'ACTIVE' }, { transaction: t });

            // 2) Ensure checking account exists
            const [checking] = await Account.findOrCreate({
                where: { userId, type: 'CHECKING' },
                defaults: { balance: 0, status: 'OPEN' },
                transaction: t,
                lock: t.LOCK.UPDATE,
            });

            // 3) Apply 1% origination fee (demo)
            const fee = +(p * 0.01).toFixed(2);
            const netProceeds = +(p - fee).toFixed(2);

            // 4) Credit checking with net proceeds
            checking.balance = parseFloat(checking.balance) + netProceeds;
            await checking.save({ transaction: t });

            // 5) Write transaction feed entries
            await Transaction.bulkCreate([
                { userId, accountId: checking.id, accountType: checking.type, amount: netProceeds, description: `Loan funded (${loan.id.slice(0, 8)})`, status: 'SETTLED' },
                { userId, accountId: checking.id, accountType: checking.type, amount: -fee, description: `Origination fee (${loan.id.slice(0, 8)})`, status: 'SETTLED' },
            ], { transaction: t });

            return loan;
        });

        res.status(201).json(result);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: 'Invalid payload', details: err.message });
    }
});

router.post('/:id/repay', async (req, res) => {
    try {
        const loan = await Loan.findByPk(req.params.id);
        if (!loan) return res.status(404).json({ error: 'Not found' });
        const amt = parseFloat(req.body.amount);
        if (Number.isNaN(amt) || amt <= 0) return res.status(400).json({ error: 'Invalid amount' });

        // Repay from user's CHECKING account within a transaction
        await db.sequelize.transaction(async (t) => {
            const checking = await Account.findOne({ where: { userId: loan.userId, type: 'CHECKING' }, transaction: t, lock: t.LOCK.UPDATE });
            if (!checking) throw new Error('Checking account not found');
            if (parseFloat(checking.balance) < amt) throw new Error('Insufficient funds');

            checking.balance = parseFloat(checking.balance) - amt;
            await checking.save({ transaction: t });

            loan.outstanding = Math.max(0, parseFloat(loan.outstanding) - amt);
            if (parseFloat(loan.outstanding) === 0) loan.status = 'PAID';
            await loan.save({ transaction: t });

            await Transaction.create({
                userId: loan.userId,
                accountId: checking.id,
                accountType: checking.type,
                amount: -amt,
                description: `Loan repayment (${loan.id.slice(0, 8)})`,
                status: 'SETTLED',
            }, { transaction: t });
        });

        const updated = await Loan.findByPk(req.params.id);
        res.json(updated);
    } catch (err) {
        console.error(err);
        res.status(400).json({ error: 'Repayment failed', details: err.message });
    }
});

export default router;