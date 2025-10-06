import { DataTypes } from 'sequelize';

export default (sequelize) => {
    const StockHolding = sequelize.define(
        'StockHolding',
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
            symbol: {
                type: DataTypes.STRING,
                allowNull: false,
            },
            shares: {
                type: DataTypes.DECIMAL(14, 4),
                allowNull: false,
            },
            avgPrice: {
                type: DataTypes.DECIMAL(14, 2),
                allowNull: false,
            },
        },
        {
            tableName: 'stock_holdings',
            timestamps: true,
        }
    );

    return StockHolding;
};