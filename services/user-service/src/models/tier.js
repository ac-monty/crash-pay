module.exports = (sequelize, DataTypes) => {
    const Tier = sequelize.define('Tier', {
        name: {
            type: DataTypes.STRING,
            unique: true,
        },
        description: DataTypes.STRING,
    }, {
        tableName: 'tiers',
    });

    Tier.associate = models => {
        Tier.hasMany(models.User, { foreignKey: 'tier_id' });
    };

    return Tier;
}; 