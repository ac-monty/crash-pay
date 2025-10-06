module.exports = (sequelize, DataTypes) => {
    const Role = sequelize.define('Role', {
        name: {
            type: DataTypes.STRING,
            unique: true,
        },
        description: DataTypes.STRING,
    }, {
        tableName: 'roles',
    });

    Role.associate = models => {
        Role.belongsToMany(models.User, {
            through: 'users_roles',
            foreignKey: 'role_id',
        });

        Role.belongsToMany(models.Scope, {
            through: 'roles_scopes',
            foreignKey: 'role_id',
        });
    };

    return Role;
}; 