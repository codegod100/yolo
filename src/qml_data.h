#pragma once

// QML embedded as raw string literal
inline QString getMainQml() {
    return R"QML(
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import yolo.greeter

Kirigami.ApplicationWindow {
    id: root
    
    title: "YOLO Greeter"
    width: 800
    height: 600
    // Removed visibility: Window.FullScreen and FramelessWindowHint
    
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false
    
    pageStack.initialPage: loginPage
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    
    // === Login Page (inlined) ===
    Kirigami.ScrollablePage {
        id: loginPage
        title: "Sign In"
        
        Rectangle {
            anchors.fill: parent
            color: Kirigami.Theme.backgroundColor
            opacity: 0.9
        }
        
        property string username: ""
        property string password: ""
        property string sessionCommand: ""
        property bool isAuthenticating: false
        property bool firstSecretConsumed: false
        
        GreetdClient {
            id: greetd
            
            onSuccess: {
                if (loginPage.isAuthenticating) {
                    statusLabel.text = "Starting session..."
                    greetd.startSession(loginPage.sessionCommand)
                }
            }
            
            onAuthMessage: (type, message) => {
                if (type === 2) { // secret
                    if (!loginPage.firstSecretConsumed) {
                        greetd.postAuthResponse(loginPage.password)
                        loginPage.firstSecretConsumed = true
                    } else {
                        greetd.postAuthResponse(loginPage.password)
                    }
                } else if (type === 1) { // visible
                    greetd.postAuthResponse(loginPage.username)
                } else if (type === 3) { // info
                    root.showPassiveNotification(message)
                } else if (type === 4) { // error
                    root.showPassiveNotification(message)
                    loginPage.reset()
                }
            }
            
            onError: (errorType, description) => {
                var prettyError = formatError(errorType, description)
                root.showPassiveNotification(prettyError)
                statusLabel.text = prettyError
                greetd.cancelSession()
                loginPage.reset()
            }
            
            onSessionStarted: {
                statusLabel.text = "Session started."
                Qt.quit()
            }
            
            function formatError(errorType, description) {
                var lowered = description.toLowerCase()
                if (lowered.includes("auth_error") || lowered.includes("invalid credentials")) {
                    return "Incorrect username or password."
                }
                if (lowered.includes("pam_user_unknown")) {
                    return "This user account does not exist."
                }
                if (lowered.includes("pam_maxtries")) {
                    return "Too many failed attempts."
                }
                if (lowered.includes("session_error")) {
                    return "Session failed to start."
                }
                return description || errorType
            }
        }
        
        SessionModel { id: sessionModel }
        UserModel { id: userModel }
        
        function reset() {
            loginPage.isAuthenticating = false
            loginPage.firstSecretConsumed = false
            loginButton.enabled = true
            loginButton.text = "Sign In"
            usernameField.enabled = true
            passwordField.enabled = true
            sessionCombo.enabled = true
            passwordField.forceActiveFocus()
        }
        
        function attemptLogin() {
            if (loginPage.username.length === 0 || loginPage.password.length === 0) {
                root.showPassiveNotification("Please enter username and password")
                return
            }
            
            loginPage.sessionCommand = sessionCombo.currentText
            if (sessionCombo.currentIndex >= 0) {
                loginPage.sessionCommand = sessionModel.commandAt(sessionCombo.currentIndex)
            }
            
            if (loginPage.sessionCommand.length === 0) {
                root.showPassiveNotification("Please select or enter a session")
                return
            }
            
            loginPage.isAuthenticating = true
            loginPage.firstSecretConsumed = false
            loginButton.enabled = false
            loginButton.text = "Signing in..."
            usernameField.enabled = false
            passwordField.enabled = false
            sessionCombo.enabled = false
            statusLabel.text = "Authenticating..."
            
            greetd.connectToGreetd(greetdSocketPath)
            greetd.createSession(loginPage.username)
        }
        
        Item {
            anchors.fill: parent
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                anchors.centerIn: parent
                width: Math.min(parent.width * 0.4, 400)
                
                Kirigami.Icon {
                    source: "user-identity"
                    implicitWidth: Kirigami.Units.iconSizes.huge
                    implicitHeight: Kirigami.Units.iconSizes.huge
                    Layout.alignment: Qt.AlignHCenter
                }
                
                Kirigami.Heading {
                    text: "Sign In"
                    level: 1
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: Kirigami.Units.largeSpacing
                }
                
                Controls.ComboBox {
                    id: usernameField
                    editable: true
                    model: userModel
                    textRole: "username"
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.largeSpacing * 2
                    
                    onCurrentTextChanged: loginPage.username = currentText
                    onAccepted: passwordField.forceActiveFocus()
                }
                
                Controls.TextField {
                    id: passwordField
                    echoMode: TextInput.Password
                    placeholderText: "Password"
                    Layout.fillWidth: true
                    
                    onTextChanged: loginPage.password = text
                    onAccepted: loginPage.attemptLogin()
                }
                
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    
                    Controls.Label { text: "Session:" }
                    
                    Controls.ComboBox {
                        id: sessionCombo
                        model: sessionModel
                        textRole: "name"
                        Layout.fillWidth: true
                    }
                }
                
                Controls.Button {
                    id: loginButton
                    text: "Sign In"
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.largeSpacing
                    onClicked: loginPage.attemptLogin()
                    highlighted: true
                }
                
                Controls.Label {
                    id: statusLabel
                    text: ""
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    color: Kirigami.Theme.neutralTextColor
                }
                
                Item { Layout.fillHeight: true }
            }
        }
        
        Component.onCompleted: passwordField.forceActiveFocus()
    }
    
    Shortcut {
        sequence: "Ctrl+Alt+Delete"
        onActivated: rebootDialog.open()
    }
    
    Process {
        id: powerProcess
    }

    Kirigami.PromptDialog {
        id: rebootDialog
        title: "Reboot System"
        subtitle: "Are you sure you want to reboot?"
        standardButtons: Kirigami.PromptDialog.Ok | Kirigami.PromptDialog.Cancel
        
        onAccepted: {
            powerProcess.start("/usr/bin/loginctl", ["reboot"]);
        }
    }
}
)QML";
}
