"""Recording feedback stays owned by the live session and never takes focus."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from ovb_rc003 import bridge_runtime_status as status, qt_settings_app
from tests import test_qt_settings_app


@unittest.skipUnless(test_qt_settings_app._HAS_PYSIDE6, test_qt_settings_app._SKIP_REASON)
class VoiceActivityControllerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_qt_settings_app.SettingsControllerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.controller, _ = self.fixture._make_controller()
        self.controller._bridge_running = True
        self.live = status.BridgeRuntimeStatus(
            schema=status.SCHEMA_VERSION, state=status.BridgeConnectionState.CONNECTED,
            pid=os.getpid(), updated_at=time.time(), voice_active=True,
            voice_runtime_state="receiving_audio",
            voice_runtime_provider=self.controller._voice_program_settings["provider"],
            **vars(self.controller._current_runtime_identity),
        )

    def test_release_processing_completion_and_cancel_are_distinct(self):
        c = self.controller
        for update, expected in (
            (self.live, "listening"),
            (replace(self.live, voice_active=False), ""),
            (replace(self.live, voice_active=False, voice_runtime_state="transcribing"), "processing"),
            (replace(self.live, voice_active=False, voice_runtime_state="model_loading"), "loading"),
            (replace(self.live, voice_active=False, voice_runtime_state="success"), ""),
            (replace(self.live, voice_active=False, voice_runtime_state="failed"), ""),
        ):
            with self.subTest(expected=expected, state=update.voice_runtime_state):
                c._set_bridge_input_states(update)
                self.assertEqual(c.voiceActivityState, expected)

    def test_stale_foreign_disconnected_and_stopped_sessions_hide_overlay(self):
        c = self.controller
        for invalid in (
            None, SimpleNamespace(raw_input_state="unknown", hid_tap_state="unknown"),
            replace(self.live, updated_at=time.time() - 30),
            replace(self.live, runtime_id="different-session"),
            replace(self.live, state=status.BridgeConnectionState.RETRY_WAIT),
        ):
            c._set_bridge_input_states(self.live)
            self.assertEqual(c.voiceActivityState, "listening")
            c._set_bridge_input_states(invalid)
            self.assertEqual(c.voiceActivityState, "")
        c._set_bridge_input_states(self.live)
        c._set_bridge_running(False)
        self.assertEqual(c.voiceActivityState, "")

    def test_previous_provider_cannot_leave_a_loading_animation_behind(self):
        c = self.controller
        previous = replace(self.live, voice_active=False, voice_runtime_state="model_loading")
        c._set_bridge_input_states(previous)
        self.assertEqual(c.voiceActivityState, "loading")
        c._voice_program_settings = dict(c._voice_program_settings, provider="custom")
        c._set_bridge_input_states(previous)
        self.assertEqual(c.voiceActivityState, "")

    def test_fast_poll_is_read_only_and_stops_during_exit(self):
        c = self.controller
        with mock.patch.object(status, "read_status", return_value=self.live) as read, \
                mock.patch.object(c, "refreshBridgeState") as general_refresh, \
                mock.patch.object(qt_settings_app.config, "load_config") as load, \
                mock.patch.object(qt_settings_app.config, "save_config") as save:
            c.refreshVoiceActivity()
            self.assertEqual(c.voiceActivityState, "listening")
            read.assert_called_once_with(c._config_root)
            general_refresh.assert_not_called()
            load.assert_not_called()
            save.assert_not_called()
            c._application_exit_intent.set()
            c.refreshVoiceActivity()
            self.assertEqual(c.voiceActivityState, "")
            self.assertEqual(read.call_count, 1)


_NATIVE_PROBE = r'''
import ctypes, json, os, time
from ctypes import wintypes as w
from pathlib import Path
u = ctypes.WinDLL('user32', use_last_error=True)
u.CreateDesktopW.argtypes = (w.LPCWSTR, w.LPCWSTR, w.LPVOID, w.DWORD, w.DWORD, w.LPVOID)
u.CreateDesktopW.restype = w.HANDLE
u.SetThreadDesktop.argtypes = (w.HANDLE,)
u.SetThreadDesktop.restype = w.BOOL
desktop = u.CreateDesktopW('RemoteMicOverlayTest' + str(os.getpid()), None, None, 0, 0x1ff, None)
assert desktop and u.SetThreadDesktop(desktop), ctypes.get_last_error()
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from ovb_rc003 import qt_settings_app as m
app = QGuiApplication([])
app.setQuitOnLastWindowClosed(False)
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda entries: warnings.extend(str(e) for e in entries))
engine.load(QUrl.fromLocalFile(str(m._qml_directory() / 'VoiceActivityOverlay.qml')))
assert engine.rootObjects(), warnings
overlay = engine.rootObjects()[0]
def pump(seconds):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        app.processEvents()
        time.sleep(0.01)
u.GetActiveWindow.restype = w.HWND
u.GetForegroundWindow.restype = w.HWND
u.GetWindowLongPtrW.argtypes = (w.HWND, ctypes.c_int)
u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
target = QQuickWindow()
target.setWidth(320)
target.setHeight(160)
target.show()
target.requestActivate()
pump(0.2)
active_before = u.GetActiveWindow()
foreground_before = u.GetForegroundWindow()
assert not overlay.isVisible()
overlay.setProperty('activityState', 'listening')
pump(0.35)
assert overlay.isVisible()
assert u.GetActiveWindow() == active_before, 'overlay changed active window'
assert u.GetForegroundWindow() == foreground_before, 'overlay changed foreground'
style = u.GetWindowLongPtrW(int(overlay.winId()), -20)
assert style & 0x08000000, hex(style)  # WS_EX_NOACTIVATE
assert style & 0x00000020, hex(style)  # WS_EX_TRANSPARENT
assert style & 0x00000080, hex(style)  # WS_EX_TOOLWINDOW
assert overlay.transientParent() is None
first = overlay.grabWindow()
pump(0.15)
second = overlay.grabWindow()
assert not first.isNull() and first != second, 'waveform is not animating'
waveform = overlay.findChild(type(target.contentItem()), 'voiceRecordingWaveform')
spinner = overlay.findChild(type(target.contentItem()), 'voiceRecognitionSpinner')
assert waveform is not None and spinner is not None
assert waveform.isVisible() and not spinner.isVisible()
preview = os.environ.get('RC003_OVERLAY_PREVIEW')
if preview:
    assert second.save(preview)
# Hiding the settings/target window must not hide recording feedback.
target.hide()
pump(0.1)
assert overlay.isVisible()
active_hidden = u.GetActiveWindow()
for state in ('processing', 'loading'):
    overlay.setProperty('activityState', state)
    pump(0.35)
    assert overlay.isVisible()
    assert spinner.isVisible() and not waveform.isVisible(), 'processing did not switch animation'
    first_rotation = spinner.rotation()
    frame = overlay.grabWindow()
    pump(0.15)
    assert spinner.rotation() != first_rotation, 'loading ring is not rotating'
    assert frame != overlay.grabWindow(), 'loading ring is not rendering animation'
    assert u.GetActiveWindow() == active_hidden, 'animation switch changed active window'
    assert u.GetForegroundWindow() == foreground_before, 'animation switch changed foreground'
    if preview:
        assert overlay.grabWindow().save(str(Path(preview).with_stem(Path(preview).stem + '-' + state)))
overlay.setProperty('activityState', '')
pump(0.4)
assert not overlay.isVisible(), 'overlay did not fade out'
assert not spinner.isVisible() and not waveform.isVisible()
# All bar animations stop once the overlay is hidden.
overlay.setProperty('activityState', 'listening')
pump(0.2)
assert overlay.isVisible()
assert waveform.isVisible() and not spinner.isVisible(), 'next recording did not restore waveform'
overlay.setProperty('activityState', '')
pump(0.4)
assert not warnings, warnings
print(json.dumps({'native_styles': hex(style), 'focus_preserved': True, 'animated': True,
                  'tray_independent': True, 'warnings': warnings}))
'''


@unittest.skipUnless(sys.platform == 'win32', 'requires a private Windows desktop')
class NativeVoiceActivityOverlayTests(unittest.TestCase):
    def test_native_overlay_animates_without_stealing_focus_and_hides(self):
        env = dict(os.environ, QT_QPA_PLATFORM='windows', QT_QUICK_BACKEND='software')
        result = subprocess.run([sys.executable, '-B', '-c', _NATIVE_PROBE],
                                env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout.strip().splitlines()[-1])['focus_preserved'])


@unittest.skipUnless(test_qt_settings_app._HAS_PYSIDE6, test_qt_settings_app._SKIP_REASON)
class VoiceActivityMainWindowTests(unittest.TestCase):
    def test_real_shell_polls_voice_state_while_hidden_and_hides_on_exit(self):
        from tests.test_remote_selection import _QML_PROBE
        probe = _QML_PROBE.split('def click(name):')[0] + r'''
from dataclasses import replace
from ovb_rc003 import bridge_runtime_status as s
item('bridgeStatusRefreshTimer').setProperty('running', False)
item('startupUpdateTimer').setProperty('running', False)
overlay = item('voiceActivityOverlay')
current = [s.BridgeRuntimeStatus(
    schema=s.SCHEMA_VERSION, state=s.BridgeConnectionState.CONNECTED,
    pid=os.getpid(), updated_at=time.time(), voice_active=True,
    voice_runtime_state='receiving_audio',
    voice_runtime_provider=controller._voice_program_settings['provider'],
    **vars(controller._current_runtime_identity))]
def wait_for(predicate):
    until = time.monotonic() + 1.5
    while not predicate() and time.monotonic() < until:
        app.processEvents()
        time.sleep(0.01)
    assert predicate(), (controller.voiceActivityState, overlay.isVisible(), warnings)
with mock.patch.object(s, 'read_status', side_effect=lambda *a, **kw: current[0]):
    assert not overlay.isVisible()
    controller._set_bridge_running(True)
    window.hide()
    wait_for(lambda: overlay.isVisible())
    assert not window.isVisible()
    assert overlay.property('activityState') == 'listening'
    current[0] = replace(current[0], voice_active=False, voice_runtime_state='transcribing')
    wait_for(lambda: overlay.property('activityState') == 'processing')
    assert overlay.isVisible()
    current[0] = replace(current[0], voice_runtime_state='success')
    wait_for(lambda: not overlay.isVisible())
    current[0] = replace(current[0], voice_active=True, voice_runtime_state='active')
    wait_for(lambda: overlay.isVisible())
    window.setProperty('applicationExitInProgress', True)
    wait_for(lambda: not overlay.isVisible())
    assert not item('voiceActivityRefreshTimer').property('running')
controller._set_bridge_running(False)
controller.shutdownBackgroundTasks()
m._shutdown_diagnostics_workers()
assert not warnings, warnings
print(json.dumps({'hidden_shell_feedback': True, 'warnings': warnings}))
'''
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, LOCALAPPDATA=directory, QT_QPA_PLATFORM='offscreen',
                       RC003_DISABLE_LIVE_INPUT='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
            env.pop('TEST_ISOLATED_ROOT', None)
            result = subprocess.run([sys.executable, '-B', '-c', probe], env=env,
                                    capture_output=True, text=True, encoding='utf-8', timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
