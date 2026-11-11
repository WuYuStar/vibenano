import errno
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from ovb_rc003 import config, data_migration, dev_session, hid_helper_consumers


class DataMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.env = mock.patch.dict(os.environ, {"LOCALAPPDATA": str(self.base), "REMOTE_MIC_ISOLATED_TEST": "0"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.old = config.legacy_config_root()
        self.new = config.config_root()

    def write(self, relative, data=b"settings"):
        path = self.old / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_path_lookup_does_not_migrate_or_create_data(self):
        self.assertEqual(self.new, self.base / "VibeNano/RC003")
        self.assertFalse(self.new.exists())

    def test_copies_settings_without_changing_legacy_and_skips_runtime_files(self):
        for name in data_migration.SETTINGS:
            self.write(name, b'{"schema_version":17}')
        self.write("logs/app.log")
        self.write("bridge-runtime-status-s1.json")
        self.write("hid-helper-consumers/old.json")
        config.migrate_legacy_data()
        for name in data_migration.SETTINGS:
            self.assertEqual((self.new/name).read_bytes(), (self.old/name).read_bytes())
        self.assertFalse((self.new/"logs").exists())
        self.assertFalse((self.new/"bridge-runtime-status-s1.json").exists())
        self.assertFalse((self.new/"hid-helper-consumers").exists())
        self.assertTrue(data_migration.completed(self.new))

    def test_reuses_complete_nano_files_but_not_other_engines_or_partial_downloads(self):
        model = self.write("models/fun-asr-nano/gguf/encoder.gguf", b"GGUF-model")
        self.write("models/fun-asr-nano/nano-ready.json", b'{"path":"gguf"}')
        self.write("models/fun-asr-nano/gguf/decoder.gguf.part")
        self.write("models/fun-asr-nano/nano-download.json")
        self.write("models/qwen3-asr/unused")
        config.migrate_legacy_data()
        copied = self.new / model.relative_to(self.old)
        self.assertEqual(copied.read_bytes(), b"GGUF-model")
        self.assertTrue(os.path.samefile(model, copied))
        self.assertFalse((copied.parent/"decoder.gguf.part").exists())
        self.assertFalse((self.new/"models/qwen3-asr").exists())
        self.assertFalse((self.new/"models/fun-asr-nano/nano-download.json").exists())

    def test_cross_volume_model_link_failure_falls_back_to_atomic_copy(self):
        model = self.write("models/fun-asr-nano/gguf/model.gguf", b"GGUF-model")
        original = os.link
        def link(source, target, *args, **kwargs):
            if Path(source) == model:
                raise OSError(errno.EXDEV, "different volumes")
            return original(source, target, *args, **kwargs)
        with mock.patch.object(data_migration.os, "link", side_effect=link):
            config.migrate_legacy_data()
        copied = self.new / model.relative_to(self.old)
        self.assertEqual(copied.read_bytes(), model.read_bytes())
        self.assertFalse(os.path.samefile(model, copied))

    def test_never_overwrites_existing_new_settings_or_models(self):
        self.write("config.json", b"old-settings")
        self.write("models/fun-asr-nano/gguf/model.gguf", b"old-model")
        target = self.new/"models/fun-asr-nano/gguf/model.gguf"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"new-model")
        (self.new/"config.json").write_bytes(b"new-settings")
        config.migrate_legacy_data()
        self.assertEqual(target.read_bytes(), b"new-model")
        self.assertEqual((self.new/"config.json").read_bytes(), b"new-settings")

    def test_failed_copy_leaves_no_partial_destination_and_can_retry(self):
        self.write("config.json", b"legacy-settings")
        with mock.patch.object(data_migration.shutil, "copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                config.migrate_legacy_data()
        self.assertFalse(data_migration.completed(self.new))
        self.assertFalse((self.new/"config.json").exists())
        self.assertEqual((self.old/"config.json").read_bytes(), b"legacy-settings")
        config.migrate_legacy_data()
        self.assertTrue(data_migration.completed(self.new))

    def test_completed_migration_does_not_reimport_legacy_changes(self):
        self.write("config.json", b"original")
        config.migrate_legacy_data()
        (self.new/"config.json").unlink()
        self.write("config.json", b"stale-legacy")
        config.migrate_legacy_data()
        self.assertFalse((self.new/"config.json").exists())

    def test_legacy_control_location_is_used_until_import_completes(self):
        self.old.mkdir(parents=True)
        self.assertEqual(config.control_root(), self.old)
        config.migrate_legacy_data()
        self.assertEqual(config.control_root(), self.new)

    def test_helper_registry_uses_new_directory_without_recreating_legacy_root(self):
        self.assertEqual(hid_helper_consumers.consumer_directory(self.new),
                         self.new / "hid-helper-consumers")
        self.assertFalse(self.old.exists())

    def test_device_symbol_cache_uses_new_brand_directory(self):
        from ovb_rc003 import chromecast_hid_tap_windows as tap
        self.assertEqual(tap._symbol_cache(), self.base / "VibeNano/HidSymbols")
        self.assertFalse((self.base / "RemoteMic").exists())

    def test_isolated_session_never_imports_normal_user_data(self):
        with mock.patch.object(dev_session, "is_isolated", return_value=True), \
                mock.patch.object(dev_session, "isolated_root", return_value=self.base/"isolated"), \
                mock.patch.object(data_migration, "migrate") as migrate:
            self.assertEqual(config.migrate_legacy_data(), self.base/"isolated")
            migrate.assert_not_called()


class MigrationStartupOwnershipTests(unittest.TestCase):
    def test_import_is_inside_the_owned_desktop_lifetime(self):
        from ovb_rc003 import __main__ as main, single_instance, settings_ui
        events = []
        class Guard:
            def __init__(self, name): self.name = name
            def __enter__(self): events.append(self.name+" enter"); return self
            def __exit__(self, *args): events.append(self.name+" exit")
        with mock.patch.object(dev_session, "is_isolated", return_value=False), \
                mock.patch.object(single_instance, "ApplicationRuntimeInstanceGuard", side_effect=lambda: Guard("runtime")), \
                mock.patch.object(single_instance, "ApplicationInstanceGuard", side_effect=lambda: Guard("owner")), \
                mock.patch.object(main, "_migrate_legacy_bridge_before_desktop_start", side_effect=lambda: events.append("old bridge stopped") or False), \
                mock.patch.object(config, "migrate_legacy_data", side_effect=lambda: events.append("data imported")), \
                mock.patch.object(main, "_register_current_hid_helper_consumer"), \
                mock.patch.object(settings_ui, "main", side_effect=lambda **kwargs: events.append("settings opened")):
            main._run_settings()
        self.assertLess(events.index("owner enter"), events.index("data imported"))
        self.assertLess(events.index("old bridge stopped"), events.index("data imported"))
        self.assertLess(events.index("data imported"), events.index("settings opened"))
        self.assertLess(events.index("settings opened"), events.index("owner exit"))
