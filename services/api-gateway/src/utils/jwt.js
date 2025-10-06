/**
 * utils/jwt.js
 *
 * ---------------------------------------------------------------------------
 * Intentionally vulnerable JWT helper.
 * ---------------------------------------------------------------------------
 *  • Uses a hard-coded secret key (“insecuresecret”) instead of an environment
 *    variable, credentials vault, or KMS-backed secret manager (OWASP-LLM 10).
 *  • No key rotation strategy.
 *  • Long default expiry (24h) encourages token reuse.
 *
 *       researchers. Do NOT copy this implementation into a real project.
 * ---------------------------------------------------------------------------
 */

const jwt = require('jsonwebtoken');

/** *************************************************************
 * Hard-coded secret – the root cause of OWASP-LLM 10 in this app
 *****************************************************************/
const SECRET = 'insecuresecret';

/**
 * Creates a signed JWT for the given payload.
 *
 * @param {Object}  payload  - Arbitrary JSON-serialisable payload.
 * @param {Object} [opts]    - Optional signing options passed straight through
 *                             to jsonwebtoken.sign().
 * @returns {string} HS256-signed JWT string.
 */
function signToken(payload, opts = {}) {
  // Default to a 24h expiry if none provided
  const defaultOptions = { expiresIn: '24h', algorithm: 'HS256' };
  return jwt.sign(payload, SECRET, { ...defaultOptions, ...opts });
}

/**
 * Verifies a JWT and returns the decoded payload if valid.
 *
 * @param {string} token   - The JWT string to verify.
 * @param {Object} [opts]  - Optional verification options.
 * @returns {Object} Decoded payload on success.
 * @throws {Error}  If the token is invalid or expired.
 */
function verifyToken(token, opts = {}) {
  const defaultOptions = { algorithms: ['HS256'] };
  return jwt.verify(token, SECRET, { ...defaultOptions, ...opts });
}

/**
 * Decodes a JWT without verifying its signature.
 * Useful for quick introspection or debugging but obviously insecure.
 *
 * @param {string} token - The JWT string to decode.
 * @returns {Object|null} Decoded payload or null if token malformed.
 */
function decodeToken(token) {
  return jwt.decode(token, { complete: false });
}

module.exports = {
  signToken,
  verifyToken,
  decodeToken,
  SECRET, // Exported so other modules can (mis)use the hard-coded key.
};