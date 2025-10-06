// Initialize APM first (must be before other requires)
let apm = null;
try {
  if (process.env.ELASTIC_APM_SERVER_URL) {
    apm = require('elastic-apm-node').start({
      serviceName: process.env.ELASTIC_APM_SERVICE_NAME || 'api-gateway',
      serverUrl: process.env.ELASTIC_APM_SERVER_URL,
      environment: process.env.NODE_ENV || 'development'
    });
    console.log('✅ APM initialized for API Gateway');
  } else {
    console.log('ℹ️ APM not configured (ELASTIC_APM_SERVER_URL not set)');
  }
} catch (error) {
  console.warn('⚠️ APM initialization failed:', error.message);
}

const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const http = require('http');
const jwt = require('jsonwebtoken');
const morgan = require('morgan');
const cors = require('cors');
const { MongoClient } = require('mongodb');
const crypto = require('crypto');

// Shared APM utility with graceful error handling
const { captureError, captureMessage, middleware: apmMiddleware, setApmInstance } = require('../../shared/utils/apm');

// Set the APM instance in the shared utility
if (apm) {
  setApmInstance(apm);
}

// MongoDB connection
const MONGO_URI = process.env.MONGO_URI || 'mongodb://mongo:27017/fakefintech';
let db;
let mongoClient;

// Initialize MongoDB connection
async function initMongoDB() {
  try {
    mongoClient = new MongoClient(MONGO_URI);
    await mongoClient.connect();
    db = mongoClient.db();
    console.log('📊 Connected to MongoDB for chat auditing');

    // Create indexes for better performance
    await db.collection('chat_sessions').createIndex({ sessionId: 1 });
    await db.collection('chat_sessions').createIndex({ userId: 1 });
    await db.collection('chat_sessions').createIndex({ timestamp: 1 });
  } catch (error) {
    console.error('❌ MongoDB connection failed:', error.message);
  }
}

// Initialize MongoDB on startup
initMongoDB();

// In-memory session storage (for active conversations)
const activeSessions = new Map();

const {
  PORT = 3030,
  JWT_SECRET = process.env.JWT_SECRET || 'super-secret-not-safe',
  JWT_EXPIRES_IN = '7d',
  USER_SERVICE_URL = `http://user-service:${process.env.USER_SERVICE_INTERNAL_PORT || 8081}`,
  FINANCE_SERVICE_URL = `http://finance-service:${process.env.FINANCE_SERVICE_INTERNAL_PORT || 4002}`,
  LLM_SERVICE_URL = `http://llm-service:${process.env.LLM_SERVICE_INTERNAL_PORT || 8000}`,
  RAG_SERVICE_URL = `http://rag-service:${process.env.RAG_SERVICE_INTERNAL_PORT || 8001}`,
  TOOLS_SERVICE_URL = `http://tools-service:${process.env.TOOLS_SERVICE_INTERNAL_PORT || 8002}`,
  MOCK_PARTNER_API_URL = `http://mock-external-api:${process.env.MOCK_EXTERNAL_API_INTERNAL_PORT || 4005}`,
  MODEL_REGISTRY_URL = `http://model-registry:${process.env.MODEL_REGISTRY_INTERNAL_PORT || 8050}`,
} = process.env;

const app = express();

// Timeouts (tunable via env, with safe defaults above frontend proxy)
const SERVER_TIMEOUT_MS = parseInt(process.env.GATEWAY_SERVER_TIMEOUT_MS || '190000', 10);
const HEADERS_TIMEOUT_MS = parseInt(process.env.GATEWAY_HEADERS_TIMEOUT_MS || '195000', 10);
const PROXY_TIMEOUT_MS = parseInt(process.env.GATEWAY_PROXY_TIMEOUT_MS || '190000', 10);

// ────────────────────────────────────────────────────────────
// Global Middleware
// ────────────────────────────────────────────────────────────
app.use(cors({
  origin: true, // Allow all origins
  credentials: true, // Allow credentials
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], // Explicitly include OPTIONS
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With'], // Allow common headers
  exposedHeaders: ['X-Session-Id', 'X-Message-Count', 'X-User-Id'] // Expose custom headers to frontend
})); // Allows everything
app.use(morgan('combined'));
app.use(express.json({ limit: '1gb' })); // effectively "no limit"
app.use(express.urlencoded({ extended: true, limit: '1gb' }));

// ────────────────────────────────────────────────────────────
// JWT Helpers (Insecure by Design)
//  • Hard-coded secret fallback
//  • Verbose error messages
// ────────────────────────────────────────────────────────────
function signToken(payload, expiresIn = '7d') {
  return jwt.sign(payload, JWT_SECRET, { expiresIn });
}

