from array import array
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

from ovb_rc003 import local_speech_core as provider


DEFAULTS = {
    provider.MODEL_SETTING: "small",
    provider.THREADS_SETTING: 4,
    provider.BEAM_SIZE_SETTING: 1,
}


def pcm(*samples):
    return array("h", samples).tobytes()


class Recorder:
    def __init__(self):
        self.condition = threading.Condition()
        self.statuses = []
        self.texts = []
        self.text_result = True
        self.text_threads = []

    def on_status(self, owner, state):
        with self.condition:
            self.statuses.append((owner, state))
            self.condition.notify_all()

    def on_text(self, owner, text, target):
        with self.condition:
            self.texts.append((owner, text, target))
            self.text_threads.append(threading.current_thread().name)
            self.condition.notify_all()
        return self.text_result

    def wait_status(self, owner, state, timeout=2.0):
        with self.condition:
            return self.condition.wait_for(
                lambda: (owner, state) in self.statuses,
                timeout=timeout,
            )

    def states(self, owner):
        with self.condition:
            return [state for candidate, state in self.statuses if candidate is owner]

    def text_for(self, owner):
        with self.condition:
            return [entry for entry in self.texts if entry[0] is owner]


class FakeModel:
    def __init__(self, segments=(" recognized ",), hook=None):
        self.segments = segments
        self.hook = hook
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio.copy(), kwargs, threading.current_thread().name))
        if self.hook is not None:
            self.hook(len(self.calls))

        def generate():
            for text in self.segments:
                yield SimpleNamespace(text=text)

        return generate(), SimpleNamespace(language="zh")


class FakeFactory:
    def __init__(self, make_model=None):
        self.make_model = make_model or (lambda _index: FakeModel())
        self.calls = []
        self.models = []
        self.threads = []

    def __call__(self, model_name, cpu_threads, model_root):
        self.calls.append((model_name, cpu_threads, model_root))
        self.threads.append(threading.current_thread().name)
        model = self.make_model(len(self.calls))
        self.models.append(model)
        return model


class SettingsTests(unittest.TestCase):
    def test_defaults_and_all_allowed_values(self):
        self.assertEqual(provider.normalize_settings(None), DEFAULTS)
        self.assertEqual(provider.normalize_settings({}), DEFAULTS)
        for model in provider.ALLOWED_MODELS:
            for threads in provider.ALLOWED_CPU_THREADS:
                for beam in provider.ALLOWED_BEAM_SIZES:
                    with self.subTest(model=model, threads=threads, beam=beam):
                        self.assertEqual(
                            provider.normalize_settings(
                                {
                                    provider.MODEL_SETTING: model,
                                    provider.THREADS_SETTING: threads,
                                    provider.BEAM_SIZE_SETTING: beam,
                                }
                            ),
                            {
                                provider.MODEL_SETTING: model,
                                provider.THREADS_SETTING: threads,
                                provider.BEAM_SIZE_SETTING: beam,
                            },
                        )

    def test_invalid_values_fall_back_per_field_without_coercion(self):
        for invalid in (True, False, 3, 1.0, "4", None, [], object()):
            with self.subTest(invalid=invalid):
                normalized = provider.normalize_settings(
                    {
                        provider.MODEL_SETTING: "tiny",
                        provider.THREADS_SETTING: invalid,
                        provider.BEAM_SIZE_SETTING: invalid,
                    }
                )
                self.assertEqual(normalized[provider.MODEL_SETTING], "tiny")
                self.assertEqual(normalized[provider.THREADS_SETTING], 4)
                self.assertEqual(normalized[provider.BEAM_SIZE_SETTING], 1)
        for invalid in ("SMALL", "medium", "", 1, True, None, [], object()):
            with self.subTest(model=invalid):
                normalized = provider.normalize_settings(
                    {provider.MODEL_SETTING: invalid}
                )
                self.assertEqual(normalized, DEFAULTS)
        normalized = provider.normalize_settings({})
        normalized[provider.MODEL_SETTING] = "tiny"
        self.assertEqual(provider.normalize_settings({}), DEFAULTS)


class PcmCaptureTests(unittest.TestCase):
    def test_finish_is_immutable_repeatable_and_seals_capture(self):
        capture = provider.PcmCapture(max_seconds=0.01)
        source = bytearray(pcm(-32768, 0, 32767))
        self.assertTrue(capture.append(memoryview(source)))
        source[0] = 0
        expected = pcm(-32768, 0, 32767)
        finished = capture.finish()
        self.assertIsInstance(finished, bytes)
        self.assertEqual(finished, expected)
        self.assertIs(capture.finish(), finished)
        self.assertFalse(capture.append(pcm(1)))
        capture.cancel()
        self.assertEqual(capture.finish(), expected)

    def test_overflow_and_malformed_chunks_fail_closed_and_clear_audio(self):
        for malformed in (pcm(4), b"\x00"):
            with self.subTest(malformed=malformed):
                capture = provider.PcmCapture(max_seconds=3 / provider.SAMPLE_RATE)
                self.assertTrue(capture.append(pcm(1, 2, 3)))
                self.assertFalse(capture.append(malformed))
                self.assertFalse(capture.append(pcm(4)))
                self.assertEqual(capture.finish(), b"")
                self.assertEqual(capture.finish(), b"")
                capture.cancel()
                capture.cancel()
                self.assertEqual(capture.finish(), b"")

    def test_cancel_is_idempotent_and_empty_finish_seals(self):
        capture = provider.PcmCapture()
        self.assertTrue(capture.append(b""))
        self.assertEqual(capture.finish(), b"")
        self.assertFalse(capture.append(pcm(1)))

        capture = provider.PcmCapture()
        self.assertTrue(capture.append(pcm(1)))
        capture.cancel()
        capture.cancel()
        self.assertFalse(capture.append(pcm(2)))
        self.assertEqual(capture.finish(), b"")


