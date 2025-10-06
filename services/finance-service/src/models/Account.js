import { DataTypes } from 'sequelize';

/**
 * Account Model – represents a user-facing wallet/bank account.
 * Note: No formal foreign-key to Users table to keep cross-service
 * coupling loose (intentional for red-team demos).
 */
export default (sequelize) => {
    const Account = sequelize.define(
        'Account',
        {
            id: {
                type: DataTypes.UUID,
                defaultValue: DataTypes.UUIDV4,
                primaryKey: true,
            },
            userId: {
                type: DataTypes.UUID,
                allowNull: false,
            },
            type: {
                type: DataTypes.ENUM('CHECKING', 'SAVINGS'),
                defaultValue: 'CHECKING',
            },
            balance: {
                type: DataTypes.DECIMAL(14, 2),
                defaultValue: 0,
                allowNull: false,
            },
            status: {
                type: DataTypes.ENUM('OPEN', 'FROZEN', 'CLOSED'),
                defaultValue: 'OPEN',
            },
        },
        {
            tableName: 'accounts',
            timestamps: true,
        }
    );

    Account.associate = (models) => {
        Account.hasMany(models.Transfer, { as: 'Outgoing', foreignKey: 'fromAccountId' });
        Account.hasMany(models.Transfer, { as: 'Incoming', foreignKey: 'toAccountId' });
    };

    return Account;
};