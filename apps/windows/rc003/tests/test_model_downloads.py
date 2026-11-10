"""Nano cache, checksum, resume and pause behavior without downloading weights."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from ovb_rc003 import model_downloads as models

class ModelDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=b"GGUF fixture bytes"
        self.files={"model.gguf":(len(self.data),hashlib.sha256(self.data).hexdigest())}
        patch=mock.patch.object(models,"NANO_FILES",self.files);patch.start();self.addCleanup(patch.stop)

    def response(self,data,status=200,start=0):
        r=mock.MagicMock(status_code=status,headers={"Content-Range":f"bytes {start}-{len(self.data)-1}/{len(self.data)}"})
        r.__enter__.return_value=r;r.iter_content.return_value=[data]
        session=mock.MagicMock();session.__enter__.return_value=session;session.get.return_value=r
        patch=mock.patch("requests.Session",return_value=session);patch.start();self.addCleanup(patch.stop)
        return session

    def test_resume_publishes_ready_and_reuses_complete_cache(self):
        root=self.root/"gguf";root.mkdir();(root/"model.gguf.part").write_bytes(self.data[:4])
        remote=self.response(self.data[4:],206,4)
        path=models.ensure_model(self.root,models.NANO)
        self.assertEqual((path/"model.gguf").read_bytes(),self.data)
        self.assertEqual(remote.get.call_args.kwargs["headers"]["Range"],"bytes=4-")
        self.assertEqual(models.ensure_model(self.root,models.NANO),path)
        self.assertEqual(remote.get.call_count,1)
        self.assertEqual(models.model_status(self.root,models.NANO)["state"],"ready")

    def test_server_ignoring_range_restarts_without_duplicating_prefix(self):
        root=self.root/"gguf";root.mkdir();(root/"model.gguf.part").write_bytes(self.data[:4])
        self.response(self.data)
        path=models.ensure_model(self.root,models.NANO)
        self.assertEqual((path/"model.gguf").read_bytes(),self.data)

    def test_bad_checksum_is_visible_and_retry_succeeds(self):
        self.response(b"X"*len(self.data))
        with self.assertRaises(ValueError):models.ensure_model(self.root,models.NANO)
        self.assertEqual(models.model_status(self.root,models.NANO)["state"],"failed")
        self.assertFalse((self.root/"gguf/model.gguf.part").exists())
        self.response(self.data);models.ensure_model(self.root,models.NANO)
        self.assertEqual(models.model_status(self.root,models.NANO)["state"],"ready")

    def test_partial_and_escaped_ready_markers_are_not_valid(self):
        (self.root/"nano-ready.json").write_text(json.dumps({"path":".."}))
        self.assertIsNone(models.cached_model(self.root))
        root=self.root/"gguf";root.mkdir();(root/"model.gguf").write_bytes(self.data[:-1])
        self.assertIsNone(models.cached_model(self.root))

    def test_dead_downloader_becomes_resumable_and_unknown_engines_rejected(self):
        (self.root/"nano-download.json").write_text(json.dumps({"state":"downloading","pid":0,"percent":35}))
        self.assertEqual(models.model_status(self.root,models.NANO)["state"],"paused")
        for engine in ("faster_whisper","paraformer_streaming","qwen3_asr"):
            with self.assertRaises(ValueError):models.ensure_model(self.root,engine)

    def test_idle_manager_close_is_idempotent(self):
        manager=models.ModelDownloadManager(self.root);manager.close();manager.close()
        self.assertIsNone(manager.process)
