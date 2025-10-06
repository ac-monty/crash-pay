const express = require('express');
const { Op, Sequelize } = require('sequelize');
const { User } = require('../models');             // User model from models/index.js
const jwt = require('jsonwebtoken');
const axios = require('axios');
const bcrypt = require('bcryptjs');
// const { MongoClient } = require('mongodb');

// APM instrumentation for error tracking
const { captureError, captureMessage, startSpan, endSpan } = require('../../../shared/utils/apm');

const router = express.Router();


// Get JWT secret from environment
const JWT_SECRET = process.env.JWT_SECRET || 'super-secret-not-safe';
// Audience claim expected by llm-service validator
const JWT_AUDIENCE = process.env.OAUTH_AUDIENCE || 'llm-service';

/* =========================================================================
 * ⚠️  INTENTIONALLY INSECURE ROUTES
 * -------------------------------------------------------------------------
 * • No input validation or sanitisation
 * • Over-privileged SQL queries (some raw, string-concatenated)
 * • Hard-coded JWT secret + long-lived tokens
 * • Missing rate-limiting / brute-force protections
 * • No CSRF or same-site cookie flags
 * • Verbose error responses leaking stack traces
 * ========================================================================= */

/**
 * POST /register
 * Creates a new user record.
 * Body: { username, email, password }
 */
