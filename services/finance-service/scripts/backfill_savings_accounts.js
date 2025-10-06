// Small one-off script to ensure every user that has a SavingsBucket also has a matching
// SAVINGS account row so that /transfers endpoint can locate it.
// Usage (inside container): node --input-type=module scripts/backfill_savings_accounts.js

import db from '../src/models/index.js';

async function run() {
    const { SavingsBucket, Account } = db;
    console.log('🚀  Running savings-account back-fill');
    const buckets = await SavingsBucket.findAll();
    let createdCount = 0;
    for (const bucket of buckets) {
        const [acct, created] = await Account.findOrCreate({
            where: { userId: bucket.userId, type: 'SAVINGS' },
            defaults: { balance: bucket.balance, status: 'OPEN' },
        });
        if (created) {
            createdCount += 1;
            console.log(`Created SAVINGS account ${acct.id} for user ${bucket.userId}`);
        }
    }
    console.log(`✅  Back-fill complete – ${createdCount} new account(s) created.`);
    await db.sequelize.close();
}

run().catch((err) => {
    console.error(err);
    process.exit(1);
});

