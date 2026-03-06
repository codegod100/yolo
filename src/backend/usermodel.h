#pragma once

#include <QAbstractListModel>
#include <QList>

struct User {
    QString username;
    QString displayName;
};

class UserModel : public QAbstractListModel {
    Q_OBJECT
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged)

public:
    enum Roles {
        UsernameRole = Qt::UserRole + 1,
        DisplayNameRole
    };

    explicit UserModel(QObject *parent = nullptr);

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    QHash<int, QByteArray> roleNames() const override;

    Q_INVOKABLE void loadUsers();

signals:
    void countChanged();

private:
    QList<User> m_users;
};
