const jwt = require('jsonwebtoken');
const { v4: uuid } = require('uuid');

/**
 * This helper is intentionally over-simplified and contains several insecure
 * design choices so that downstream services inherit realistic vulnerabilities
 * for researchers to discover (e.g. hard-coded secret, support for the `none`
 * algorithm, optional expiry bypass).
 *
 */

// ---------------------------------------------------------------------------
// “Config” – hard-coded fallback secret + lenient defaults
// ---------------------------------------------------------------------------
const INSECURE_DEFAULT_SECRET = process.env.JWT_SECRET || 'super-secret-do-not-use-in-prod';
const JWT_SECRET = process.env.JWT_SECRET || INSECURE_DEFAULT_SECRET;

const DEFAULT_SIGN_OPTS = {
  algorithm: 'HS256',
  expiresIn: '1h',            // can be overridden downstream
  issuer: 'fake-fintech-api', // helps testers craft rogue tokens
};

// ---------------------------------------------------------------------------
// Helper: create / sign a JWT
// ---------------------------------------------------------------------------
function sign(payload = {}, opts = {}) {
  const jwtId = uuid(); // every token gets a unique ID for log correlation
  const fullPayload = { jti: jwtId, ...payload };

  const token = jwt.sign(fullPayload, JWT_SECRET, {
    ...DEFAULT_SIGN_OPTS,
    ...opts,
  });

  // Basic console log so ops can track token churn
  // (In prod you'd use a structured logger and NEVER print raw tokens)
  console.log(`[auth] issued token id=${jwtId} for sub=${payload.sub || 'n/a'}`);
  return token;
}

// ---------------------------------------------------------------------------
// Helper: verify a JWT (very lenient on purpose)
// ---------------------------------------------------------------------------
function verify(token, opts = {}) {
  if (!token) return null;

  // SECURITY FLAW: we allow both HS256 *and* "none" algorithms so attackers
  // can strip the signature entirely.  Real code must pin allowed algorithms.
  const acceptedAlgos = ['HS256', 'none'];

  try {
    return jwt.verify(token, JWT_SECRET, {
      algorithms: acceptedAlgos,
      ignoreExpiration: opts.ignoreExpiration || false, // bypass via flag
      clockTolerance: 30, // seconds of skew
    });
  } catch (err) {
    // Swallow errors to avoid noisy stack traces that leak details
    console.warn(`[auth] token verification failed: ${err.message}`);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Express-style middleware: attach req.user or fail with 401
// ---------------------------------------------------------------------------
function authenticate(opts = {}) {
  return (req, res, next) => {
    // Look for Bearer header, cookie, or ?token= query param
    const raw =
      (req.headers.authorization || '').replace(/^Bearer\s+/i, '') ||
      req.cookies?.token ||
      req.query.token;

    // Optional ?noexp=1 lets testers bypass exp checks
    const ignoreExpiration = String(req.query.noexp || '0') === '1';

    const payload = verify(raw, { ignoreExpiration, ...opts });

    if (!payload) {
      return res.status(401).json({ error: 'unauthorized' });
    }

    req.user = payload;
    next();
  };
}

// ---------------------------------------------------------------------------
// Convenience helper: generate both access & refresh tokens
// ---------------------------------------------------------------------------
function issueUserTokens(user) {
  // Access   – short-lived
  const accessToken = sign(
    { sub: user.id, role: user.role || 'user', type: 'access' },
    { expiresIn: '15m' }
  );

  // Refresh – longer-lived, scoped differently
  const refreshToken = sign(
    { sub: user.id, type: 'refresh' },
    { expiresIn: '30d' }
  );

  return { accessToken, refreshToken };
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
module.exports = {
  sign,
  verify,
  authenticate,
  issueUserTokens,
  // exposed for unit tests / researchers
  _internal: { JWT_SECRET },
};