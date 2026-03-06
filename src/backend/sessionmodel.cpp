#include "sessionmodel.h"
#include <QDir>
#include <QFile>
#include <QTextStream>
#include <QStandardPaths>
#include <QRegularExpression>

SessionModel::SessionModel(QObject *parent)
    : QAbstractListModel(parent)
{
    loadSessions();
}

int SessionModel::rowCount(const QModelIndex &parent) const
{
    if (parent.isValid()) return 0;
    return m_sessions.count();
}

QVariant SessionModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_sessions.count())
        return QVariant();

    const Session &session = m_sessions[index.row()];
    switch (role) {
    case NameRole:
        return session.name;
    case CommandRole:
        return session.command;
    default:
        return QVariant();
    }
}

QHash<int, QByteArray> SessionModel::roleNames() const
{
    return {
        {NameRole, "name"},
        {CommandRole, "command"}
    };
}

void SessionModel::loadSessions()
{
    beginResetModel();
    m_sessions.clear();

    QStringList sessionDirs = {
        "/usr/share/wayland-sessions",
        "/usr/share/xsessions",
        "/usr/local/share/wayland-sessions",
        "/usr/local/share/xsessions"
    };

    QSet<QString> seenCommands;

    for (const QString &dirPath : sessionDirs) {
        QDir dir(dirPath);
        if (!dir.exists()) continue;

        for (const QFileInfo &fileInfo : dir.entryInfoList({"*.desktop"}, QDir::Files)) {
            QFile file(fileInfo.absoluteFilePath());
            if (!file.open(QIODevice::ReadOnly)) continue;

            QTextStream in(&file);
            QString name, exec;
            bool inDesktopEntry = false;
            bool noDisplay = false;

            while (!in.atEnd()) {
                QString line = in.readLine().trimmed();
                if (line.startsWith('[')) {
                    inDesktopEntry = (line == "[Desktop Entry]");
                    continue;
                }
                if (!inDesktopEntry) continue;

                if (line.startsWith("Name=")) {
                    name = line.mid(5).trimmed();
                } else if (line.startsWith("Exec=")) {
                    exec = line.mid(5).trimmed();
                    // Remove field codes like %f, %u, etc.
                    exec.remove(QRegularExpression(R"(\s%[a-zA-Z])"));
                } else if (line.startsWith("NoDisplay=") && line.mid(10).trimmed().toLower() == "true") {
                    noDisplay = true;
                }
            }

            if (!noDisplay && !name.isEmpty() && !exec.isEmpty()) {
                if (!seenCommands.contains(exec)) {
                    seenCommands.insert(exec);
                    addSession(name, exec);
                }
            }
        }
    }

    // Add fallback sessions if none found
    if (m_sessions.isEmpty()) {
        addSession("Sway", "sway");
        addSession("Plasma Wayland", "startplasma-wayland");
        addSession("X11 (startx)", "startx");
        addSession("Bash", "bash");
    }

    endResetModel();
    emit countChanged();
}

void SessionModel::addSession(const QString &name, const QString &command)
{
    Session session;
    session.name = name;
    session.command = command;
    m_sessions.append(session);
}

QString SessionModel::commandAt(int index) const
{
    if (index >= 0 && index < m_sessions.count())
        return m_sessions[index].command;
    return QString();
}
