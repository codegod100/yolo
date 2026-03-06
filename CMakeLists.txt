cmake_minimum_required(VERSION 3.20)

project(yolo-greeter 
    VERSION 1.0.0 
    LANGUAGES CXX
    DESCRIPTION "Kirigami-based greetd login manager"
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(ECM REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} ${ECM_MODULE_PATH})

include(KDEInstallDirs)
include(KDECMakeSettings)
include(FeatureSummary)

find_package(Qt6 REQUIRED COMPONENTS Core Quick QuickControls2 Svg)
find_package(KF6 REQUIRED COMPONENTS Kirigami)

set(SOURCES
    src/main.cpp
    src/qml_data.h
    src/backend/greetdclient.cpp
    src/backend/greetdclient.h
    src/backend/sessionmodel.cpp
    src/backend/sessionmodel.h
    src/backend/usermodel.cpp
    src/backend/usermodel.h
    src/backend/process.h
)

add_executable(yolo-greeter ${SOURCES})

target_include_directories(yolo-greeter PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src/backend
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(yolo-greeter PRIVATE
    Qt6::Core
    Qt6::Quick
    Qt6::QuickControls2
    Qt6::Svg
    KF6::Kirigami
)

install(TARGETS yolo-greeter 
    DESTINATION ${CMAKE_INSTALL_BINDIR}
)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/yolo-greeter.desktop.in
    ${CMAKE_CURRENT_BINARY_DIR}/yolo-greeter.desktop
    @ONLY
)

install(FILES ${CMAKE_CURRENT_BINARY_DIR}/yolo-greeter.desktop
    DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/wayland-sessions
)

feature_summary(WHAT ALL FATAL_ON_MISSING_REQUIRED_PACKAGES)