function jwtMiddleware(req, res, next) {
  const auth = req.headers.authorization || '';
  const token = auth.replace(/^Bearer /i, '');

  if (!token) {
    return res.status(401).json({
      error: 'No bearer token provided – access denied',
    });
  }

  jwt.verify(token, JWT_SECRET, (err, decoded) => {
    if (err) {
      // Overly detailed error output (intentional)
      return res.status(401).json({
        error: 'Invalid JWT',
        details: err.message,
      });
    }
    req.user = decoded;
    next();
  });
}

// New Middleware to check for Admin role
function adminJwtMiddleware(req, res, next) {
  const auth = req.headers.authorization || '';
  const token = auth.replace(/^Bearer /i, '');

  if (!token) {
    return res.status(401).json({
      error: 'No bearer token provided – admin access denied',
    });
  }

  jwt.verify(token, JWT_SECRET, (err, decoded) => {
    if (err) {
      return res.status(401).json({
        error: 'Invalid JWT for admin access',
        details: err.message,
      });
    }
    // Check for admin role
    if (decoded.role !== 'admin') {
      return res.status(403).json({
        error: 'Forbidden – admin role required',
      });
    }
    req.user = decoded; // Add user to request object
    next();
  });
}

// ────────────────────────────────────────────────────────────
// Public Routes
// ────────────────────────────────────────────────────────────

// "Login" – no password checks; returns JWT for any username
app.post('/login', (req, res) => {
  const { username = 'anonymous' } = req.body || {};
  const token = signToken({ sub: username, role: 'user' });
  res.json({ token });
});

// New Admin Login Route
app.post(['/admin/login', '/api/admin/login'], (req, res) => {
  const { username, password } = req.body || {};

  if (username === process.env.ADMIN_USERNAME && password === process.env.ADMIN_PASSWORD) {
    const token = signToken({ sub: username, role: 'admin' }, '1h'); // Shorter expiry for admin
    res.json({ token, message: 'Admin login successful' });
  } else {
    res.status(401).json({ error: 'Invalid admin credentials' });
  }
});

// Health
app.get('/health', (_req, res) =>
  res.json({ status: 'ok', timestamp: Date.now() })
);

// Health check route
app.get('/healthz', (_req, res) =>
  res.json({ status: 'ok', timestamp: Date.now(), service: 'api-gateway' })
);

// ────────────────────────────────────────────────────────────
// Proxy Configuration Helper
// ────────────────────────────────────────────────────────────
function makeProxy(target, addPath = '') {
  // Disable keep-alive on upstream to avoid connection reset with chunked encoding
  const agent = new http.Agent({ keepAlive: false });
  return createProxyMiddleware({
    agent,
    target,
    changeOrigin: true,
    // Extend timeouts so long LLM turns don't 504 at the gateway
    timeout: PROXY_TIMEOUT_MS,
    proxyTimeout: PROXY_TIMEOUT_MS,
    pathRewrite: (path) => {
      const newPath = path.replace(new RegExp(`^/api`), '');
      console.log(`[PROXY] Rewriting path: ${path} -> ${newPath}`);
      return newPath;
    },
    logLevel: 'debug',
    onProxyRes: (_proxyRes, _req, res) => {
      // Flush headers early to enable streaming passthrough
      if (typeof res.flushHeaders === 'function') {
        res.flushHeaders();
      }
    },
    onProxyReq: (proxyReq, req) => {
      // Forward original JWT downstream so services can introspect user
      if (req.headers.authorization) {
        proxyReq.setHeader('authorization', req.headers.authorization);
      }
      // Re-stream JSON body so finance-service receives it (needed for POST/PUT)
      if ((req.method === 'POST' || req.method === 'PUT') && req.body && Object.keys(req.body).length) {
        const bodyData = JSON.stringify(req.body);
        proxyReq.setHeader('Content-Type', 'application/json');
        proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
        proxyReq.write(bodyData);
      }
    },
  });
}

// ────────────────────────────────────────────────────────────
// Protected Routes – require JWT
// ────────────────────────────────────────────────────────────
app.use('/api/users', adminJwtMiddleware, makeProxy(USER_SERVICE_URL, '/users'));
app.use(
  '/api/transactions',
  jwtMiddleware,
  makeProxy(FINANCE_SERVICE_URL, '/transactions')
);
app.use('/api/accounts', jwtMiddleware, makeProxy(FINANCE_SERVICE_URL, '/accounts'));
app.use('/api/transfers', jwtMiddleware, makeProxy(FINANCE_SERVICE_URL, '/transfers'));
app.use('/api/savings', jwtMiddleware, makeProxy(FINANCE_SERVICE_URL, '/savings'));
app.use('/api/loans', jwtMiddleware, makeProxy(FINANCE_SERVICE_URL, '/loans'));
app.use('/api/credit-score', jwtMiddleware, makeProxy(FINANCE_SERVICE_URL, '/credit-score'));
app.use('/api/trading', jwtMiddleware, makeProxy(FINANCE_SERVICE_URL, '/trading'));


