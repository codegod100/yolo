#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QIcon>
#include <QQuickStyle>
#include <QByteArray>

#include "backend/greetdclient.h"
#include "backend/sessionmodel.h"
#include "backend/usermodel.h"
#include "backend/process.h"
#include "qml_data.h"

int main(int argc, char *argv[])
{
    // Fix for EGL not available in some environments
    if (!qEnvironmentVariableIsSet("QT_QUICK_BACKEND")) {
        qputenv("QT_QUICK_BACKEND", "software");
    }

    // Use system theme (Breeze/KDE)
    if (!qEnvironmentVariableIsSet("QT_QUICK_CONTROLS_STYLE")) {
        QQuickStyle::setStyle("Breeze");
    }

    QGuiApplication app(argc, argv);
    app.setApplicationName("yolo-greeter");
    app.setApplicationDisplayName("YOLO Greeter");
    app.setOrganizationName("yolo");

    // Ensure we can find icons
    app.setWindowIcon(QIcon::fromTheme("user-identity"));

    qmlRegisterType<GreetdClient>("yolo.greeter", 1, 0, "GreetdClient");
    qmlRegisterType<SessionModel>("yolo.greeter", 1, 0, "SessionModel");
    qmlRegisterType<UserModel>("yolo.greeter", 1, 0, "UserModel");
    qmlRegisterType<Process>("yolo.greeter", 1, 0, "Process");

    QQmlApplicationEngine engine;

    // Use mock socket by default if not set
    QString socketPath = qEnvironmentVariable("GREETD_SOCK", "/tmp/greetd-test.sock");
    engine.rootContext()->setContextProperty("greetdSocketPath", socketPath);

    // Load QML from embedded string
    engine.loadData(getMainQml().toUtf8());

    if (engine.rootObjects().isEmpty())
        return -1;

    return app.exec();
}
