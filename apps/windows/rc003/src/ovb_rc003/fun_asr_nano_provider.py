"""CPU-only GGUF inference in a persistent, private native child.

No audio files, local HTTP server or third-party ASR imports. Parent worker
termination closes its Windows job and also terminates the native child.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import struct
import subprocess
import sys

_MAX_PCM_BYTES = 16000 * 2 * 600
_MAX_TEXT_BYTES = 1024 * 1024
_worker_job = None


def _protect_native_children():
    global _worker_job
    if _worker_job is not None:
        return
    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]
    class Io(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount",
            "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Io),
            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    api.CreateJobObjectW.restype = wintypes.HANDLE
    api.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    api.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    api.GetCurrentProcess.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Extended()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    if not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.get_last_error(); api.CloseHandle(job); raise ctypes.WinError(error)
    if not api.AssignProcessToJobObject(job, api.GetCurrentProcess()):
        error = ctypes.get_last_error(); api.CloseHandle(job); raise ctypes.WinError(error)
    # Intentionally kept until OS process teardown. Closing a job containing
    # this worker earlier would terminate the worker itself.
    _worker_job = job


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        piece = stream.read(remaining)
        if not piece:
            raise OSError("Nano worker closed its pipe")
        chunks.append(piece)
        remaining -= len(piece)
    return b"".join(chunks)


class NativeNanoModel:
    def __init__(self, root, threads=4):
        if sys.platform != "win32":
            raise OSError("Nano native runtime requires Windows")
        if type(threads) is not int or threads not in (1, 2, 4, 8):
            raise ValueError("invalid Nano thread count")
        _protect_native_children()
        root = Path(root)
        runtime = (Path(sys._MEIPASS) / "fun_asr_nano" if getattr(sys, "frozen", False)
                   else Path(__file__).resolve().parents[2] / ".build" / "nano-runtime")
        executable = runtime / "rc003-nano.exe"
        if not executable.is_file():
            raise FileNotFoundError("Nano native runtime missing")
        self.process = subprocess.Popen([str(executable),
            "--enc", str(root / "funasr-encoder-f16.gguf"),
            "-m", str(root / "qwen3-0.6b-q8_0.gguf"),
            "--vad", str(root / "fsmn-vad.gguf"), "--threads", str(threads)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW, bufsize=0)
        try:
            if _read_exact(self.process.stdout, 4) != b"RCN1":
                raise OSError("Nano protocol unavailable")
        except BaseException:
            self.close()
            raise

    def transcribe(self, pcm):
        if not isinstance(pcm, bytes) or len(pcm) % 2 or len(pcm) > _MAX_PCM_BYTES:
            raise ValueError("invalid Nano PCM")
        packet = memoryview(struct.pack("<I", len(pcm)) + pcm)
        while packet:
            count = self.process.stdin.write(packet)
            if not count:
                raise OSError("Nano input pipe closed")
            packet = packet[count:]
        self.process.stdin.flush()
        length, = struct.unpack("<I", _read_exact(self.process.stdout, 4))
        if length > _MAX_TEXT_BYTES:
            raise ValueError("invalid Nano response length")
        return _read_exact(self.process.stdout, length).decode("utf-8").strip()

    def close(self):
        process = self.process
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        if process.stdout:
            process.stdout.close()