// LLM Chat Endpoint – now forwards to versioned /api/v1 routes on llm-service
app.use(
  '/api/llm',
  (req, res, next) => {
    // Allow public access to metadata endpoints
    const urlPath = req.originalUrl || req.url || '';
    if (urlPath.startsWith('/api/llm/available-models') || urlPath.startsWith('/api/llm/current-model')) {
      return next();
    }
    return jwtMiddleware(req, res, next);
  },
  createProxyMiddleware({
    // Keep upstream connection alive for long/streamed responses
    agent: new http.Agent({ keepAlive: true }),
    target: LLM_SERVICE_URL,
    changeOrigin: true,
    timeout: PROXY_TIMEOUT_MS,
    proxyTimeout: PROXY_TIMEOUT_MS,
    pathRewrite: { '^/api/llm': '/api/v1' }, // /api/llm/auth/chat → /api/v1/auth/chat
    logLevel: 'debug', // Increase logging for debugging
    onProxyRes: (_proxyRes, _req, res) => {
      // Disable buffering and flush headers for streaming passthrough
      res.setHeader('Connection', 'keep-alive');
      if (typeof res.flushHeaders === 'function') {
        res.flushHeaders();
      }
    },
    onProxyReq: (proxyReq, req) => {
      if (req.headers.authorization) {
        proxyReq.setHeader('authorization', req.headers.authorization);
      }

      // Handle JSON body forwarding for POST requests
      if (req.method === 'POST' && req.body) {
        const bodyData = JSON.stringify(req.body);
        proxyReq.setHeader('Content-Type', 'application/json');
        proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
        proxyReq.write(bodyData);
      }
    },
    onError: (err, req, res) => {
      console.error('Proxy error:', err.message);
      res.status(500).json({ error: 'Proxy error', details: err.message });
    }
  })
);

// Tools service - INTENTIONALLY DANGEROUS AND UNAUTHENTICATED
app.use('/api/tools', makeProxy(TOOLS_SERVICE_URL, '/tools'));

// RAG routes are no longer exposed via gateway – llm-service handles RAG internally

// Mock external bank partner
app.use('/api/partner', makeProxy(MOCK_PARTNER_API_URL, '/partner'));

// ────────────────────────────────────────────────────────────
// LLM Public Info Routes (no auth) – allow Admin UI to load
// model metadata without a token
// ────────────────────────────────────────────────────────────
app.use(
  ['/api/llm/available-models', '/api/llm/current-model'],
  createProxyMiddleware({
    agent: new http.Agent({ keepAlive: false }),
    target: LLM_SERVICE_URL,
    changeOrigin: true,
    pathRewrite: { '^/api/llm': '/api/v1' },
    logLevel: 'debug'
  })
);

// ────────────────────────────────────────────────────────────
// Admin Routes - Require Admin JWT
// ────────────────────────────────────────────────────────────
// Admin routes with proper proxy setup
app.use(['/admin/stats', '/api/admin/stats'], createProxyMiddleware({
  agent: new http.Agent({ keepAlive: false }),
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/admin/stats': '/admin/stats', '^/api/admin/stats': '/admin/stats' }
}));

app.use(['/admin/generate-users', '/api/admin/generate-users'], createProxyMiddleware({
  agent: new http.Agent({ keepAlive: false }),
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/admin/generate-users': '/admin/generate-users', '^/api/admin/generate-users': '/admin/generate-users' },
  onProxyReq: (proxyReq, req) => {
    // Ensure request body is forwarded for POST requests
    if (req.body && req.method === 'POST') {
      const bodyData = JSON.stringify(req.body);
      proxyReq.setHeader('Content-Type', 'application/json');
      proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
      proxyReq.write(bodyData);
    }
  }
}));

app.use(['/admin/reset', '/api/admin/reset'], createProxyMiddleware({
  agent: new http.Agent({ keepAlive: false }),
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/admin/reset': '/admin/reset', '^/api/admin/reset': '/admin/reset' },
  onProxyReq: (proxyReq, req) => {
    if (req.body && req.method === 'POST') {
      const bodyData = JSON.stringify(req.body);
      proxyReq.setHeader('Content-Type', 'application/json');
      proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
      proxyReq.write(bodyData);
    }
  }
}));

app.use(['/admin/generate-transactions', '/api/admin/generate-transactions'], createProxyMiddleware({
  agent: new http.Agent({ keepAlive: false }),
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/admin/generate-transactions': '/admin/generate-transactions', '^/api/admin/generate-transactions': '/admin/generate-transactions' },
  onProxyReq: (proxyReq, req) => {
    // Ensure request body is forwarded for POST requests
    if (req.body && req.method === 'POST') {
      const bodyData = JSON.stringify(req.body);
      proxyReq.setHeader('Content-Type', 'application/json');
      proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
      proxyReq.write(bodyData);
    }
  }
}));

