#pragma once

#include <QAbstractListModel>
#include <QStringList>

struct Session {
    QString name;
    QString command;
};

class SessionModel : public QAbstractListModel {
    Q_OBJECT
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged)

public:
    enum Roles {
        NameRole = Qt::UserRole + 1,
        CommandRole
    };

    explicit SessionModel(QObject *parent = nullptr);

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    QHash<int, QByteArray> roleNames() const override;

    Q_INVOKABLE void loadSessions();
    Q_INVOKABLE QString commandAt(int index) const;

signals:
    void countChanged();

private:
    QList<Session> m_sessions;
    void addSession(const QString &name, const QString &command);
};
