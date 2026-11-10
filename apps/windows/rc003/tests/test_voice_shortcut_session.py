import threading
import unittest
from unittest import mock

from ovb_rc003 import bridge_runtime_status as status, voice_shortcut_session as shortcut


class VoiceResultTests(unittest.TestCase):
    def make_session(self, backend=shortcut._VOICE_HOTKEY_BACKEND_WETYPE):
        services = mock.Mock()
        session = shortcut.VoiceShortcutSession(
            hotkey_text="ctrl+win", logger=mock.Mock(), trace=mock.Mock(), services=services)
        session.begin_runtime(backend)
        session.track_generation(7, backend)
        return session, services

    def test_result_does_not_depend_on_audio_and_cleanup_callback_order(self):
        for confirmed in (None, False, True):
            for frames in (0, 303):
                for clean in (False, True):
                    for audio_first in (False, True):
                        with self.subTest(confirmed=confirmed, frames=frames, clean=clean, audio_first=audio_first):
                            session, services = self.make_session()
                            if confirmed is not None:
                                session.on_confirmation(7, confirmed)
                            if audio_first:
                                session.record_audio_result(frames)
                                session.on_cleanup(7, clean)
                            else:
                                session.on_cleanup(7, clean)
                                session.record_audio_result(frames)
                            expected = (status.VOICE_RUNTIME_HOST_STOP_FAILED if not clean
                                        else status.VOICE_RUNTIME_AUDIO_EMPTY if frames == 0
                                        else status.VOICE_RUNTIME_SUCCESS if confirmed is True
                                        else status.VOICE_RUNTIME_HOST_UNCONFIRMED)
                            services.set_result.assert_called_with(expected, provider="wetype")

    def test_unknown_keeps_protocol_confirmation_pending_and_never_claims_failure(self):
        session, services = self.make_session()
        session.on_confirmation(7, False)
        self.assertIsNone(session.runtime_mic_confirmed)
        self.assertEqual(session.ui_confirmation, "unknown")
        services.set_result.assert_not_called()
        session.logger.warning.assert_not_called()

    def test_late_or_stale_confirmation_cannot_rewrite_completed_or_new_attempt(self):
        for finish_first in (False, True):
            session, services = self.make_session()
            if finish_first:
                session.on_cleanup(7, True)
                session.record_audio_result(303)
            else:
                session.begin_runtime()
                session.track_generation(8)
            services.reset_mock()
            session.on_confirmation(7, True)
            services.set_result.assert_not_called()
            self.assertIsNone(session.runtime_mic_confirmed)

    def test_confirmation_publication_cannot_cross_into_next_generation(self):
        session, services = self.make_session()
        entered, proceed, begun = threading.Event(), threading.Event(), threading.Event()
        def current_state():
            entered.set()
            proceed.wait(2)
            return status.VOICE_RUNTIME_ACTIVE
        services.current_state.side_effect = current_state
        old = threading.Thread(target=lambda: session.on_confirmation(7, True))
        new = threading.Thread(target=lambda: (session.begin_runtime(), begun.set()))
        try:
            old.start()
            self.assertTrue(entered.wait(1))
            new.start()
            self.assertFalse(begun.wait(.02))
        finally:
            proceed.set()
            old.join(1)
            if new.ident is not None:
                new.join(1)
        self.assertFalse(old.is_alive())
        self.assertFalse(new.is_alive())
        self.assertTrue(begun.is_set())
        self.assertIsNone(session.runtime_mic_confirmed)
        services.set_result.assert_called_once_with(status.VOICE_RUNTIME_MIC_CONFIRMED, provider="wetype")

    def test_new_attempt_resets_ui_confirmation(self):
        session, _ = self.make_session()
        session.on_confirmation(7, True)
        session.begin_runtime()
        self.assertEqual(session.ui_confirmation, "unknown")

    def test_doubao_result_does_not_require_wetype_capture(self):
        session, services = self.make_session(shortcut._VOICE_HOTKEY_BACKEND_DOUBAO)
        session.on_cleanup(7, True)
        session.record_audio_result(303)
        services.set_result.assert_called_with(status.VOICE_RUNTIME_SUCCESS, provider="doubao_ime")


class LocalBackendShortcutTests(unittest.TestCase):
    def make_session(self):
        services = mock.Mock()
        services.configured_backend.return_value = shortcut._VOICE_HOTKEY_BACKEND_LOCAL
        trace = mock.Mock()
        trace.current_context.return_value = {}
        session = shortcut.VoiceShortcutSession(
            hotkey_text="ctrl+win",
            logger=mock.Mock(),
            trace=trace,
            services=services,
        )
        session.wetype_control = mock.Mock()
        session.doubao_control = mock.Mock()
        session.chatterfly_control = mock.Mock()
        session.doubao_physicalizer = mock.Mock()
        return session, services

    def test_local_key_down_and_up_never_emit_host_input_or_pending_tokens(self):
        session, services = self.make_session()
        with mock.patch.object(
            session,
            "send_action",
            side_effect=AssertionError("local mode must not send a host hotkey"),
        ) as send_action, mock.patch.object(
            shortcut.win32_input,
            "send_voice_key_combo_down",
        ) as marked_down, mock.patch.object(
            shortcut.win32_input,
            "send_voice_key_combo_up",
        ) as marked_up, mock.patch.object(
            shortcut.win32_input,
            "send_wetype_voice_key_combo_down",
        ) as wetype_down, mock.patch.object(
            shortcut.win32_input,
            "send_wetype_voice_key_combo_up",
        ) as wetype_up, mock.patch.object(
            shortcut.win32_keys,
            "resolve_vk_codes",
            side_effect=AssertionError("local mode must not resolve hotkey tokens"),
        ) as resolve:
            self.assertTrue(
                session.apply(shortcut.voice_controller.VoiceHostAction.KEY_DOWN)
            )
            self.assertIsNone(session.pending_tokens)
            self.assertIsNone(session.pending_backend)
            self.assertEqual(
                session.active_backend,
                shortcut._VOICE_HOTKEY_BACKEND_LOCAL,
            )
            services.resume_tracking.assert_not_called()

            self.assertTrue(
                session.apply(shortcut.voice_controller.VoiceHostAction.KEY_UP)
            )

        self.assertIsNone(session.pending_tokens)
        self.assertIsNone(session.pending_backend)
        self.assertIsNone(session.active_backend)
        self.assertIsNone(session.retry_timer)
        services.resume_tracking.assert_called_once_with()
        send_action.assert_not_called()
        marked_down.assert_not_called()
        marked_up.assert_not_called()
        wetype_down.assert_not_called()
        wetype_up.assert_not_called()
        resolve.assert_not_called()
        session.wetype_control.start.assert_not_called()
        session.wetype_control.stop.assert_not_called()
        session.doubao_control.start.assert_not_called()
        session.doubao_control.stop.assert_not_called()
        session.chatterfly_control.start.assert_not_called()
        session.chatterfly_control.stop.assert_not_called()
        session.doubao_physicalizer.expect_markers.assert_not_called()

    def test_local_backend_maps_to_local_speech_core(self):
        session, _services = self.make_session()
        self.assertEqual(
            session.provider_for_backend(shortcut._VOICE_HOTKEY_BACKEND_LOCAL),
            shortcut.voice_program_manager.VOICE_PROGRAM_FASTER_WHISPER,
        )
        self.assertEqual(
            session.provider_for_backend(shortcut._VOICE_HOTKEY_BACKEND_LOCAL),
            "faster_whisper",
        )
