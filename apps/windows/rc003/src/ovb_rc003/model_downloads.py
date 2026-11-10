"""Nano model cache and observable, resumable downloads; no Python ML stack."""
from __future__ import annotations
import json
import multiprocessing as mp
import os
from pathlib import Path
import threading
import time

NANO = "fun_asr_nano"
NANO_REPO = "FunAudioLLM/Fun-ASR-Nano-GGUF"
NANO_REVISION = "46e849502a867080d66d351b8dfb1018b607e509"
NANO_VAD_REPO = "FunAudioLLM/fsmn-vad-GGUF"
NANO_VAD_REVISION = "6840bae4c5c92ee8c04faaf4db23dd0105098d7f"
NANO_FILES = {
    "funasr-encoder-f16.gguf": (469331008, "f92f91d01a24fbed6c863495b2ee8c6a6788144a02858b75743f0946668de8a2"),
    "qwen3-0.6b-q8_0.gguf": (804753280, "819f385dc0e035dccc3d9e7edaf6b7b044b8ba7ace63cbcbf84c7e397eecbf27"),
    "fsmn-vad.gguf": (1720512, "1270f2559c495f4e7b6e739541151027d360761a3fda43fc147034f5719f5479"),
}

def validate(engine, name="nano"):
    if engine != NANO:
        raise ValueError("unknown model engine")
    return "nano"

def cache_root(models_root, engine=NANO):
    validate(engine)
    return Path(models_root) / "fun-asr-nano"

def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}



def _complete(path, engine):
    validate(engine)
    try:
        for name, (size, _digest) in NANO_FILES.items():
            target = path / name
            if target.stat().st_size != size:
                return False
            with target.open("rb") as stream:
                if stream.read(4) != b"GGUF":
                    return False
        return True
    except OSError:
        return False

def cached_model(root, engine=NANO, name="nano"):
    key = validate(engine, name)
    root = Path(root).resolve()
    marker = _read(root / f"{key}-ready.json")
    candidates = [root / "gguf"]
    if isinstance(marker.get("path"), str):
        candidates.insert(0, root / marker["path"])
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
            candidate.relative_to(root)
            if _complete(candidate, engine):
                return candidate
        except (OSError, ValueError):
            pass
    return None

def _alive(pid):
    if type(pid) is not int or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.restype = wintypes.HANDLE
        api.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        api.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        api.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = api.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            return api.WaitForSingleObject(handle, 0) == 258
        finally:
            api.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def model_status(root, engine, name="small"):
    key = validate(engine, name)
    root = Path(root)
    ready = cached_model(root, engine, name)
    state = _read(root / f"{key}-download.json")
    if ready is not None:
        return {"state": "ready", "percent": 100, "message": "已下载，可离线使用", "file": ""}
    if state.get("state") in ("connecting", "downloading") and not _alive(state.get("pid")):
        state.update(state="paused", message="下载已中断，点击继续下载")
    if state.get("state") not in ("connecting", "downloading", "failed", "paused"):
        state = {"state": "missing", "percent": 0, "message": "尚未下载", "file": ""}
    percent = state.get("percent", 0)
    if type(percent) not in (float, int):
        percent = 0
    state["percent"] = max(0, min(100, percent))
    return state


class _Reporter:
    def __init__(self, root, key):
        self.path = Path(root) / f"{key}-download.json"
        self.lock = threading.Lock()
        self.last = 0.0

    def emit(self, state, message, *, filename="", done=0, total=0, force=False):
        with self.lock:
            now = time.monotonic()
            if not force and now - self.last < .15:
                return
            self.last = now
            _atomic_json(self.path, {"state": state, "message": message,
                "file": Path(filename).name, "done": int(done), "total": int(total or 0),
                "percent": min(99.9, done * 100 / total) if total else 0,
                "pid": os.getpid(), "updated_at": time.time()})



def _verified(path, size, digest):
    import hashlib
    try:
        if path.stat().st_size != size:
            return False
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest() == digest
    except OSError:
        return False