// New admin endpoints
/*
app.use('/admin/clear-chat-sessions', createProxyMiddleware({
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/admin/clear-chat-sessions': '/admin/clear-chat-sessions' },
  onProxyReq: (proxyReq, req) => {
    if (req.body && req.method === 'POST') {
      const bodyData = JSON.stringify(req.body);
      proxyReq.setHeader('Content-Type', 'application/json');
      proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
      proxyReq.write(bodyData);
    }
  }
}));
*/

app.use(['/admin/change-user-password', '/api/admin/change-user-password'], createProxyMiddleware({
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/admin/change-user-password': '/admin/change-user-password', '^/api/admin/change-user-password': '/admin/change-user-password' },
  onProxyReq: (proxyReq, req) => {
    if (req.body && req.method === 'POST') {
      const bodyData = JSON.stringify(req.body);
      proxyReq.setHeader('Content-Type', 'application/json');
      proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
      proxyReq.write(bodyData);
    }
  }
}));

// Users endpoint
app.get('/users', adminJwtMiddleware, createProxyMiddleware({
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/users': '/users' }
}));

app.delete('/users/:id', adminJwtMiddleware, createProxyMiddleware({
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/users': '/users' }
}));

// ────────────────────────────────────────────────────────────
// Direct Service Access routes removed. Conversation history now handled by llm-service.
// ────────────────────────────────────────────────────────────

// Forward to LLM service directly (legacy path removed; use /api/llm instead)

// Forward to tools service directly (DANGEROUS - no auth)
app.use('/tools', makeProxy(TOOLS_SERVICE_URL));
app.use('/shell', makeProxy(TOOLS_SERVICE_URL));
app.use('/payments', makeProxy(TOOLS_SERVICE_URL));

// Banking routes (public access)
app.post(['/banking/login', '/api/banking/login'], createProxyMiddleware({
  agent: new http.Agent({ keepAlive: false }),
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/banking/login': '/banking/login', '^/api/banking/login': '/banking/login' },
  onProxyReq: (proxyReq, req) => {
    // Ensure request body is forwarded for POST requests
    if (req.body && req.method === 'POST') {
      const bodyData = JSON.stringify(req.body);
      proxyReq.setHeader('Content-Type', 'application/json');
      proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
      proxyReq.write(bodyData);
    }
  }
}));

app.get(['/banking/transactions/:userId', '/api/banking/transactions/:userId'], createProxyMiddleware({
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/banking/transactions': '/banking/transactions', '^/api/banking/transactions': '/banking/transactions' }
}));

app.get(['/banking/profile/:userId', '/api/banking/profile/:userId'], createProxyMiddleware({
  target: USER_SERVICE_URL,
  changeOrigin: true,
  pathRewrite: { '^/banking/profile': '/banking/profile', '^/api/banking/profile': '/banking/profile' }
}));

// Admin endpoint to clear all chat sessions
app.post(['/admin/clear-chat-sessions', '/api/admin/clear-chat-sessions'], async (req, res) => {
  try {
    let deletedCount = 0;

    // Clear active sessions
    const activeCount = activeSessions.size;
    activeSessions.clear();

    // Clear MongoDB sessions
    if (db) {
      const result = await db.collection('chat_sessions').deleteMany({});
      deletedCount = result.deletedCount;
    }

    res.json({
      ok: true,
      message: `Cleared ${deletedCount} stored sessions and ${activeCount} active sessions`,
      deletedCount: deletedCount,
      activeCleared: activeCount
    });
  } catch (error) {
    console.error('Clear chat sessions error:', error);
    res.status(500).json({ ok: false, error: error.message });
  }
});

// ────────────────────────────────────────────────────────────
// Catch-All & Error Handler
// ────────────────────────────────────────────────────────────
app.all('*', (_req, res) =>
  res.status(404).json({ error: 'Route not found on API Gateway' })
);

app.use((err, _req, res, _next) => {
  // Verbose error leak (intentional)
  res.status(err.status || 500).json({
    error: 'Unexpected error',
    message: err.message,
    stack: err.stack,
  });
});

// ────────────────────────────────────────────────────────────
// Server
// ────────────────────────────────────────────────────────────
const server = app.listen(PORT, () =>
  /* eslint-disable no-console */
  console.log(
    `🚩 Fake-Fintech API Gateway running on port ${PORT}
      – No rate limits, generous body size, permissive CORS`
  )
  /* eslint-enable no-console */
);

// Ensure gateway timeouts exceed frontend proxy settings
server.setTimeout(SERVER_TIMEOUT_MS);
server.headersTimeout = HEADERS_TIMEOUT_MS;

// Simple UUID v4 generator using crypto
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

module.exports = app;