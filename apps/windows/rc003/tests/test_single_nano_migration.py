import unittest
from ovb_rc003 import voice_program_manager as manager, config, local_speech_provider as speech

class SingleNanoMigrationTests(unittest.TestCase):
    def test_only_nano_is_a_selectable_local_model(self):
        self.assertEqual(manager.LOCAL_VOICE_PROVIDERS,frozenset({speech.NANO}))
        self.assertEqual(set(manager.VOICE_PROGRAM_SELECTABLE_PROVIDER_ORDER) &
            {"faster_whisper","paraformer_streaming","qwen3_asr"},set())
        self.assertIn("fun_asr_nano",manager.VOICE_PROGRAM_SELECTABLE_PROVIDER_ORDER)

    def test_retired_provider_configs_migrate_without_changing_external_providers(self):
        for old in ("faster_whisper","paraformer_streaming","qwen3_asr"):
            with self.subTest(old=old):
                normalized=manager.normalize_voice_program_settings({"provider":old,"faster_whisper_threads":8})
                self.assertEqual(normalized["provider"],speech.NANO)
                self.assertEqual(normalized["faster_whisper_threads"],8)
                self.assertFalse(normalized["launch_elevated"])
                self.assertEqual(manager.provider_index(old),manager.provider_index(speech.NANO))
        for external in ("none","sogou","wetype","doubao_ime","chatterfly","custom"):
            self.assertEqual(manager.normalize_voice_program_settings({"provider":external})["provider"],external)
