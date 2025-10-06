import express from 'express';
import bodyParser from 'body-parser';
import db from './models/index.js';

// Route modules
import transactionsRouter from './routes/transactions.js';
import accountsRouter from './routes/accounts.js';
import transfersRouter from './routes/transfers.js';
import savingsRouter from './routes/savings.js';
import loansRouter from './routes/loans.js';
import creditRouter from './routes/credit.js';
import tradingRouter from './routes/trading.js';
import adminRouter from './routes/admin.js';

const app = express();

// Large body limit, no content-type checks → potential DoS (OWASP-LLM 04)
app.use(bodyParser.json({ limit: '250mb', type: '*/*' }));

// Simple request logger – log to console for now
app.use(async (req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.originalUrl}`);
  next();
});

// Mount routers (intentionally no versioning/auth)
app.use('/transactions', transactionsRouter);
app.use('/accounts', accountsRouter);
app.use('/transfers', transfersRouter);
app.use('/savings', savingsRouter);
app.use('/loans', loansRouter);
app.use('/credit-score', creditRouter);
app.use('/admin', adminRouter);
app.use('/trading', tradingRouter);

// Healthcheck
app.get('/healthz', (_, res) => res.send('ok'));

// DB init helper
export async function initDatabase() {
  try {
    await db.sequelize.authenticate();
    await db.sequelize.sync({ alter: true }); // auto-migrate/alter for lab simplicity
    console.log('[finance-service] Connected to PostgreSQL');
  } catch (err) {
    console.error('[finance-service] Database initialization error:', err);
    throw err;
  }
}

export default app;
