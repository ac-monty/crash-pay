import { DataTypes } from 'sequelize';

export default (sequelize) => {
    const StockOrder = sequelize.define(
        'StockOrder',
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
            side: {
                type: DataTypes.ENUM('BUY', 'SELL'),
                allowNull: false,
            },
            quantity: {
                type: DataTypes.DECIMAL(14, 4),
                allowNull: false,
            },
            price: {
                type: DataTypes.DECIMAL(14, 2),
                allowNull: false,
            },
            status: {
                type: DataTypes.ENUM('QUEUED', 'FILLED', 'CANCELLED'),
                defaultValue: 'QUEUED',
            },
        },
        {
            tableName: 'stock_orders',
            timestamps: true,
        }
    );

    return StockOrder;
};