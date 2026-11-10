"""Shared PCM capture and bounded local-worker cancellation barriers.

No inference libraries or model implementations are imported here. Historical
setting keys remain readable for migration; only the CPU thread count is used.
"""

from __future__ import annotations

from array import array
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math
from numbers import Real
from pathlib import Path
import queue
import re
import sys
import threading
from typing import Any, Optional


SAMPLE_RATE = 16_000
DEFAULT_MAX_SECONDS = 600

MODEL_SETTING = "faster_whisper_model"
THREADS_SETTING = "faster_whisper_threads"
BEAM_SIZE_SETTING = "faster_whisper_beam_size"

DEFAULT_MODEL = "small"
ALLOWED_MODELS = ("tiny", "base", "small")
DEFAULT_CPU_THREADS = 4
ALLOWED_CPU_THREADS = (1, 2, 4, 8)
DEFAULT_BEAM_SIZE = 1
ALLOWED_BEAM_SIZES = (1, 2, 5)

DEFAULT_QUEUE_SIZE = 2
PAUSE_SPACE_SECONDS = 0.6

STATE_MODEL_LOADING = "model_loading"
STATE_TRANSCRIBING = "transcribing"
STATE_SUCCESS = "success"
STATE_AUDIO_EMPTY = "audio_empty"
STATE_UNAVAILABLE = "unavailable"
STATE_FAILED = "failed"
STATE_BUSY = "busy"
STATE_TEXT_SUBMIT_FAILED = "text_submit_failed"

_STOP = object()


def normalize_settings(mapping: Mapping[str, object]) -> dict[str, object]:
    """Return the three persisted engine settings, falling back per field.

    Values are deliberately not coerced: strings, floats, booleans, and other
    lookalikes do not silently select a different native inference workload.
    """

    source = mapping if isinstance(mapping, Mapping) else {}

    def value(key: str) -> object:
        try:
            return source.get(key)
        except Exception:
            return None

    model = value(MODEL_SETTING)
    if type(model) is not str or model not in ALLOWED_MODELS:
        model = DEFAULT_MODEL

    cpu_threads = value(THREADS_SETTING)
    if type(cpu_threads) is not int or cpu_threads not in ALLOWED_CPU_THREADS:
        cpu_threads = DEFAULT_CPU_THREADS

    beam_size = value(BEAM_SIZE_SETTING)
    if type(beam_size) is not int or beam_size not in ALLOWED_BEAM_SIZES:
        beam_size = DEFAULT_BEAM_SIZE

    return {
        MODEL_SETTING: model,
        THREADS_SETTING: cpu_threads,
        BEAM_SIZE_SETTING: beam_size,
    }


def pcm_bytes_from_samples(samples: object) -> bytes:
    """Pack decoded signed-int16 samples without creating an audio file."""

    if isinstance(samples, bytes):
        packed = samples
        if len(packed) % 2:
            raise ValueError("odd PCM byte count")
        return packed
    values = array("h", samples)  # type: ignore[arg-type]
    if sys.byteorder != "little":
        values.byteswap()
    return values.tobytes()


class PcmCapture:
    """Bounded in-memory mono signed-int16 16 kHz PCM accumulation.

    Once finished, cancelled, or failed, appends are harmless no-ops.  A
    malformed or overflowing append fails the whole capture rather than
    retaining a prefix that could be mistaken for a complete utterance.
    """

    def __init__(self, max_seconds: float = DEFAULT_MAX_SECONDS) -> None:
        if (
            isinstance(max_seconds, bool)
            or not isinstance(max_seconds, (int, float))
            or not math.isfinite(max_seconds)
            or max_seconds <= 0
        ):
            raise ValueError("max_seconds must be a finite positive number")
        self._max_samples = int(SAMPLE_RATE * max_seconds)
        self._samples = array("h")
        self._lock = threading.Lock()
        self._state = "active"
        self._finished_pcm = b""

    def append(self, pcm_bytes: object) -> bool:
        with self._lock:
            if self._state != "active":
                return False
            try:
                if isinstance(pcm_bytes, bytes):
                    raw = pcm_bytes
                else:
                    raw = memoryview(pcm_bytes).tobytes()
                if len(raw) % 2:
                    raise ValueError("odd PCM byte count")
                incoming_samples = len(raw) // 2
                if incoming_samples > self._max_samples - len(self._samples):
                    raise OverflowError("PCM capture bound exceeded")
                chunk = array("h")
                chunk.frombytes(raw)
                self._samples.extend(chunk)
                return True
            except Exception:
                self._samples = array("h")
                self._state = "failed"
                return False

    def finish(self) -> bytes:
        with self._lock:
            if self._state == "finished":
                return self._finished_pcm
            if self._state != "active":
                return b""
            try:
                self._finished_pcm = self._samples.tobytes()
                self._state = "finished"
                return self._finished_pcm
            except Exception:
                self._finished_pcm = b""
                self._state = "failed"
                return b""
            finally:
                self._samples = array("h")

    def cancel(self) -> None:
        with self._lock:
            if self._state == "finished":
                return
            self._samples = array("h")
            self._finished_pcm = b""
            if self._state == "active":
                self._state = "cancelled"


