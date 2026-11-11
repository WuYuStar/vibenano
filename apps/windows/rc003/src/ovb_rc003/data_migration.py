"""Non-destructive first-start import of settings and completed Nano models."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading

MARKER = ".data-migration-v1.json"
_LOCK = threading.Lock()
SETTINGS = ("config.json", "key_bindings.json", "mapping_presets.json")


def completed(root):
    try:
        data = json.loads((Path(root) / MARKER).read_text(encoding="utf-8"))
        return data.get("schema") == 1 and data.get("completed") is True
    except (OSError, ValueError, AttributeError):
        return False


def _link_like(path):
    return path.is_symlink() or (getattr(path, "is_junction", lambda: False)())


def _copy_missing(source, target, *, immutable=False):
    if target.exists() or target.is_symlink():
        return
    if _link_like(source):
        raise OSError("legacy data is redirected; migration stopped")
    target.parent.mkdir(parents=True, exist_ok=True)
    if immutable:
        try:
            # Same-volume NTFS links reuse the completed model bytes, no duplicate GBs.
            os.link(source, target)
            return
        except FileExistsError:
            return
        except OSError:
            pass
    fd, name = tempfile.mkstemp(prefix=".vibenano-import-", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as stream:
            shutil.copyfileobj(stream, out, 1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        try:
            if os.name == "nt":
                # Windows rename does not replace an existing destination.
                os.rename(temporary, target)
            else:
                # Atomic no-replace publication on POSIX.
                os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def _walk_error(error):
    raise error


def migrate(legacy, target):
    legacy, target = Path(legacy), Path(target)
    with _LOCK:
        if completed(target):
            return
        if legacy == target or _link_like(legacy) or _link_like(target):
            raise OSError("unsafe data migration root")
        for name in SETTINGS:
            source = legacy / name
            if source.is_file():
                _copy_missing(source, target / name)
        # No runtime status, IPC requests, logs, permissions or old-model caches.
        source_models = legacy / "models/fun-asr-nano"
        if source_models.exists():
            if _link_like(legacy / "models") or _link_like(source_models):
                raise OSError("legacy model cache is redirected")
            for directory, dirs, files in os.walk(source_models, followlinks=False, onerror=_walk_error):
                parent = Path(directory)
                if any(_link_like(parent / name) for name in dirs):
                    raise OSError("legacy model cache contains redirected directories")
                for name in files:
                    if not (name.endswith(".gguf") or name == "nano-ready.json"):
                        continue
                    source = parent / name
                    _copy_missing(source, target / "models/fun-asr-nano" / source.relative_to(source_models),
                                  immutable=name.endswith(".gguf"))
        target.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".migration-", dir=target)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"schema": 1, "completed": True}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target / MARKER)
        finally:
            temporary.unlink(missing_ok=True)
