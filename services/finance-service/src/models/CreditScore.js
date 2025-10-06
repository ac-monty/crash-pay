import { DataTypes } from 'sequelize';

export default (sequelize) => {
    const CreditScore = sequelize.define(
        'CreditScore',
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
            score: {
                type: DataTypes.INTEGER,
                allowNull: false,
                defaultValue: 650,
            },
            lastPulledAt: {
                type: DataTypes.DATE,
                allowNull: true,
            },
        },
        {
            tableName: 'credit_scores',
            timestamps: true,
        }
    );

    return CreditScore;
};