@dataclass
class _Job:
    owner: object
    pcm_bytes: bytes
    settings: dict[str, object]
    target: object
    cancelled: bool = False


class LocalSpeechQueue:
    """Serialize local inference while making owner cancellation explicit.

    ``model_factory`` receives ``(model_name, cpu_threads, model_root)`` and is
    called only by the daemon worker.  Owners must be unique objects per
    attempt; identity, rather than equality, controls cancellation.
    """

    def __init__(
        self,
        model_root: Path,
        on_status: Callable[[object, str], None],
        on_text: Callable[[object, str, object], bool],
        logger: Any,
        model_factory: Optional[Callable[[str, int, Path], object]] = None,
        queue_size: int = DEFAULT_QUEUE_SIZE,
    ) -> None:
        if type(queue_size) is not int or queue_size <= 0:
            raise ValueError("queue_size must be a positive integer")
        self._model_root = Path(model_root)
        self._on_status = on_status
        self._on_text = on_text
        self._logger = logger
        self._model_factory = model_factory or self._missing_model_factory
        self._queue: "queue.Queue[object]" = queue.Queue(maxsize=queue_size)

        self._state_lock = threading.Lock()
        self._submit_lock = threading.Lock()
        self._callback_lock = threading.RLock()
        self._close_lock = threading.Lock()
        self._jobs: dict[int, _Job] = {}
        self._closed = False
        self._stop_queued = False

        # These two fields are touched only by the worker, so model replacement
        # never races a submit, cancel, or close caller.
        self._model: Optional[object] = None
        self._model_config: Optional[tuple[str, int]] = None

        self._thread = threading.Thread(
            target=self._run,
            name="local-speech-queue",
            daemon=True,
        )
        self._thread.start()

    def submit(
        self,
        owner: object,
        pcm_bytes: object,
        settings: Mapping[str, object],
        target: object = None,
    ) -> bool:
        try:
            if isinstance(pcm_bytes, bytes):
                pcm = pcm_bytes
            else:
                pcm = memoryview(pcm_bytes).tobytes()
        except Exception:
            self._safe_status(owner, STATE_FAILED)
            return False
        if len(pcm) % 2:
            self._safe_status(owner, STATE_FAILED)
            return False

        job = _Job(owner, pcm, normalize_settings(settings), target)
        owner_key = id(owner)
        busy = False
        with self._submit_lock:
            with self._state_lock:
                if self._closed or not self._thread.is_alive():
                    return False
                # Reusing an owner while its old attempt is still known would
                # make cancellation ambiguous.  The public contract requires a
                # fresh identity for every attempt.
                if owner_key in self._jobs:
                    return False
                self._jobs[owner_key] = job
            try:
                self._queue.put_nowait(job)
            except queue.Full:
                with self._state_lock:
                    if self._jobs.get(owner_key) is job:
                        del self._jobs[owner_key]
                busy = True
        if busy:
            # User callbacks never run under the submission lock; in
            # particular, a busy-status callback may safely request close().
            self._safe_status(owner, STATE_BUSY)
            return False
        return True

    def cancel(self, owner: object) -> None:
        # Taking the same lock as final text delivery makes cancel a barrier:
        # once it returns, that owner cannot begin a later text callback.
        with self._callback_lock:
            with self._state_lock:
                for key, job in tuple(self._jobs.items()):
                    if job.owner is owner:
                        job.cancelled = True
                        del self._jobs[key]

    def close(self, timeout: Optional[float] = None) -> bool:
        # Closed is published before any queue or thread operation.  Even a
        # timed-out close therefore prevents all future text invocations.
        with self._state_lock:
            self._closed = True
            for job in self._jobs.values():
                job.cancelled = True
            self._jobs.clear()

        # A worker can pass its final active check and be descheduled just
        # before invoking on_text.  Cross that delivery lock before returning,
        # even when the subsequent thread join has a timeout.  Otherwise a
        # timed-out close could return immediately before that already-checked
        # callback begins.  The lock is released well before the join below.
        with self._callback_lock:
            pass

        is_worker = threading.current_thread() is self._thread
        if is_worker:
            # A status/text callback can request close.  Blocking here could
            # deadlock against another closer waiting to join this worker.
            acquired = self._close_lock.acquire(blocking=False)
        else:
            acquired = self._close_lock.acquire()
        if not acquired:
            return False
        try:
            with self._submit_lock:
                with self._state_lock:
                    self._closed = True
                    for job in self._jobs.values():
                        job.cancelled = True
                    self._jobs.clear()
                    stop_queued = self._stop_queued
                if not stop_queued:
                    self._discard_queued_jobs()
                    self._queue.put_nowait(_STOP)
                    with self._state_lock:
                        self._stop_queued = True

            # Never join while holding submission, state, or text callback
            # locks: inference completion and final delivery may need them.
            if is_worker:
                return False
            self._thread.join(timeout=timeout)
            return not self._thread.is_alive()
        finally:
            self._close_lock.release()

    def _discard_queued_jobs(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            if isinstance(item, _Job):
                item.cancelled = True
            self._queue.task_done()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                self._queue.task_done()
                return
            try:
                if isinstance(item, _Job):
                    try:
                        self._process(item)
                    except Exception as exc:
                        self._log_exception("worker", exc)
                        self._notify_status(item, STATE_FAILED)
                    finally:
                        self._finish_job(item)
            finally:
                self._queue.task_done()
                # Do not retain the last utterance and target while idle.
                item = None

    @staticmethod
    def _missing_model_factory(*_args):
        raise ImportError("A native speech worker factory is required")

    def _process(self, job: _Job) -> None:
        raise NotImplementedError("The native speech runtime owns inference")

    def _ensure_model(self, job: _Job) -> Optional[object]:
        config = (
            job.settings[MODEL_SETTING],
            job.settings[THREADS_SETTING],
        )
        if self._model is not None and self._model_config == config:
            return self._model

        self._notify_status(job, STATE_MODEL_LOADING)
        if not self._job_active(job):
            return None
        try:
            # No filesystem is touched by construction or submission; the root
            # is needed only on an actual lazy model-loading path.
            self._model_root.mkdir(parents=True, exist_ok=True)
            model = self._model_factory(config[0], config[1], self._model_root)
            if model is None:
                raise TypeError("model factory returned no model")
        except (ImportError, OSError) as exc:
            self._log_exception(STATE_MODEL_LOADING, exc)
            self._notify_status(job, STATE_UNAVAILABLE)
            return None
        except Exception as exc:
            self._log_exception(STATE_MODEL_LOADING, exc)
            self._notify_status(job, STATE_FAILED)
            return None

        # Publish a replacement only after it loaded successfully.  Beam size
        # is intentionally absent: it changes transcribe arguments, not models.
        self._model = model
        self._model_config = config
        return model

    def _deliver_text(self, job: _Job, text: str) -> None:
        try:
            with self._callback_lock:
                if not self._job_active(job):
                    return
                accepted = self._on_text(job.owner, text, job.target)
        except Exception as exc:
            self._log_exception(STATE_TEXT_SUBMIT_FAILED, exc)
            self._notify_status(job, STATE_TEXT_SUBMIT_FAILED)
            return

        if accepted is False:
            self._notify_status(job, STATE_TEXT_SUBMIT_FAILED)
        else:
            self._notify_status(job, STATE_SUCCESS)

    def _job_active(self, job: _Job) -> bool:
        with self._state_lock:
            return (
                not self._closed
                and not job.cancelled
                and self._jobs.get(id(job.owner)) is job
            )

    def _finish_job(self, job: _Job) -> None:
        with self._state_lock:
            key = id(job.owner)
            if self._jobs.get(key) is job:
                del self._jobs[key]

    def _notify_status(self, job: _Job, state: str) -> None:
        if self._job_active(job):
            self._safe_status(job.owner, state)

    def _safe_status(self, owner: object, state: str) -> None:
        try:
            self._on_status(owner, state)
        except Exception as exc:
            self._log_exception("status", exc)

    def _log_exception(self, stage: str, exc: BaseException) -> None:
        if self._logger is None:
            return
        try:
            self._logger.error(
                "local-speech stage=%s exception=%s",
                stage,
                type(exc).__name__,
            )
        except Exception:
            pass
