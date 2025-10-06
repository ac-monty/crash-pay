import { DataTypes } from 'sequelize';

/**
 * Transfer – ledger entries between two Account IDs.
 */
export default (sequelize) => {
    const Transfer = sequelize.define(
        'Transfer',
        {
            id: {
                type: DataTypes.UUID,
                defaultValue: DataTypes.UUIDV4,
                primaryKey: true,
            },
            fromAccountId: {
                type: DataTypes.UUID,
                allowNull: false,
            },
            toAccountId: {
                type: DataTypes.UUID,
                allowNull: false,
            },
            amount: {
                type: DataTypes.DECIMAL(14, 2),
                allowNull: false,
            },
            description: DataTypes.STRING,
            status: {
                type: DataTypes.ENUM('PENDING', 'SETTLED', 'FAILED'),
                defaultValue: 'PENDING',
            },
        },
        {
            tableName: 'transfers',
            timestamps: true,
        }
    );

    return Transfer;
};