"""Lazy Fun-ASR-Nano worker with explicit process/resource release."""
from __future__ import annotations
from collections.abc import Mapping
import multiprocessing as mp
import threading
from . import local_speech_core as core

NANO = "fun_asr_nano"
LOCAL_PROVIDERS = frozenset((NANO,))

def model_cache_root(root, engine=NANO):
    from .model_downloads import cache_root
    return cache_root(root, engine)

def normalize_settings(raw):
    result = core.normalize_settings(raw)
    result["provider"] = NANO
    return result

def _worker(pipe, engine, model_name, threads, root):
    model = None
    try:
        if engine != NANO:
            raise ValueError("unsupported local speech engine")
        from .model_downloads import ensure_model
        from .fun_asr_nano_provider import NativeNanoModel
        path = ensure_model(root, NANO)
        model = NativeNanoModel(path, threads)
        pipe.send(("ready", None))
        while True:
            op, payload = pipe.recv()
            if op == "stop":
                break
            if op != "finish":
                raise ValueError("invalid speech command")
            pcm = payload[0] if isinstance(payload, tuple) else payload
            text = model.transcribe(pcm)
            pipe.send(("text", text))
            pcm = payload = text = None
    except (ImportError, OSError):
        try: pipe.send(("unavailable", None))
        except (BrokenPipeError, EOFError, OSError): pass
    except Exception:
        try: pipe.send(("failed", None))
        except (BrokenPipeError, EOFError, OSError): pass
    finally:
        if model is not None:
            model.close()
        pipe.close()

class _ProcessModel:
    def __init__(self, engine, model_name, threads, root, register, worker_target=_worker):
        context = mp.get_context("spawn")
        self.pipe, child = context.Pipe()
        self.process = context.Process(target=worker_target, args=(child, engine, model_name, threads, str(root)), daemon=True)
        self.stream_owner = None
        self.engine = engine
        self._closed = False
        self._lock = threading.Lock()
        # Publish before starting/loading: close can interrupt startup too.
        register(self)
        with self._lock:
            if self._closed:
                child.close()
                raise OSError("speech worker closed")
            self.process.start()
        child.close()
        try:
            self._receive()
        except BaseException:
            self.close()
            raise

    def _receive(self):
        kind, data = self.pipe.recv()
        if kind == "unavailable":
            raise ImportError("speech dependency or model unavailable")
        if kind == "failed":
            raise RuntimeError("speech worker failed")
        return data

    def request(self, op, payload=None):
        self.pipe.send((op, payload))
        return self._receive()

    def close(self):
        with self._lock:
            self._closed = True
            if self.process.pid is not None:
                if self.process.is_alive():
                    self.process.terminate()
                self.process.join(2)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(2)
                if self.process.is_alive():
                    raise RuntimeError("speech worker did not exit")
            self.pipe.close()



class LocalSpeechRuntime(core.LocalSpeechQueue):
    """The desktop only owns this queue; the model lives in its child."""
    def __init__(self, *args, engine=NANO, worker_target=_worker, delivery_lock=None, **kwargs):
        if engine != NANO:
            raise ValueError("unknown local speech engine")
        self._delivery_lock = delivery_lock
        self._worker_target = worker_target
        self.engine = NANO
        self._process_model = None
        self._process_lock = threading.Lock()
        kwargs["model_factory"] = self._create_model
        super().__init__(*args, **kwargs)

    def _register_process(self, model):
        with self._process_lock:
            if self._closed:
                raise OSError("runtime closed")
            self._process_model = model

    def _create_model(self, name, threads, root):
        with self._process_lock:
            old, self._process_model = self._process_model, None
        if old is not None:
            old.close()
        return _ProcessModel(NANO, name, threads, root, self._register_process, self._worker_target)

    def _process(self, job):
        if not self._job_active(job):
            return
        if not job.pcm_bytes or not any(job.pcm_bytes):
            self._notify_status(job, core.STATE_AUDIO_EMPTY)
            return
        model = self._ensure_model(job)
        if model is None or not self._job_active(job):
            return
        self._notify_status(job, core.STATE_TRANSCRIBING)
        try:
            text = model.request("finish", (job.pcm_bytes, 1))
        except Exception:
            with self._process_lock:
                failed, self._process_model = self._process_model, None
            if failed is not None:
                failed.close()
            self._model = self._model_config = None
            raise
        if not self._job_active(job):
            return
        if text:
            self._deliver_text(job, text)
        else:
            self._notify_status(job, core.STATE_AUDIO_EMPTY)

    def _deliver_text(self, job, text):
        if self._delivery_lock is None:
            return super()._deliver_text(job, text)
        with self._delivery_lock:
            return super()._deliver_text(job, text)

    def close(self, timeout=None):
        with self._state_lock:
            self._closed = True
        with self._process_lock:
            model, self._process_model = self._process_model, None
        if model is not None:
            model.close()
        result = super().close(timeout=timeout)
        self._model = self._model_config = None
        return result
