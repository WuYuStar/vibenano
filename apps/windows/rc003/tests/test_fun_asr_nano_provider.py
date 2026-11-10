"""Native protocol bounds, real worker selection and cancellation barriers."""
import io
import struct
import threading
import unittest
from unittest import mock
from ovb_rc003 import fun_asr_nano_provider as nano
from ovb_rc003 import local_speech_provider as speech
from ovb_rc003 import model_downloads as downloads
from ovb_rc003 import voice_program_manager as manager
from ovb_rc003 import config
from tests.test_local_speech_provider import LocalSpeechProcessTests

class NanoProtocolTests(unittest.TestCase):
    def model(self, text="创建一个 agent 调用 API"):
        model = nano.NativeNanoModel.__new__(nano.NativeNanoModel)
        data = text.encode("utf-8")
        model.process = mock.Mock(stdin=io.BytesIO(), stdout=io.BytesIO(struct.pack("<I",len(data))+data))
        return model

    def test_utf8_text_and_pcm_are_framed_without_audio_files(self):
        model=self.model()
        pcm=b"\x01\x00" * 100
        self.assertEqual(model.transcribe(pcm),"创建一个 agent 调用 API")
        self.assertEqual(model.process.stdin.getvalue(),struct.pack("<I",len(pcm))+pcm)

    def test_truncated_or_oversized_response_fails(self):
        for data in (b"",struct.pack("<I",10)+b"short",struct.pack("<I",1024*1024+1)):
            with self.subTest(data=data):
                model=self.model();model.process.stdout=io.BytesIO(data)
                with self.assertRaises((OSError,ValueError)):model.transcribe(b"\x01\x00")

    def test_invalid_pcm_is_rejected_before_write(self):
        model=self.model()
        for pcm in (b"x","string",bytearray(2)):
            with self.assertRaises(ValueError):model.transcribe(pcm)
        self.assertEqual(model.process.stdin.getvalue(),b"")

    def test_nano_configuration_has_independent_identity_and_cache(self):
        self.assertEqual(speech.normalize_settings({"provider":speech.NANO})["provider"],speech.NANO)
        settings=manager.normalize_voice_program_settings({"provider":speech.NANO})
        self.assertEqual(settings["provider"],speech.NANO)
        self.assertFalse(settings["launch_on_bridge_start"])
        self.assertFalse(settings["launch_elevated"])
        self.assertEqual(downloads.validate(speech.NANO,"small"),"nano")
        self.assertEqual(downloads.cache_root("models",speech.NANO).name,"fun-asr-nano")
        self.assertNotEqual(downloads.cache_root("models",speech.NANO),downloads.cache_root("other-models",speech.NANO))

class NanoLifecycleTests(LocalSpeechProcessTests):
    def test_nano_is_lazy_reuses_one_child_and_releases_it_on_close(self):
        runtime=self.runtime(speech.NANO)
        self.assertIsNone(runtime._process_model)
        for _ in range(2):
            self.done.clear()
            self.assertTrue(runtime.submit(object(),b"\x01\x00"*100,{}))
            self.assertTrue(self.done.wait(8))
        self.assertEqual(len(self.texts),2)
        self.assertEqual(self.texts[0][1].split(":")[-1],self.texts[1][1].split(":")[-1])
        child=runtime._process_model.process
        self.assertTrue(runtime.close(timeout=3))
        self.assertFalse(child.is_alive())