def _download(root, engine, name, reporter):
    validate(engine, name)
    import requests
    destination = Path(root) / "gguf"
    destination.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        for filename, (size, digest) in NANO_FILES.items():
            target = destination / filename
            reporter.emit("connecting", "正在校验模型文件", filename=filename, force=True)
            if _verified(target, size, digest):
                continue
            partial = target.with_name(filename + ".part")
            if _verified(partial, size, digest):
                os.replace(partial, target)
                continue
            offset = partial.stat().st_size if partial.exists() else 0
            if offset >= size:
                partial.unlink(missing_ok=True)
                offset = 0
            headers = {"Accept-Encoding": "identity"}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            vad = filename == "fsmn-vad.gguf"
            repo, revision = (NANO_VAD_REPO, NANO_VAD_REVISION) if vad else (NANO_REPO, NANO_REVISION)
            url = f"https://huggingface.co/{repo}/resolve/{revision}/{filename}"
            reporter.emit("connecting", "正在连接模型下载站点", filename=filename, force=True)
            with session.get(url, headers=headers, stream=True, timeout=(15, 60)) as response:
                response.raise_for_status()
                if offset and response.status_code == 206:
                    if not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                        raise ValueError("invalid model download range")
                else:
                    offset = 0
                reporter.emit("downloading", "正在下载", filename=filename,
                              done=offset, total=size, force=True)
                with partial.open("ab" if offset else "wb") as stream:
                    done = offset
                    for block in response.iter_content(chunk_size=1024 * 1024):
                        if not block:
                            continue
                        done += len(block)
                        if done > size:
                            raise ValueError("oversized model download")
                        stream.write(block)
                        reporter.emit("downloading", "正在下载", filename=filename, done=done, total=size)
            reporter.emit("connecting", "正在校验模型文件", filename=filename, force=True)
            if not _verified(partial, size, digest):
                partial.unlink(missing_ok=True)
                raise ValueError("model checksum mismatch")
            os.replace(partial, target)
    return destination

def ensure_model(root, engine, name="small"):
    """Called in an isolated download or inference worker, never the UI."""
    key = validate(engine, name)
    started_at = time.time()
    root = Path(root).resolve()
    ready = cached_model(root, engine, name)
    if ready is not None:
        return ready
    root.mkdir(parents=True, exist_ok=True)
    from filelock import FileLock
    with FileLock(str(root / f"{key}.download.lock")):
        if _read(root / f"{key}-pause.json").get("at", 0) > started_at:
            raise RuntimeError("download paused while waiting for cache")
        ready = cached_model(root, engine, name)
        if ready is not None:
            return ready
        reporter = _Reporter(root, key)
        reporter.emit("connecting", "正在连接模型下载站点", force=True)
        try:
            path = _download(root, engine, name, reporter).resolve()
            relative = path.relative_to(root)
            if not _complete(path, engine):
                raise ValueError("incomplete model snapshot")
            _atomic_json(root / f"{key}-ready.json", {"path": str(relative)})
            reporter.emit("ready", "下载完成，可离线使用", force=True)
            return path
        except Exception as exc:
            import errno
            message = ("磁盘空间不足，请清理后重试" if getattr(exc, "errno", None) == errno.ENOSPC
                       else "下载失败，请检查网络和磁盘空间后重试")
            reporter.emit("failed", message, force=True)
            raise


def download_worker(root, engine, name):
    try:
        ensure_model(root, engine, name)
    except Exception:
        # Startup/dependency failures before the SDK starts also need a visible
        # result, rather than silently returning to an empty download button.
        key = validate(engine, name)
        state = model_status(root, engine, name)
        if state["state"] not in ("failed", "paused", "ready"):
            _Reporter(root, key).emit("failed", "下载组件启动失败，请重新打开应用后重试", force=True)


class ModelDownloadManager:
    """One optional, memory-light downloader; first-use workers share its cache."""
    def __init__(self, models_root):
        self.models_root = Path(models_root)
        self.process = None
        self.selection = None

    def start(self, engine, name="small"):
        name = validate(engine, name)
        self.reap()
        if self.process is not None:
            return False
        root = cache_root(self.models_root, engine)
        if model_status(root, engine, name)["state"] in ("ready", "connecting", "downloading"):
            return False
        self.selection = (engine, name)
        self.process = mp.get_context("spawn").Process(target=download_worker,
            args=(str(root), engine, name), daemon=True)
        try:
            self.process.start()
        except Exception:
            self.process.close()
            self.process = self.selection = None
            _Reporter(root, name).emit("failed", "无法启动下载，请重新打开应用后重试", force=True)
            return False
        return True

    def reap(self):
        if self.process is not None and not self.process.is_alive():
            self.process.join()
            if self.process.exitcode and self.selection:
                engine, name = self.selection
                root = cache_root(self.models_root, engine)
                if model_status(root, engine, name)["state"] not in ("ready", "failed"):
                    _Reporter(root, name).emit("failed", "下载进程意外结束，请重试", force=True)
            self.process.close()
            self.process = self.selection = None

    def cancel(self):
        if self.process is None:
            return
        selection = self.selection
        process = self.process
        if selection:
            engine, name = selection
            root = cache_root(self.models_root, engine)
            _atomic_json(root / f"{name}-pause.json", {"at": time.time()})
        if process.is_alive():
            process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        if process.is_alive():
            raise RuntimeError("download process did not exit")
        process.close()
        self.process = self.selection = None
        if selection:
            engine, name = selection
            root = cache_root(self.models_root, engine)
            if cached_model(root, engine, name) is None:
                old = model_status(root, engine, name)
                old.update(state="paused", message="下载已暂停，点击继续下载")
                _atomic_json(root / f"{name}-download.json", old)

    close = cancel
