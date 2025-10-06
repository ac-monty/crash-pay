// shared/utils/apm.js
//
// Centralised APM (Application Performance Monitoring) utility that provides:
// – Graceful degradation when observability stack is down
// – Consistent error tracking across all services
// – Reusable helper functions for performance monitoring
// – Safe initialization that never crashes the application
// – Automatic retry mechanisms for APM reconnection
//

class APMService {
    constructor() {
        this.apm = null;
        this.isInitialized = false;
        this.initializationAttempts = 0;
        this.maxRetries = 3;
        this.serviceName = process.env.ELASTIC_APM_SERVICE_NAME || 'unknown-service';

        // Don't auto-initialize - wait for services to call setApmInstance
    }

    /**
     * Initialize APM with graceful error handling
     */
    initialize() {
        // Don't auto-initialize - wait for setApmInstance to be called
        if (!process.env.ELASTIC_APM_SERVER_URL) {
            this.logInfo('APM not configured (ELASTIC_APM_SERVER_URL not set), continuing without observability');
            return;
        }

        this.logInfo('APM utility ready - waiting for APM instance from service');
    }

    /**
     * Set APM instance from service (called after service initializes APM)
     */
    setApmInstance(apmInstance) {
        this.apm = apmInstance;
        this.isInitialized = !!apmInstance;
        this.logInfo(`✅ APM instance set for service: ${this.serviceName}`);
    }

    /**
     * Safe logging that doesn't depend on external logger
     */
    logInfo(message) {
        console.log(`[APM:${this.serviceName}] ${message}`);
    }

    logWarning(message) {
        console.warn(`[APM:${this.serviceName}] ${message}`);
    }

    logError(message, error = null) {
        console.error(`[APM:${this.serviceName}] ${message}`, error);
    }

    /**
     * Check if APM is available and working
     */
    isAvailable() {
        return this.isInitialized && this.apm !== null;
    }

    /**
     * Safely capture an exception/error
     * @param {Error} error - The error to capture
     * @param {Object} context - Additional context (labels, user info, etc.)
     */
    captureError(error, context = {}) {
        if (!this.isAvailable()) {
            this.logError('Error occurred (APM unavailable)', error);
            return;
        }

        try {
            const apmContext = {
                labels: {
                    service: this.serviceName,
                    component: 'error-tracking',
                    ...context.labels
                },
                user: context.user || {},
                custom: context.custom || {}
            };

            this.apm.captureError(error, apmContext);
            this.logInfo(`Error captured in APM: ${error.message}`);

        } catch (apmError) {
            this.logWarning(`APM error capture failed: ${apmError.message}`);
            // Fallback to regular logging
            this.logError('Original error (APM capture failed)', error);
        }
    }

    /**
     * Safely capture a custom message/warning
     * @param {string} message - The message to capture
     * @param {string} level - The severity level (info, warning, error)
     * @param {Object} context - Additional context
     */
    captureMessage(message, level = 'info', context = {}) {
        if (!this.isAvailable()) {
            this.logInfo(`Message (APM unavailable): ${message}`);
            return;
        }

        try {
            // For messages, create an Error object for APM
            const error = new Error(message);
            error.name = level.charAt(0).toUpperCase() + level.slice(1);

            const apmContext = {
                labels: {
                    service: this.serviceName,
                    component: 'message-tracking',
                    level: level,
                    ...context.labels
                },
                user: context.user || {},
                custom: context.custom || {}
            };

            this.apm.captureError(error, apmContext);
            this.logInfo(`Message captured in APM: ${message}`);

        } catch (apmError) {
            this.logWarning(`APM message capture failed: ${apmError.message}`);
            // Fallback to regular logging
            this.logInfo(`Message (APM capture failed): ${message}`);
        }
    }

    /**
     * Start a custom transaction
     * @param {string} name - Transaction name
     * @param {string} type - Transaction type (request, background, etc.)
     * @returns {Object|null} Transaction object or null if APM unavailable
     */
    startTransaction(name, type = 'custom') {
        if (!this.isAvailable()) {
            this.logInfo(`Transaction started (APM unavailable): ${name}`);
            return null;
        }

        try {
            const transaction = this.apm.startTransaction(name, type);
            this.logInfo(`Transaction started: ${name}`);
            return transaction;
        } catch (apmError) {
            this.logWarning(`APM transaction start failed: ${apmError.message}`);
            return null;
        }
    }

