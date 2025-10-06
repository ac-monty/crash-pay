import { DataTypes } from 'sequelize';

/** Legacy Transaction model kept for backward compatibility with
 * existing /transactions endpoints used by user-service and others. */
export default (sequelize) => {
    const Transaction = sequelize.define(
        'Transaction',
        {
            id: {
                type: DataTypes.UUID,
                defaultValue: DataTypes.UUIDV4,
                primaryKey: true,
            },
            accountId: {
                type: DataTypes.UUID,
                allowNull: true,
            },
            accountType: {
                type: DataTypes.ENUM('CHECKING', 'SAVINGS'),
                allowNull: true,
            },
            userId: {
                type: DataTypes.UUID,
                allowNull: false,
            },
            amount: {
                type: DataTypes.DECIMAL(12, 2),
                allowNull: false,
            },
            description: {
                type: DataTypes.TEXT,
                allowNull: true,
            },
            status: {
                type: DataTypes.ENUM('PENDING', 'SETTLED', 'FAILED'),
                defaultValue: 'PENDING',
            },
        },
        {
            tableName: 'transactions',
            timestamps: true,
        }
    );

    return Transaction;
};