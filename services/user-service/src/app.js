// Initialize APM first (must be before other requires)
let apm = null;
try {
  if (process.env.ELASTIC_APM_SERVER_URL) {
    apm = require('elastic-apm-node').start({
      serviceName: process.env.ELASTIC_APM_SERVICE_NAME || 'user-service',
      serverUrl: process.env.ELASTIC_APM_SERVER_URL,
      environment: process.env.NODE_ENV || 'development'
    });
    console.log('✅ APM initialized for User Service');
  } else {
    console.log('ℹ️ APM not configured (ELASTIC_APM_SERVER_URL not set)');
  }
} catch (error) {
  console.warn('⚠️ APM initialization failed:', error.message);
}

const express = require('express');
const { Sequelize, DataTypes } = require('sequelize');
const bodyParser = require('body-parser');
const morgan = require('morgan');

// APM instrumentation with graceful error handling
const { middleware: apmMiddleware, captureError, captureMessage, setApmInstance } = require('../../shared/utils/apm');

// Set the APM instance in the shared utility
if (apm) {
  setApmInstance(apm);
}

/**
 *        OWASP-LLM Top-10 weaknesses can be exercised by security researchers.
 *        Do NOT copy this pattern into any production system.
 */

/* -------------------------------------------------------------------------- */
/*                               ENV / CONFIG                                 */
/* -------------------------------------------------------------------------- */

const {
  PG_HOST = 'postgres',        // docker-compose service name or hostname
  PG_PORT = 5432,
  PG_DB = 'fake_fintech',
  PG_USER = 'postgres',
  PG_PASSWORD = 'postgres',
  NODE_ENV = 'development',
  SERVICE_PORT = 8081          // user-service default port
} = process.env;

/* -------------------------------------------------------------------------- */
/*                               DB CONNECTION                                */
/* -------------------------------------------------------------------------- */

// Import models and routes
const { sequelize } = require('./models');
const usersRouter = require('./routes/users');
const healthRouter = require('./routes/health');

/* -------------------------------------------------------------------------- */
/*                               APP SETUP                                    */
/* -------------------------------------------------------------------------- */

const app = express();

// APM middleware for automatic transaction tracking
app.use(apmMiddleware);

app.use(bodyParser.json({ limit: '10mb' })); // no schema / size protection
app.use(morgan('combined'));                 // basic access logs

// Mount routes
app.use('/', healthRouter);
app.use('/', usersRouter);

/* -------------------------------------------------------------------------- */
/*                               ROUTES                                       */
/* -------------------------------------------------------------------------- */

// Routes are now handled by the users router

/* -------------------------------------------------------------------------- */
/*                               SERVER BOOT                                  */
/* -------------------------------------------------------------------------- */

(async () => {
  try {
    await sequelize.authenticate();
    console.log('✅ PostgreSQL connection established');

    // Auto-migrate with `sync({ alter: true })` for convenience (unsafe in prod).
    await sequelize.sync({ alter: true });
    console.log('✅ Models synced');

    // Seed tiers and roles if empty
    const { Tier, Role, Scope } = require('./models');

    // Seed tiers
    const tierNames = ['basic', 'premium', 'director'];
    for (const t of tierNames) {
      await Tier.findOrCreate({ where: { name: t } });
    }

    // Seed roles
    const roleNames = ['customer', 'advisor', 'admin'];
    for (const r of roleNames) {
      await Role.findOrCreate({ where: { name: r } });
    }

    // Seed scopes
    const scopeNames = [
      'banking:read',
      'banking:write',
      'transfers:create',
      'investments:read',
      'admin:read'
    ];
    for (const s of scopeNames) {
      await Scope.findOrCreate({ where: { name: s } });
    }

    // Seed role-scope mappings
    const roleScopeMappings = {
      customer: ['banking:read', 'banking:write', 'transfers:create'],
      advisor: ['banking:read', 'investments:read'],
      admin: ['banking:read', 'banking:write', 'transfers:create', 'admin:read'],
    };

    for (const [roleName, scopeNames] of Object.entries(roleScopeMappings)) {
      const role = await Role.findOne({ where: { name: roleName } });
      if (role) {
        const scopes = await Scope.findAll({ where: { name: scopeNames } });
        await role.setScopes(scopes);
      }
    }

    console.log('✅ Seeded tiers, roles, scopes, and role-scope mappings');

    app.listen(SERVICE_PORT, () =>
      console.log(`🚀 User Service running on http://0.0.0.0:${SERVICE_PORT}`)
    );
  } catch (err) {
    console.error('❌ Unable to start service:', err);

    // Capture startup errors in APM
    captureError(err, {
      labels: {
        error_type: 'service_startup_failure',
        service: 'user-service',
        component: 'database_connection'
      }
    });

    process.exit(1);
  }
})();

process.on('SIGTERM', () => {
  console.log('🔻 Gracefully shutting down');
  sequelize.close().then(() => process.exit(0));
});