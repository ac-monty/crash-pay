import { DataTypes } from 'sequelize';

export default (sequelize) => {
    const SavingsBucket = sequelize.define(
        'SavingsBucket',
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
            balance: {
                type: DataTypes.DECIMAL(14, 2),
                defaultValue: 0,
            },
            apy: {
                type: DataTypes.DECIMAL(5, 2),
                allowNull: false,
                defaultValue: 4.5, // generous fake APY
            },
        },
        {
            tableName: 'savings_buckets',
            timestamps: true,
        }
    );

    return SavingsBucket;
};