    /**
     * End a transaction with result
     * @param {Object} transaction - Transaction object from startTransaction
     * @param {string} result - Transaction result (success, failure, etc.)
     */
    endTransaction(transaction, result = 'success') {
        if (!transaction || !this.isAvailable()) {
            return;
        }

        try {
            transaction.result = result;
            transaction.end();
            this.logInfo(`Transaction ended: ${result}`);
        } catch (apmError) {
            this.logWarning(`APM transaction end failed: ${apmError.message}`);
        }
    }

    /**
     * Create a custom span for performance monitoring
     * @param {string} name - Span name
     * @param {string} type - Span type (db, http, etc.)
     * @returns {Object|null} Span object or null if APM unavailable
     */
    startSpan(name, type = 'custom') {
        if (!this.isAvailable()) {
            return null;
        }

        try {
            const span = this.apm.startSpan(name, type);
            return span;
        } catch (apmError) {
            this.logWarning(`APM span start failed: ${apmError.message}`);
            return null;
        }
    }

    /**
     * End a span
     * @param {Object} span - Span object from startSpan
     */
    endSpan(span) {
        if (!span || !this.isAvailable()) {
            return;
        }

        try {
            span.end();
        } catch (apmError) {
            this.logWarning(`APM span end failed: ${apmError.message}`);
        }
    }

    /**
     * Set user context for current transaction
     * @param {Object} user - User information
     */
    setUser(user) {
        if (!this.isAvailable()) {
            return;
        }

        try {
            this.apm.setUserContext(user);
        } catch (apmError) {
            this.logWarning(`APM set user context failed: ${apmError.message}`);
        }
    }

    /**
     * Add custom labels to current transaction
     * @param {Object} labels - Key-value pairs of labels
     */
    addLabels(labels) {
        if (!this.isAvailable()) {
            return;
        }

        try {
            this.apm.addLabels(labels);
        } catch (apmError) {
            this.logWarning(`APM add labels failed: ${apmError.message}`);
        }
    }

    /**
     * Express/Fastify middleware for automatic transaction tracking
     * @param {Object} req - Request object
     * @param {Object} res - Response object  
     * @param {Function} next - Next middleware function
     */
    middleware(req, res, next) {
        const transactionName = `${req.method} ${req.route?.path || req.path}`;
        const transaction = this.startTransaction(transactionName, 'request');

        if (transaction) {
            // Add request context
            this.addLabels({
                http_method: req.method,
                http_url: req.url,
                user_ip: req.ip || req.connection?.remoteAddress
            });

            // Set user context if available
            if (req.user) {
                this.setUser({
                    id: req.user.id || req.user.sub,
                    username: req.user.username || req.user.name,
                    email: req.user.email
                });
            }
        }

        // Attach APM service to request for route handlers
        req.apm = this;

        res.on('finish', () => {
            if (transaction) {
                this.addLabels({
                    http_status_code: res.statusCode
                });

                const result = res.statusCode < 400 ? 'success' : 'error';
                this.endTransaction(transaction, result);
            }
        });

        next();
    }

    /**
     * Health check for APM service
     * @returns {Object} Health status
     */
    getHealthStatus() {
        return {
            service: 'apm',
            status: this.isAvailable() ? 'healthy' : 'degraded',
            initialized: this.isInitialized,
            attempts: this.initializationAttempts,
            message: this.isAvailable()
                ? 'APM operational'
                : 'APM unavailable, using fallback logging'
        };
    }
}

// Create singleton instance
const apmService = new APMService();

module.exports = {
    apm: apmService,

    // Convenience functions for direct use
    captureError: (error, context) => apmService.captureError(error, context),
    captureMessage: (message, level, context) => apmService.captureMessage(message, level, context),
    startTransaction: (name, type) => apmService.startTransaction(name, type),
    endTransaction: (transaction, result) => apmService.endTransaction(transaction, result),
    startSpan: (name, type) => apmService.startSpan(name, type),
    endSpan: (span) => apmService.endSpan(span),
    setUser: (user) => apmService.setUser(user),
    addLabels: (labels) => apmService.addLabels(labels),
    middleware: (req, res, next) => apmService.middleware(req, res, next),
    isAvailable: () => apmService.isAvailable(),
    getHealthStatus: () => apmService.getHealthStatus(),
    setApmInstance: (apm) => apmService.setApmInstance(apm)
}; 