router.post('/register', async (req, res) => {
  try {
    const { username, email, password } = req.body;          // ⚠️  no validation / hashing
    const user = await User.create({ username, email, password });
    res.status(201).json({ ok: true, user });
  } catch (err) {
    console.error('[register] error:', err);

    // Capture registration errors in APM
    captureError(err, {
      labels: {
        error_type: 'user_registration_failure',
        service: 'user-service',
        endpoint: '/register',
        username: req.body?.username
      }
    });

    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * POST /login
 * Very naive login that returns a JWT if the first record matches.
 * Body: { username, password }
 */
router.post('/login', async (req, res) => {
  try {
    const { username, password } = req.body;                 // ⚠️  plaintext comparison
    const { Tier, Role } = require('../models');
    const user = await User.findOne({
      where: { username, password },
      include: [Tier, Role]
    });

    if (!user) {
      // Capture failed login attempts as security events
      captureMessage(`Failed login attempt for username: ${username}`, 'warning', {
        labels: {
          security_event: 'failed_login_attempt',
          service: 'user-service',
          endpoint: '/login',
          username: username
        }
      });

      return res.status(401).json({ ok: false, error: 'Invalid credentials' });
    }

    const roleNames = user.Roles.map(r => r.name);
    const tierName = user.Tier ? user.Tier.name : 'basic';

    // Build scopes/permissions from DB role→scope mapping
    const { Scope } = require('../models');
    const scopeRows = await Scope.findAll({
      include: [{ model: Role, where: { name: roleNames } }],
    });

    const permissions = [...new Set(scopeRows.map(s => s.name))];
    const scopeStr = permissions.join(' ');

    // STEP 1: create a temporary token (without fxn) so llm-service can authenticate our request
    const tempToken = jwt.sign({
      sub: user.id,
      username: user.username,
      scope: scopeStr,
      roles: roleNames,
      membership_tier: tierName,
      aud: JWT_AUDIENCE,
    }, JWT_SECRET, { expiresIn: '5m' });

    let permittedFunctions = [];
    try {
      const llmUrl = `http://llm-service:${process.env.LLM_SERVICE_INTERNAL_PORT || 8000}/api/llm/auth/permissions`;
      const resp = await axios.get(llmUrl, {
        headers: { Authorization: `Bearer ${tempToken}` },
        timeout: 5000
      });
      permittedFunctions = resp.data?.permitted_functions || [];
      console.log('🎟️  Permitted functions for user', user.username, permittedFunctions);
    } catch (permErr) {
      console.warn('⚠️  Failed to fetch permitted functions, issuing token with empty fxn:', permErr.message);
    }

    // STEP 2: issue final token embedding fxn claim (short alias)
    const finalTokenPayload = {
      sub: user.id,
      username: user.username,
      scope: scopeStr,
      roles: roleNames,
      membership_tier: tierName,
      aud: JWT_AUDIENCE,
      fxn: permittedFunctions,  // <- consumed by llm-service
      permissions,
    };

    // ⚠️ Still using long-lived tokens for the lab
    const token = jwt.sign(finalTokenPayload, JWT_SECRET, { expiresIn: '30d' });

    res.json({ ok: true, token });
  } catch (err) {
    console.error('[login] error:', err);

    // Capture login errors in APM
    captureError(err, {
      labels: {
        error_type: 'login_system_failure',
        service: 'user-service',
        endpoint: '/login',
        username: req.body?.username
      }
    });

    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * GET /users
 * Returns every user in the system. No auth required.
 */
router.get('/users', async (req, res) => {
  try {
    const { name } = req.query;
    const { Tier, Role } = require('../models');
    // If a name query param is supplied, perform a case-insensitive search instead of returning **everything**
    if (name) {
      const users = await User.findAll({
        where: {
          name: { [Op.iLike]: `%${name}%` }
        },
        attributes: ['id', 'name'], // lean payload for auto-complete
        limit: 20,
        order: [['name', 'ASC']]
      });
      return res.json({ ok: true, users });
    }

    // Default behaviour – return full list with joins (existing implementation)
    const users = await User.findAll({ include: [Tier, Role] });
    res.json({ ok: true, users });
  } catch (err) {
    console.error('[list-users] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * GET /users/:id
 * Uses a raw, unsanitised SQL query that is vulnerable to SQL injection.
 */
router.get('/users/:id', async (req, res) => {
  try {
    const { id } = req.params;                               // ⚠️  unsanitised

    // Track potential SQL injection attempts
    if (id && (id.includes(';') || id.includes('--') || id.includes('DROP') || id.includes('DELETE'))) {
      captureMessage(`Potential SQL injection attempt detected: ${id}`, 'warning', {
        labels: {
          security_event: 'sql_injection_attempt',
          service: 'user-service',
          endpoint: '/users/:id',
          suspicious_input: id,
          user_ip: req.ip
        }
      });
    }

    const result = await User.sequelize.query(
      `SELECT * FROM "Users" WHERE id = ${id}`,              // ⚠️  SQLi
      { type: Sequelize.QueryTypes.SELECT }
    );
    if (!result.length) {
      return res.status(404).json({ ok: false, error: 'User not found' });
    }
    res.json({ ok: true, user: result[0] });
  } catch (err) {
    console.error('[get-user] error:', err);

    // Capture SQL errors (could indicate injection attempts)
    captureError(err, {
      labels: {
        error_type: 'sql_query_failure',
        service: 'user-service',
        endpoint: '/users/:id',
        user_id_param: req.params?.id,
        potential_injection: true
      }
    });

    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * PUT /users/:id
 * Updates arbitrary columns based on request body (mass-assignment).
 */
router.put('/users/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const [affected] = await User.update(req.body, { where: { id } }); // ⚠️  mass assignment
    if (!affected) {
      return res.status(404).json({ ok: false, error: 'User not found' });
    }
    const user = await User.findByPk(id);
    res.json({ ok: true, user });
  } catch (err) {
    console.error('[update-user] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * DELETE /users/:id
 * Removes a user account with no authentication or confirmation.
 */
router.delete('/users/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const removed = await User.destroy({ where: { id } });
    if (!removed) {
      return res.status(404).json({ ok: false, error: 'User not found' });
    }
    res.json({ ok: true, message: `User ${id} deleted` });
  } catch (err) {
    console.error('[delete-user] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * GET /debug/env
 * Dumps all environment variables — classic information disclosure.
 */
router.get('/debug/env', (_req, res) => {
  res.json({ env: process.env });                             // ⚠️  leaks secrets
});

/**
 * POST /admin/login
 * Admin authentication endpoint
 */
router.post('/admin/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    // Check against env vars (intentionally insecure)
    if (username === process.env.ADMIN_USERNAME && password === process.env.ADMIN_PASSWORD) {
      const token = jwt.sign(
        {
          id: 'admin',
          username: username,
          role: 'admin'
        },
        JWT_SECRET,
        { expiresIn: '8h' }
      );

      res.json({
        ok: true,
        token,
        user: {
          id: 'admin',
          username,
          role: 'admin',
          email: process.env.ADMIN_EMAIL
        }
      });
    } else {
      res.status(401).json({ ok: false, error: 'Invalid admin credentials' });
    }
  } catch (err) {
    console.error('[admin-login] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * POST /admin/generate-users
 * AI-powered fake user generation
 */
router.post('/admin/generate-users', async (req, res) => {
  try {
    const { userCount = 10 } = req.body;

    // Call LLM service to generate realistic user data
    const prompt = `Generate ${userCount} realistic fake user profiles for a fintech application.\n\nReturn ONLY the raw JSON array (no markdown, no prose). Each object must contain:\n  - \"name\": full name (e.g., \"Sofia Garcia\")\n  - \"ssn\": string in the format \"XXX-XX-XXXX\"\n  - \"balance\": number between 100 and 50000\n\nExample format:\n[\n  {\"name\":\"John Smith\",\"ssn\":\"123-45-6789\",\"balance\":1234},\n  {\"name\":\"Maria Lopez\",\"ssn\":\"987-65-4321\",\"balance\":5230}\n]`;

    const llmResponse = await axios.post(`http://llm-service:${process.env.LLM_SERVICE_INTERNAL_PORT || 8000}/api/v1/chat`, {
      prompt,
      temperature: 0,
      stream: false
    });

    let generatedUsers;
    try {
      console.log('LLM raw data:', llmResponse.data);

      // Extract JSON from LLM response
      const responseText = llmResponse.data.response || llmResponse.data.token || '';

      // Clean markdown fences and surrounding text
      let cleaned = responseText.replace(/```[\s\S]*?```/g, '').trim();

      // Attempt to locate JSON array
      const startIdx = cleaned.indexOf('[');
      if (startIdx !== -1) {
        const jsonText = cleaned.slice(startIdx);
        try {
          generatedUsers = JSON.parse(jsonText);
        } catch (parseErr) {
          console.error('⚠️ Failed JSON.parse on extracted text:', parseErr.message);
        }
      }

      if (!generatedUsers) {
        throw new Error('No JSON array found in LLM response');
      }
    } catch (parseErr) {
      console.error('Failed to parse LLM response. Raw text:\n', llmResponse.data.response || llmResponse.data.token);
      console.error('Parse error:', parseErr);
      // Fallback to simple generation
      const timestamp = Date.now();
      generatedUsers = Array.from({ length: userCount }, (_, i) => ({
        name: `Generated User ${timestamp}-${i + 1}`,
        ssn: `${(timestamp + i).toString().slice(-3).padStart(3, '0')}-${Math.floor(Math.random() * 99).toString().padStart(2, '0')}-${Math.floor(Math.random() * 9999).toString().padStart(4, '0')}`,
        balance: Math.floor(Math.random() * 49900) + 100
      }));
    }

    // Create users in database
    const createdUsers = [];
    for (const userData of generatedUsers) {
      try {
        const { Tier, Role } = require('../models');
        // Random tier & roles
        const tiers = ['basic', 'premium', 'director'];
        const rolesPool = ['customer', 'advisor'];
        const tierName = tiers[Math.floor(Math.random() * tiers.length)];
        const roleNames = ['customer'];
        if (Math.random() < 0.1) roleNames.push('advisor');

        // ensure tier exists
        const tier = await Tier.findOrCreate({ where: { name: tierName } });

        const user = await User.create({
          ...userData,
          password: 'user',
          tier_id: tier[0].id
        });

        // attach roles
        const roles = await Role.findAll({ where: { name: roleNames } });
        await user.setRoles(roles);
        // ────────────────────────────────────────────────────────────
        // Create single checking account and realistic transaction history
        // ────────────────────────────────────────────────────────────
        let runningBalance = 0;
        let accountId;
        try {
          // 1) Create the account with zero balance first
          const accRes = await axios.post(`http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}/accounts`, {
            userId: user.id,
            type: 'CHECKING',
            balance: 0
          });
          accountId = accRes.data.id;

          // 2) Initial deposit equal to original generated balance
          runningBalance += userData.balance;
          await axios.post(`http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}/transactions`, {
            userId: user.id,
            accountId: accountId,
            accountType: 'CHECKING',
            amount: userData.balance,
            description: 'Initial deposit',
            status: 'SETTLED'
          });

          // 3) Nine additional random deposits / withdrawals
          for (let i = 0; i < 9; i++) {
            let amt = parseFloat(((Math.random() - 0.4) * 800).toFixed(2)); // roughly -320 to +480
            if (runningBalance + amt < 0) {
              amt = Math.abs(amt); // prevent negative balance
            }
            runningBalance += amt;
            await axios.post(`http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}/transactions`, {
              userId: user.id,
              accountId: accountId,
              accountType: 'CHECKING',
              amount: amt,
              description: amt >= 0 ? 'Deposit' : 'Withdrawal',
              status: 'SETTLED'
            });
          }

          // 4) Update account and user balance to final value
          await axios.put(`http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}/accounts/${accountId}`, {
            balance: runningBalance
          });
          await user.update({ balance: runningBalance });

        } catch (finErr) {
          console.error('Finance-service correlation failure:', finErr.message);
        }

        createdUsers.push(user);
      } catch (err) {
        console.error('Failed to create user:', err.message);
      }
    }

    res.json({
      ok: true,
      message: `Generated ${createdUsers.length} users`,
      users: createdUsers,
      usedLLM: generatedUsers !== null
    });
  } catch (err) {
    console.error('[generate-users] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * POST /admin/generate-transactions
 * AI-powered fake transaction generation
 */
// ────────────────────────────────────────────────────────────
// POST /admin/reset – wipe all users/finance data (lab only)
// ────────────────────────────────────────────────────────────
router.post('/admin/reset', async (req, res) => {
  try {
    // 1) Delete all users (cascades to junction tables). Keep admin if exists.
    await User.destroy({ where: { role: { [Op.ne]: 'admin' } }, truncate: true, cascade: true, restartIdentity: true });

    // 2) Call finance-service reset endpoint to truncate its tables
    try {
      await axios.post(`http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}/admin/reset`);
    } catch (finErr) {
      console.error('Finance-service reset failed:', finErr.message);
    }

    res.json({ ok: true, message: 'System reset complete' });
  } catch (err) {
    console.error('[admin-reset] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

router.post('/admin/generate-transactions', async (req, res) => {
  try {
    const { transactionCount = 20 } = req.body;

    // Get all users to create transactions for
    const users = await User.findAll();
    if (users.length === 0) {
      return res.status(400).json({ ok: false, error: 'No users found. Create users first.' });
    }

    // Generate realistic transaction data using LLM
    const prompt = `Generate ${transactionCount} realistic banking transactions for a fintech app. Return a JSON array with objects containing: amount (between -500 and 2000, can be negative for payments), description (realistic transaction descriptions like "Amazon Purchase", "Salary Deposit", "ATM Withdrawal", "Transfer to John", etc.). Make it diverse and realistic.`;

    let generatedTransactions;
    try {
      const llmResponse = await axios.post(`http://llm-service:${process.env.LLM_SERVICE_INTERNAL_PORT || 8000}/api/v1/chat`, {
        prompt: prompt,
        temperature: 0.2,
        stream: false
      });

      // Extract JSON from LLM response
      const responseText = llmResponse.data.response || llmResponse.data.token || '';
      const jsonMatch = responseText.match(/\[[\s\S]*\]/);
      if (jsonMatch) {
        generatedTransactions = JSON.parse(jsonMatch[0]);
      } else {
        throw new Error('No JSON array found in LLM response');
      }
    } catch (parseErr) {
      console.error('Failed to parse LLM response:', parseErr);
      // Fallback to simple generation
      generatedTransactions = Array.from({ length: transactionCount }, (_, i) => ({
        amount: (Math.random() - 0.3) * 1000, // Bias towards positive amounts
        description: [
          'ATM Withdrawal', 'Grocery Store', 'Gas Station', 'Online Purchase',
          'Salary Deposit', 'Transfer Received', 'Bill Payment', 'Restaurant'
        ][i % 8]
      }));
    }

    // Create transactions via transaction service
    const createdTransactions = [];
    for (const transactionData of generatedTransactions) {
      try {
        // Assign to random user
        const randomUser = users[Math.floor(Math.random() * users.length)];

        // Choose a concrete account for this user (prefer CHECKING)
        let accountId = null;
        let accountType = 'CHECKING';
        try {
          const accRes = await axios.get(`http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}/accounts`, { params: { userId: randomUser.id } });
          const accounts = accRes.data || [];
          const checking = accounts.find(a => String(a.type).toUpperCase() === 'CHECKING');
          const chosen = checking || accounts[0];
          if (chosen) {
            accountId = chosen.id;
            accountType = chosen.type;
          }
        } catch (accErr) {
          console.error('Failed to fetch user accounts for transaction seeding:', accErr.message);
        }

        const transactionPayload = {
          userId: randomUser.id,
          accountId,
          accountType,
          amount: parseFloat(transactionData.amount.toFixed(2)),
          description: transactionData.description,
          status: Math.random() > 0.1 ? 'SETTLED' : 'PENDING' // 90% settled, 10% pending
        };

        // Call transaction service
        const response = await axios.post(`http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}/transactions`, transactionPayload);
        createdTransactions.push(response.data);
      } catch (err) {
        console.error('Failed to create transaction:', err.message);
      }
    }

    res.json({
      ok: true,
      message: `Generated ${createdTransactions.length} transactions`,
      transactions: createdTransactions,
      usedLLM: generatedTransactions !== null
    });
  } catch (err) {
    console.error('[generate-transactions] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * GET /admin/stats
 * Dashboard statistics
 */
router.get('/admin/stats', async (req, res) => {
  try {
    const userCount = await User.count();

    // Get transaction count from transaction service
    let transactionCount = 0;
    try {
      const response = await axios.get(`http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}/transactions`);
      transactionCount = response.data.length;
    } catch (err) {
      console.error('Failed to fetch transaction count:', err);
    }

    res.json({
      ok: true,
      stats: {
        totalUsers: userCount,
        totalTransactions: transactionCount,
        timestamp: new Date().toISOString()
      }
    });
  } catch (err) {
    console.error('[admin-stats] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * POST /banking/login
 * Simple banking login - username/ssn + password from user record
 */
router.post('/banking/login', async (req, res) => {
  try {
    const { identifier, password } = req.body; // identifier can be username or SSN

    // Find user by name or SSN (include Tier + Roles for claims)
    const { Tier, Role } = require('../models');
    const user = await User.findOne({
      where: {
        [Op.or]: [
          { name: identifier },
          { ssn: identifier }
        ]
      },
      include: [Tier, Role]
    });

    if (!user) {
      return res.status(401).json({ ok: false, error: 'User not found' });
    }

    // Check password against user's stored password (fallback to 'user' if not set)
    const userPassword = user.password || 'user';
    if (password !== userPassword) {
      return res.status(401).json({ ok: false, error: `Invalid password` });
    }

    // Derive dynamic claims from DB
    const roleNames = user.Roles && user.Roles.length > 0
      ? user.Roles.map(r => r.name)
      : ['customer'];
    const tierName = user.Tier ? user.Tier.name : 'basic';

    // Build scopes/permissions from DB role→scope mapping
    const { Scope } = require('../models');
    const scopeRowsBank = await Scope.findAll({
      include: [{ model: Role, where: { name: roleNames } }],
    });

    const permissions = [...new Set(scopeRowsBank.map(s => s.name))];
    const scopeStr = permissions.join(' ');

    // Generate enhanced token for banking session with llm-service compatible claims
    const enhancedPayload = {
      sub: user.id,                          // Subject (user ID) - required by llm-service
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + (8 * 60 * 60), // 8 hours in seconds
      aud: JWT_AUDIENCE,                     // Required audience 'llm-service'
      iss: 'user-service',                   // Issuer
      // Scopes and roles built dynamically below
      roles: roleNames,
      permissions,
      scope: scopeStr,
      verified: true,
      membership_tier: tierName,
      region: user.region || 'domestic',
      attributes: {                          // Additional user attributes
        user_name: user.name,
        banking_user: true
      },

      // Legacy fields for backward compatibility
      id: user.id,
      name: user.name,
      type: 'banking',
      role: 'user'
    };

    const token = jwt.sign(enhancedPayload, JWT_SECRET, { algorithm: 'HS256' });

    res.json({
      ok: true,
      token,
      user: {
        id: user.id,
        name: user.name,
        ssn: user.ssn,
        balance: user.balance
      }
    });
  } catch (err) {
    console.error('[banking-login] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * GET /banking/transactions/:userId
 * Get transactions for a specific user from transaction service
 */
router.get('/banking/transactions/:userId', async (req, res) => {
  try {
    const { userId } = req.params;

    // Get user transactions from transaction service
    const response = await axios.get(`http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}/transactions`);
    const allTransactions = response.data;

    // Filter transactions for this user
    const userTransactions = allTransactions.filter(tx => tx.userId === userId);

    // Sort by date (newest first)
    userTransactions.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

    res.json({
      ok: true,
      transactions: userTransactions
    });
  } catch (err) {
    console.error('[banking-transactions] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * GET /banking/profile/:userId
 * Get user profile for banking dashboard
 */
router.get('/banking/profile/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const user = await User.findByPk(userId);

    if (!user) {
      return res.status(404).json({ ok: false, error: 'User not found' });
    }

    res.json({
      ok: true,
      user: {
        id: user.id,
        name: user.name,
        ssn: user.ssn,
        balance: user.balance,
        createdAt: user.createdAt
      }
    });
  } catch (err) {
    console.error('[banking-profile] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

/**
 * POST /admin/clear-chat-sessions
 * Clear all chat sessions from MongoDB
 */
/*
router.post('/admin/clear-chat-sessions', async (req, res) => {
  try {
    // Connect to MongoDB and clear chat sessions
    const MONGO_URI = process.env.MONGO_URI || 'mongodb://mongo:27017/fakefintech';
    
    const mongoClient = new MongoClient(MONGO_URI);
    await mongoClient.connect();
    const db = mongoClient.db();
    
    const result = await db.collection('chat_sessions').deleteMany({});
    await mongoClient.close();
    
    res.json({
      ok: true,
      message: `Cleared ${result.deletedCount} chat sessions`,
      deletedCount: result.deletedCount
    });
  } catch (err) {
    console.error('[clear-chat-sessions] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});
*/

/**
 * POST /admin/change-user-password
 * Change a user's password for testing
 */
router.post('/admin/change-user-password', async (req, res) => {
  try {
    const { userId, newPassword, tierName, roles } = req.body;

    if (!userId) {
      return res.status(400).json({
        ok: false,
        error: 'userId is required'
      });
    }

    const user = await User.findByPk(userId);
    if (!user) {
      return res.status(404).json({
        ok: false,
        error: 'User not found'
      });
    }

    // For this demo app, we'll store passwords in plain text (intentionally insecure)
    // In a real app, you'd hash the password
    const updates = {};
    if (newPassword) updates.password = newPassword;

    if (tierName) {
      const { Tier } = require('../models');
      const [tierRow] = await Tier.findOrCreate({ where: { name: tierName } });
      updates.tier_id = tierRow.id;
    }

    await User.update(updates, { where: { id: userId } });

    // roles update
    if (roles && Array.isArray(roles)) {
      const { Role } = require('../models');
      const roleRows = await Role.findAll({ where: { name: roles } });
      const userInstance = await User.findByPk(userId);
      if (userInstance) {
        await userInstance.setRoles(roleRows);
      }
    }

    res.json({
      ok: true,
      message: `User updated`,
      userId: userId
    });
  } catch (err) {
    console.error('[change-user-password] error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

module.exports = router;