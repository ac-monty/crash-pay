// shared/utils/logger.js
//
// Centralised Pino logger that writes **exclusively** to `stdout` so the
// side-car Filebeat agent (defined in `logging/elastic/`) can harvest logs
// uniformly across every container.
//
// – Pretty-prints when `NODE_ENV=development` for local DX
// – Pure JSON in all other environments for deterministic parsing
// – Adds a per-request `reqId` correlation token via AsyncLocalStorage
// – Safe to import in both browser (SSR) & Node contexts
//

const pino = require('pino');
const { AsyncLocalStorage } = require('async_hooks');
const { v4: uuidv4 } = require('uuid');

const als = new AsyncLocalStorage();

/**
 * Internal: builds the base Pino options object.
 * Pretty-printing is enabled only for local development.
 */
function buildPinoOptions() {
  const isDev = process.env.NODE_ENV === 'development';

  const baseOptions = {
    level: process.env.LOG_LEVEL || 'info',
    base: undefined, // do not include pid/hostname to minimise noise
    redact: ['password', '*.secret', 'authorization', 'apiKey'], // generic secret scrubbing
    timestamp: pino.stdTimeFunctions.isoTime,
  };

  if (isDev) {
    baseOptions.transport = {
      target: 'pino-pretty',
      options: {
        colorize: true,
        translateTime: 'SYS:standard',
        ignore: 'pid,hostname',
      },
    };
  }

  return baseOptions;
}

const rootLogger = pino(buildPinoOptions());

/**
 * Gets the current request-scoped logger, or returns the root logger if no
 * request context is active.
 */
function getLogger() {
  const store = als.getStore();
  return (store && store.logger) || rootLogger;
}

/**
 * Express / Fastify style middleware to create a child logger per request.
 * (Express example usage shown, but the concept is framework-agnostic.)
 *
 * @example
 *   const app = express();
 *   app.use(requestLoggerMiddleware);
 */
function requestLoggerMiddleware(req, res, next) {
  // Ensure every request has a correlation token
  const reqId = req.headers['x-request-id'] || uuidv4();

  // Create a child logger bound to this request
  const childLogger = rootLogger.child({ reqId, path: req.path, method: req.method });

  // Expose the logger on the request object for route handlers
  req.log = childLogger;

  // Store inside AsyncLocalStorage so deep-nested code can call getLogger()
  als.run({ logger: childLogger }, () => {
    childLogger.info({ msg: 'Incoming request' });

    res.on('finish', () => {
      childLogger.info({ msg: 'Request completed', statusCode: res.statusCode });
    });

    next();
  });
}

module.exports = {
  logger: rootLogger,
  getLogger,
  requestLoggerMiddleware,
};