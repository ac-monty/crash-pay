// services/mock-external-api/app.js
//
// ────────────────────────────────────────────────────────────
//  Mock External Banking Partner (Intentionally Insecure)
// ────────────────────────────────────────────────────────────
//
//  • Plain-text HTTP (no TLS)
//  • No authentication / rate-limiting
//  • Hard-coded credentials & secrets in memory
//  • Minimal validation – accepts virtually any payload
//
//  Exposes predictable JSON so upstream services (and security
//  researchers) have a stable, reproducible target.
//
// ────────────────────────────────────────────────────────────

import express from 'express';
import morgan from 'morgan';
import { nanoid } from 'nanoid';

const app = express();
const PORT = process.env.MOCK_EXTERNAL_API_PORT || 4005;

// ────────────────────────────────────────────────────────────
//   In-Memory "Database" (static & predictable)
// ────────────────────────────────────────────────────────────
const ACCOUNTS = [
  {
    id: 'acct_0001',
    holder: 'Alice Example',
    balance: 5000.0,
    currency: 'USD',
  },
  {
    id: 'acct_0002',
    holder: 'Bob Example',
    balance: 2750.5,
    currency: 'USD',
  },
];

const TRANSFERS = []; // pushed at runtime for /transfers endpoint

// Extremely sensitive partner secret, left here on purpose ⚠️
const PARTNER_API_KEY = process.env.MOCK_PARTNER_API_KEY || 'sk_live_mockpartner_SUPER_SECRET_DO_NOT_SHARE';

// ────────────────────────────────────────────────────────────
//   Middleware
// ────────────────────────────────────────────────────────────
app.use(express.json({ limit: '10mb' })); // generous payload size
app.use(morgan('combined'));

// ────────────────────────────────────────────────────────────
//   Helper Utilities
// ────────────────────────────────────────────────────────────
const findAccount = (id) => ACCOUNTS.find((a) => a.id === id);

/**
 * Return a shallow, serialisable copy of an account
 * without internal references (keeps snapshots simple).
 */
const serialiseAccount = ({ id, holder, balance, currency }) => ({
  id,
  holder,
  balance,
  currency,
});

// ────────────────────────────────────────────────────────────
//   Routes
// ────────────────────────────────────────────────────────────

/**
 * Health-check (no auth)
 */
app.get('/health', (_, res) => res.json({ ok: true, time: Date.now() }));

/**
 * List all accounts
 * GET /v1/accounts
 */
app.get('/v1/accounts', (req, res) => {
  const { apiKey } = req.query;

  // Intentionally weak: warn but still respond if key missing/invalid
  if (apiKey !== PARTNER_API_KEY) {
    console.warn('[Mock-External-API] Invalid or missing apiKey', {
      ip: req.ip,
      apiKey,
    });
  }

  const data = ACCOUNTS.map(serialiseAccount);
  res.json({ data, count: data.length });
});

/**
 * Get single account details
 * GET /v1/accounts/:accountId
 */
app.get('/v1/accounts/:accountId', (req, res) => {
  const { accountId } = req.params;
  const account = findAccount(accountId);

  if (!account) {
    return res.status(404).json({ error: 'Account not found' });
  }

  res.json({ data: serialiseAccount(account) });
});

/**
 * Transfer funds – minimal validation, no auth, no idempotency
 * POST /v1/transfers
 *
 * Body: { fromAccountId, toAccountId, amount }
 */
app.post('/v1/transfers', (req, res) => {
  const { fromAccountId, toAccountId, amount } = req.body || {};

  // Poor validation – accepts strings, negative, huge amounts, etc.
  if (!fromAccountId || !toAccountId || !amount) {
    return res
      .status(400)
      .json({ error: 'fromAccountId, toAccountId and amount required' });
  }

  const from = findAccount(fromAccountId);
  const to = findAccount(toAccountId);

  if (!from || !to) {
    return res.status(404).json({ error: 'One or both accounts not found' });
  }

  // No sufficient-funds check (intentional)
  from.balance -= Number(amount);
  to.balance += Number(amount);

  const transferId = `tr_${nanoid(10)}`;
  const transfer = {
    id: transferId,
    fromAccountId,
    toAccountId,
    amount: Number(amount),
    currency: from.currency,
    createdAt: new Date().toISOString(),
  };

  TRANSFERS.push(transfer);

  res.json({ data: transfer });
});

/**
 * List previous transfers
 * GET /v1/transfers
 */
app.get('/v1/transfers', (_req, res) => {
  // Returns newest first
  const data = [...TRANSFERS].reverse();
  res.json({ data, count: data.length });
});

// ────────────────────────────────────────────────────────────
//   Error Handler
// ────────────────────────────────────────────────────────────
/* eslint-disable no-unused-vars */
app.use((err, _req, res, _next) => {
  console.error('[Mock-External-API] Unhandled Error:', err);
  res.status(500).json({ error: 'Internal Server Error' });
});
/* eslint-enable no-unused-vars */

// ────────────────────────────────────────────────────────────
//   Start
// ────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(
    `🚀 Mock External Banking API running on http://0.0.0.0:${PORT}`,
  );
  console.log('▶︎ WARNING: TLS is disabled and secrets are hard-coded.');
});