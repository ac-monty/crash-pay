import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import Sequelize from 'sequelize';

// ---------------------------------------------------------------------------
// Dynamic Sequelize bootstrapping (pattern borrowed from user-service)
// ---------------------------------------------------------------------------
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const env = process.env.NODE_ENV || 'development';

// Intentionally over-privileged creds — mirrors existing pattern
const DB_HOST = process.env.POSTGRES_HOST || 'postgres';
const DB_PORT = process.env.POSTGRES_PORT || 5432;
const DB_NAME = process.env.PG_DB || process.env.POSTGRES_DB || 'fintech';
const DB_USER = process.env.PG_USER || process.env.POSTGRES_USER || 'fintech';
const DB_PASSWORD = process.env.PG_PASSWORD || process.env.POSTGRES_PASSWORD || 'fintech';

const sequelize = new Sequelize(DB_NAME, DB_USER, DB_PASSWORD, {
    host: DB_HOST,
    port: DB_PORT,
    dialect: 'postgres',
    logging: console.log,
    pool: { max: 50, min: 0, acquire: 30000, idle: 10000 },
    dialectOptions: {
        ssl: env === 'production' ? { require: false, rejectUnauthorized: false } : false,
    },
});

const db = {};

const files = fs.readdirSync(__dirname).filter((file) => file !== 'index.js' && file.endsWith('.js'));
for (const file of files) {
    // Dynamic import to keep ES module syntax
    // eslint-disable-next-line no-await-in-loop
    const module = await import(path.join(__dirname, file));
    const modelDef = module.default;
    const model = modelDef(sequelize);
    db[model.name] = model;
}

Object.keys(db).forEach((modelName) => {
    if (typeof db[modelName].associate === 'function') {
        db[modelName].associate(db);
    }
});

db.sequelize = sequelize;
db.Sequelize = Sequelize;

export default db;
