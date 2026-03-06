#include "greetdclient.h"
#include <QJsonDocument>
#include <QJsonArray>
#include <QDebug>

GreetdClient::GreetdClient(QObject *parent)
    : QObject(parent)
    , m_socket(new QLocalSocket(this))
{
    QObject::connect(m_socket, &QLocalSocket::readyRead, this, &GreetdClient::onReadyRead);
    QObject::connect(m_socket, &QLocalSocket::disconnected, this, [this]() {
        m_connected = false;
        emit connectedChanged();
    });
}

GreetdClient::~GreetdClient()
{
    close();
}

void GreetdClient::connectToGreetd(const QString &socketPath)
{
    m_socket->connectToServer(socketPath);
    if (m_socket->waitForConnected(1000)) {
        m_connected = true;
        emit connectedChanged();
    } else {
        emit error("connection", "Failed to connect to greetd socket");
    }
}

void GreetdClient::createSession(const QString &username)
{
    QJsonObject payload;
    payload["type"] = "create_session";
    payload["username"] = username;
    send(payload);
}

void GreetdClient::postAuthResponse(const QString &response)
{
    QJsonObject payload;
    payload["type"] = "post_auth_message_response";
    payload["response"] = response;
    send(payload);
}

void GreetdClient::startSession(const QString &command)
{
    QJsonObject payload;
    payload["type"] = "start_session";
    
    QJsonArray cmdArray;
    for (const QString &part : command.split(" ")) {
        cmdArray.append(part);
    }
    payload["cmd"] = cmdArray;
    payload["env"] = QJsonArray();
    send(payload);
}

void GreetdClient::cancelSession()
{
    QJsonObject payload;
    payload["type"] = "cancel_session";
    send(payload);
}

void GreetdClient::close()
{
    if (m_socket) {
        m_socket->disconnectFromServer();
        m_connected = false;
        emit connectedChanged();
    }
}

void GreetdClient::onReadyRead()
{
    m_buffer.append(m_socket->readAll());

    while (m_buffer.size() >= 4) {
        quint32 len = *reinterpret_cast<const quint32*>(m_buffer.constData());
        if (m_buffer.size() < 4 + static_cast<int>(len))
            break;

        QByteArray body = m_buffer.mid(4, len);
        m_buffer.remove(0, 4 + len);

        QJsonParseError err;
        QJsonObject reply = QJsonDocument::fromJson(body, &err).object();
        if (err.error != QJsonParseError::NoError) {
            emit error("protocol", "Invalid JSON from greetd");
            continue;
        }

        QString type = reply["type"].toString();

        if (type == "success") {
            emit success();
        } else if (type == "error") {
            handleError(reply);
        } else if (type == "auth_message") {
            int msgType = 0;
            QString authType = reply["auth_message_type"].toString();
            if (authType == "visible") msgType = 1;
            else if (authType == "secret") msgType = 2;
            else if (authType == "info") msgType = 3;
            else if (authType == "error") msgType = 4;
            
            emit authMessage(msgType, reply["auth_message"].toString());
        }
    }
}

void GreetdClient::send(const QJsonObject &payload)
{
    QByteArray body = QJsonDocument(payload).toJson(QJsonDocument::Compact);
    quint32 len = body.size();
    m_socket->write(reinterpret_cast<const char*>(&len), 4);
    m_socket->write(body);
    m_socket->flush();
}

void GreetdClient::handleError(const QJsonObject &msg)
{
    QString errorType = msg["error_type"].toString();
    QString description = msg["description"].toString();
    emit error(errorType, description);
}
