// services/transaction-service/src/index.js
//
// Entry point for the Finance Service

import app, { initDatabase } from './app.js';
import db from './models/index.js';

const PORT = process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002;

async function start() {
    try {
        // Initialize database connections
        await initDatabase();

        // Start the server
        app.listen(PORT, () => {
            console.log(`🚀 Finance Service running on port ${PORT}`);
            console.log('▶︎ Environment:', process.env.NODE_ENV || 'development');

            // Periodic jobs – run every 60 seconds
            setInterval(async () => {
                try {
                    // Savings interest accrual (very rough: +0.01% per minute)
                    const { SavingsBucket, CreditScore, Account, Loan } = db;
                    await SavingsBucket.increment({ balance: db.sequelize.literal('balance * 0.0001') }, { where: {} });

                    // Sync SAVINGS account balances to match buckets
                    const buckets = await SavingsBucket.findAll();
                    for (const bucket of buckets) {
                        await Account.update(
                            { balance: bucket.balance },
                            { where: { userId: bucket.userId, type: 'SAVINGS' } }
                        );
                    }

                    // Loan interest accrual: grow outstanding by 0.01% per minute for ACTIVE loans
                    await Loan.increment({ outstanding: db.sequelize.literal('outstanding * 0.0001') }, { where: { status: 'ACTIVE' } });

                    // Credit score random walk ±5
                    const allScores = await CreditScore.findAll();
                    // eslint-disable-next-line no-restricted-syntax
                    for (const cs of allScores) {
                        const delta = Math.floor(Math.random() * 11) - 5; // -5..+5
                        cs.score = Math.min(850, Math.max(300, cs.score + delta));
                        cs.lastPulledAt = new Date();
                        // eslint-disable-next-line no-await-in-loop
                        await cs.save();
                    }
                } catch (err) {
                    console.error('[finance-service] interval job error', err);
                }
            }, 60_000); // 60s
        });
    } catch (err) {
        console.error('[finance-service] Fatal start-up error:', err);
        process.exit(1);
    }
}

start(); 