import QtQuick
import QtQuick.Window

Window {
    id: overlay
    objectName: "voiceActivityOverlayWindow"

    property string activityState: ""
    readonly property bool engaged: activityState !== ""
    readonly property bool listening: activityState === "listening"

    // A separate, non-activating tool window stays useful when settings are
    // hidden in the tray. Neither showing it nor clicking it can own focus.
    transientParent: null
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
    color: "transparent"
    width: 160
    height: 76
    x: Math.round(screen.virtualX + (screen.width - width) / 2)
    y: Math.round(screen.virtualY + screen.desktopAvailableHeight - height - 18)
    visible: engaged || capsule.opacity > 0

    Item {
        id: capsule
        objectName: "voiceActivityCapsule"
        anchors.centerIn: parent
        width: overlay.listening ? 116 : 44
        height: 44
        opacity: overlay.engaged ? 1 : 0
        scale: overlay.engaged ? 1 : 0.9
        Accessible.role: Accessible.Indicator
        Accessible.name: overlay.listening ? qsTr("语音录音中")
            : overlay.activityState === "loading" ? qsTr("语音模型加载中")
            : qsTr("语音识别中")

        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on opacity { NumberAnimation { duration: 160 } }
        Behavior on scale {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        // Layered, quiet light and shadow without a continuously rendered blur.
        Rectangle {
            anchors.centerIn: parent
            width: parent.width + 20
            height: parent.height + 20
            radius: height / 2
            color: "#08000000"
            y: 2
        }
        Rectangle {
            anchors.centerIn: parent
            width: parent.width + 10
            height: parent.height + 10
            radius: height / 2
            color: "#14000000"
        }
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            border.width: 1
            border.color: "#48526378"
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "#f01a2530" }
                GradientStop { position: 1; color: "#f0252235" }
            }
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 1
            width: Math.max(0, Math.min(58, parent.width - parent.height - 6))
            height: 1
            radius: 0.5
            color: "#406fcecc"
        }

        Row {
            id: waveform
            objectName: "voiceRecordingWaveform"
            anchors.centerIn: parent
            height: 26
            spacing: 4
            visible: opacity > 0
            opacity: overlay.listening ? 1 : 0
            scale: overlay.listening ? 1 : 0.65
            Behavior on opacity { NumberAnimation { duration: 120 } }
            Behavior on scale {
                NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
            }
            Repeater {
                model: 9
                Rectangle {
                    id: bar
                    required property int index
                    readonly property real peak: [10, 17, 23, 15, 26, 19, 24, 15, 9][index]
                    width: 4
                    height: 4
                    radius: 2
                    anchors.verticalCenter: parent.verticalCenter
                    color: index < 3 ? "#70e5d6" : index < 6 ? "#c8ecef" : "#b5abf5"

                    SequentialAnimation on height {
                        running: overlay.visible && waveform.visible
                        loops: Animation.Infinite
                        PauseAnimation { duration: bar.index * 25 }
                        NumberAnimation {
                            to: bar.peak
                            duration: 190 + bar.index * 13
                            easing.type: Easing.InOutSine
                        }
                        NumberAnimation {
                            to: 4
                            duration: 230 + bar.index * 9
                            easing.type: Easing.InOutSine
                        }
                    }
                }
            }
        }

        Item {
            id: spinner
            objectName: "voiceRecognitionSpinner"
            anchors.centerIn: parent
            width: 24
            height: 24
            visible: opacity > 0
            opacity: overlay.engaged && !overlay.listening ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 160 } }

            Canvas {
                anchors.fill: parent
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.reset()
                    const center = width / 2
                    const radius = center - 3
                    ctx.lineWidth = 2.5
                    ctx.lineCap = "round"
                    ctx.strokeStyle = "#384454"
                    ctx.beginPath()
                    ctx.arc(center, center, radius, 0, Math.PI * 2)
                    ctx.stroke()
                    const gradient = ctx.createLinearGradient(2, 2, width - 2, height - 2)
                    gradient.addColorStop(0, "#70e5d6")
                    gradient.addColorStop(0.55, "#c8ecef")
                    gradient.addColorStop(1, "#b5abf5")
                    ctx.strokeStyle = gradient
                    ctx.beginPath()
                    ctx.arc(center, center, radius, -Math.PI / 2, Math.PI)
                    ctx.stroke()
                }
            }
            NumberAnimation on rotation {
                running: overlay.visible && spinner.visible
                from: 0
                to: 360
                duration: 1050
                loops: Animation.Infinite
            }
        }
    }
}
