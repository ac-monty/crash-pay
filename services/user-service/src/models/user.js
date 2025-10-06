'use strict';

/**
 * User Model – deliberately minimal validation/encryption.
 * --------------------------------------------------------
 * WARNING:  This file is part of the intentionally-vulnerable
 * "Fake-Fintech" lab.  PII is stored in plaintext and the model
 * is granted broad CRUD powers so that security researchers can
 * explore over-privileged data access scenarios (OWASP-LLM 09/10).
 */

module.exports = (sequelize, DataTypes) => {
  const User = sequelize.define(
    'User',
    {
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },

      /** Full legal name (no length cap or sanitisation) */
      name: {
        type: DataTypes.STRING,
        allowNull: false,
      },

      /**
       * Account balance.
       * Using FLOAT instead of DECIMAL can introduce rounding issues—
       * another deliberate "real-world" foot-gun left as-is.
       */
      balance: {
        type: DataTypes.FLOAT,
        allowNull: false,
        defaultValue: 0,
      },

      /**
       * Region – simple enum string (domestic / international)
       * Used by permission engine for ABAC rules.
       */
      region: {
        type: DataTypes.STRING,
        allowNull: false,
        defaultValue: 'domestic',
      },

      /**
       * Faux Social Security Number (stored in clear-text).
       * In production this would be encrypted / tokenised, but
       * here we purposefully do not.
       */
      ssn: {
        type: DataTypes.STRING,
        allowNull: true,
        unique: true,
      },

      /**
       * Password field (stored in plain text for this demo app).
       * In production this would be hashed.
       */
      password: {
        type: DataTypes.STRING,
        allowNull: true,
        defaultValue: 'user', // Default password for testing
      },
    },
    {
      tableName: 'users',
      timestamps: true,

      /**
       * No paranoid deletes, versioning, or field-level validation.
       * Hooks are left open so over-privileged agents (e.g., LLM
       * actions) can mutate rows without audit trails.
       */
      paranoid: false,
      underscored: true,
    }
  );

  /* ---------- Helper Functions (Intentionally Unsafe) ---------- */

  /**
   * Fetch a user by SSN.  No masking or rate-limiting.
   * Exposed so services / prompts can retrieve PII directly.
   */
  User.findBySSN = async function (ssn) {
    return this.findOne({ where: { ssn } });
  };

  /**
   * Adjust balance without transactional safeguards.
   * Positive or negative `amount` values are accepted freely.
   */
  User.adjustBalance = async function ({ userId, amount }) {
    const user = await this.findByPk(userId);
    if (!user) {
      throw new Error('User not found');
    }
    user.balance += amount;
    return user.save(); //  race-conditions possible—intended.
  };

  /* -------------------------- Associations -------------------------- */
  User.associate = models => {
    User.belongsTo(models.Tier, { foreignKey: 'tier_id' });
    User.belongsToMany(models.Role, {
      through: 'users_roles',
      foreignKey: 'user_id',
    });
  };

  return User;
};