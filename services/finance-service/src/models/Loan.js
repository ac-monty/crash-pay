import { DataTypes } from 'sequelize';

export default (sequelize) => {
    const Loan = sequelize.define(
        'Loan',
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
            principal: {
                type: DataTypes.DECIMAL(14, 2),
                allowNull: false,
            },
            outstanding: {
                type: DataTypes.DECIMAL(14, 2),
                allowNull: false,
            },
            interestRate: {
                type: DataTypes.DECIMAL(5, 2),
                allowNull: false,
            },
            status: {
                type: DataTypes.ENUM('ACTIVE', 'PAID', 'DEFAULTED'),
                defaultValue: 'ACTIVE',
            },
        },
        {
            tableName: 'loans',
            timestamps: true,
        }
    );

    return Loan;
};