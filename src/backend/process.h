#pragma once

#include <QObject>
#include <QProcess>
#include <QStringList>

class Process : public QObject
{
    Q_OBJECT
public:
    explicit Process(QObject *parent = nullptr) : QObject(parent) {}

    Q_INVOKABLE void start(const QString &program, const QStringList &arguments = {}) {
        QProcess::startDetached(program, arguments);
    }
};
