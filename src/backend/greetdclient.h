#pragma once

#include <QObject>
#include <QString>
#include <QJsonObject>
#include <QTcpSocket>
#include <QLocalSocket>

class GreetdClient : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool connected READ isConnected NOTIFY connectedChanged)

public:
    explicit GreetdClient(QObject *parent = nullptr);
    ~GreetdClient();

    bool isConnected() const { return m_connected; }

    Q_INVOKABLE void connectToGreetd(const QString &socketPath);
    Q_INVOKABLE void createSession(const QString &username);
    Q_INVOKABLE void postAuthResponse(const QString &response);
    Q_INVOKABLE void startSession(const QString &command);
    Q_INVOKABLE void cancelSession();
    Q_INVOKABLE void close();

signals:
    void connectedChanged();
    void success();
    void authMessage(int type, const QString &message);
    void error(const QString &errorType, const QString &description);
    void sessionStarted();

private slots:
    void onReadyRead();

private:
    void send(const QJsonObject &payload);
    QJsonObject recv();
    QByteArray recvExact(int size);
    void handleError(const QJsonObject &msg);

    QLocalSocket *m_socket = nullptr;
    bool m_connected = false;
    QByteArray m_buffer;
};
