module.exports = (sequelize, DataTypes) => {
    const Scope = sequelize.define(
        'Scope',
        {
            id: {
                type: DataTypes.INTEGER,
                autoIncrement: true,
                primaryKey: true,
            },
            name: {
                type: DataTypes.STRING,
                unique: true,
                allowNull: false,
            },
            description: DataTypes.STRING,
        },
        {
            tableName: 'scopes',
            timestamps: true,
            underscored: true,
        }
    );

    Scope.associate = models => {
        Scope.belongsToMany(models.Role, {
            through: 'roles_scopes',
            foreignKey: 'scope_id',
        });
    };

    return Scope;
};
