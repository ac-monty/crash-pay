'use strict';

/**
 * Intentionally over-permissive Sequelize bootstrap for the **User Service**.
 * ---------------------------------------------------------------------------
 * WARNING:  This file hard-codes privileged "root" credentials to illustrate
 *           OWASP-LLM Top-10 weakness LLM-09 (over-privileged DB access) and
 *           LLM-10 (plain-text secrets).  Do NOT copy this pattern into any
 *           real production system.
 *
 * The rest of the application purposefully lacks:
 *   • connection-pool limits
 *   • TLS enforcement
 *   • least-privilege database roles
 *   • secrets-manager integration
 *
 * Those omissions are deliberate so security researchers can probe them.
 */

const fs = require('fs');
const path = require('path');
const Sequelize = require('sequelize');

const basename = path.basename(__filename);
const env = process.env.NODE_ENV || 'development';
const db = {};

/* -------------------------------------------------------------------------- */
/*                                DB CONFIG                                   */
/* -------------------------------------------------------------------------- */

// Root creds baked into image; fall back to env vars if provided.
const DB_HOST = process.env.POSTGRES_HOST || 'postgres';
const DB_PORT = process.env.POSTGRES_PORT || 5432;
const DB_NAME = process.env.PG_DB || process.env.POSTGRES_DB || 'fintech';
const DB_USER = process.env.PG_USER || process.env.POSTGRES_USER || 'fintech';
const DB_PASSWORD = process.env.PG_PASSWORD || process.env.POSTGRES_PASSWORD || 'fintech';

const sequelize = new Sequelize(DB_NAME, DB_USER, DB_PASSWORD, {
  host: DB_HOST,
  port: DB_PORT,
  dialect: 'postgres',
  logging: console.log,  // noisy on purpose for researchers to observe queries
  pool: {
    // Intentionally lax values to enable connection-starvation DoS testing.
    max: 50,
    min: 0,
    acquire: 30000,
    idle: 10000
  },
  dialectOptions: {
    // RejectUnauthorized left false to allow MITM in local labs.
    ssl: env === 'production' ? { require: false, rejectUnauthorized: false } : false
  }
});

/* -------------------------------------------------------------------------- */
/*                           DYNAMIC MODEL IMPORTS                            */
/* -------------------------------------------------------------------------- */

fs.readdirSync(__dirname)
  .filter(file =>
    file.indexOf('.') !== 0 &&                          // ignore hidden files
    file !== basename &&                                // ignore this file
    (file.slice(-3) === '.js' || file.slice(-3) === '.ts')
  )
  .forEach(file => {
    // eslint-disable-next-line global-require, import/no-dynamic-require
    const model = require(path.join(__dirname, file))(sequelize, Sequelize.DataTypes);
    db[model.name] = model;
  });

// Resolve any associate() calls defined on the models.
Object.keys(db).forEach(modelName => {
  if (typeof db[modelName].associate === 'function') {
    db[modelName].associate(db);
  }
});

/* -------------------------------------------------------------------------- */
/*                              EXPORT HANDLE                                 */
/* -------------------------------------------------------------------------- */

db.sequelize = sequelize;
db.Sequelize = Sequelize;

module.exports = db;