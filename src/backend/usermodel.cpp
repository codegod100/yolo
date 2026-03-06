#include "usermodel.h"
#include <pwd.h>
#include <unistd.h>

UserModel::UserModel(QObject *parent)
    : QAbstractListModel(parent)
{
    loadUsers();
}

int UserModel::rowCount(const QModelIndex &parent) const
{
    if (parent.isValid()) return 0;
    return m_users.count();
}

QVariant UserModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_users.count())
        return QVariant();

    const User &user = m_users[index.row()];
    switch (role) {
    case UsernameRole:
        return user.username;
    case DisplayNameRole:
        return user.displayName;
    default:
        return QVariant();
    }
}

QHash<int, QByteArray> UserModel::roleNames() const
{
    return {
        {UsernameRole, "username"},
        {DisplayNameRole, "displayName"}
    };
}

void UserModel::loadUsers()
{
    beginResetModel();
    m_users.clear();

    struct passwd *pw;
    setpwent();

    while ((pw = getpwent()) != nullptr) {
        // Skip system users (UID < 1000)
        if (pw->pw_uid < 1000) continue;

        QString shell = QString::fromLocal8Bit(pw->pw_shell);
        // Skip users with nologin/false shells
        if (shell.endsWith("nologin") || shell.endsWith("false")) continue;

        User user;
        user.username = QString::fromLocal8Bit(pw->pw_name);
        user.displayName = user.username; // Could use GECOS field for full name
        m_users.append(user);
    }

    endpwent();

    // Sort by username
    std::sort(m_users.begin(), m_users.end(), [](const User &a, const User &b) {
        return a.username < b.username;
    });

    endResetModel();
    emit countChanged();
}
