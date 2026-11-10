"""Real spawn/pipe tests; no microphones, desktop, downloads or native models."""
import multiprocessing
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

from ovb_rc003 import local_speech_provider as speech


def fake_worker(pipe, engine, model, threads, root):
    pipe.send(("ready", None))
    count = 0
    try:
        while True:
            op, payload = pipe.recv()
            if op == "reset":
                count = 0
                pipe.send(("ok", None))
            elif op == "feed":
                count += len(payload)
                pipe.send(("ok", None))
            elif op == "finish":
                if payload[0] == b"\x02\x00":
                    return
                if engine == speech.NANO and payload[0] == b"\x01\x00" * 99:
                    time.sleep(30)
                pipe.send(("text", f"{engine}:{count}:{os.getpid()}"))
    except (EOFError, BrokenPipeError, OSError):
        pass
    finally:
        pipe.close()


def unavailable_worker(pipe, *args):
    pipe.send(("unavailable", None))
    pipe.close()


def loading_worker(pipe, *args):
    time.sleep(30)


class LocalSpeechProcessTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.texts, self.statuses = [], []
        self.done = threading.Event()

    def runtime(self, engine=speech.NANO, target=fake_worker):
        def text(owner, value, target):
            self.texts.append((owner, value, target))
            self.done.set()
            return True
        r = speech.LocalSpeechRuntime(Path(self.root.name),
            on_status=lambda owner, status: self.statuses.append((owner, status)),
            on_text=text, logger=None, engine=engine, worker_target=target)
        self.addCleanup(lambda: r.close(timeout=3))
        return r

    def wait(self, predicate):
        end = time.monotonic() + 8
        while time.monotonic() < end:
            if predicate():
                return
            time.sleep(.01)
        self.fail("worker condition timed out")

    def test_repeated_utterances_reuse_one_child_and_close_reclaims_it(self):
        runtime = self.runtime()
        for _ in range(2):
            self.done.clear()
            self.assertTrue(runtime.submit(object(), b"\x01\x00" * 100, {}))
            self.assertTrue(self.done.wait(8))
        self.assertEqual(self.texts[0][1].split(":")[-1], self.texts[1][1].split(":")[-1])
        child = runtime._process_model.process
        self.assertTrue(runtime.close(timeout=3))
        self.assertFalse(child.is_alive())

    def test_cancelled_native_result_is_not_delivered(self):
        runtime = self.runtime()
        owner = object()
        self.assertTrue(runtime.submit(owner, b"\x01\x00" * 99, {}))
        self.wait(lambda: runtime._process_model is not None)
        runtime.cancel(owner)
        self.assertTrue(runtime.close(timeout=3))
        self.assertEqual(self.texts, [])

    def test_failed_worker_is_discarded_and_next_attempt_can_retry(self):
        runtime = self.runtime()
        self.assertTrue(runtime.submit(object(), b"\x02\x00", {}))
        self.wait(lambda: "failed" in [status for _, status in self.statuses])
        self.assertIsNone(runtime._process_model)
        self.assertTrue(runtime.submit(object(), b"\x01\x00" * 100, {}))
        self.assertTrue(self.done.wait(8))
        self.assertEqual(len(self.texts), 1)

    def test_retired_engines_are_rejected(self):
        for name in ("faster_whisper", "paraformer_streaming", "qwen3_asr", "unknown"):
            with self.assertRaises(ValueError):
                speech.LocalSpeechRuntime(self.root.name, on_status=lambda *a: None,
                    on_text=lambda *a: True, logger=None, engine=name)

    def test_unused_engine_has_no_child_or_model(self):
        r = self.runtime()
        self.assertIsNone(r._process_model)
        self.assertIsNone(r._model)



    def test_close_interrupts_blocked_inference_and_prevents_late_text(self):
        r = self.runtime()
        self.assertTrue(r.submit(object(), b"\x01\x00" * 99, {}))
        self.wait(lambda: any(s == "transcribing" for _, s in self.statuses))
        child = r._process_model.process
        start = time.monotonic()
        self.assertTrue(r.close(timeout=3))
        self.assertLess(time.monotonic() - start, 5)
        self.assertFalse(child.is_alive())
        self.assertEqual(self.texts, [])

    def test_close_interrupts_model_loading(self):
        r = self.runtime(target=loading_worker)
        r.submit(object(), b"\x01\x00", {})
        self.wait(lambda: r._process_model is not None and r._process_model.process.pid is not None)
        child = r._process_model.process
        self.assertTrue(r.close(timeout=3))
        self.assertFalse(child.is_alive())
        self.assertEqual(self.texts, [])


    def test_unavailable_component_reports_status_without_text(self):
        r = self.runtime(target=unavailable_worker)
        r.submit(object(), b"\x01\x00", {})
        self.wait(lambda: r._queue.unfinished_tasks == 0)
        self.assertIn("unavailable", [s for _, s in self.statuses])
        self.assertEqual(self.texts, [])

    def test_silence_does_not_load_whisper(self):
        r = self.runtime()
        r.submit(object(), b"\0\0" * 100, {})
        self.wait(lambda: r._queue.unfinished_tasks == 0)
        self.assertIsNone(r._process_model)
        self.assertEqual(self.texts, [])



