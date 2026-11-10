"""Private packaged-runtime checks. Never constructs a bridge or pastes text."""
from __future__ import annotations
import json
import os
from pathlib import Path
import time

FLAG = "--local-model-check"


def run(request_path, result_path):
    result = {"ok": False}
    try:
        request = json.loads(Path(request_path).read_text(encoding="utf-8"))
        kind = request.get("kind", "recognize")
        if kind == "qml":
            result.update(_qml(request))
        else:
            from . import model_downloads as downloads
            engine = request["engine"]
            name = request.get("model", "small")
            downloads.validate(engine, name)
            root = Path(request["model_root"])
            if kind == "download":
                # Models are stored beneath an explicit disposable test root.
                manager = downloads.ModelDownloadManager(root)
                events = []
                try:
                    manager.start(engine, name)
                    deadline = time.monotonic() + 900
                    while manager.process is not None and time.monotonic() < deadline:
                        state = downloads.model_status(downloads.cache_root(root, engine), engine, name)
                        entry = (state["state"], state.get("done", 0), state.get("total", 0))
                        if not events or events[-1] != entry:
                            events.append(entry)
                        manager.reap()
                        time.sleep(.15)
                    state = downloads.model_status(downloads.cache_root(root, engine), engine, name)
                    result.update(ok=state["state"] == "ready", status=state, progress_events=events)
                finally:
                    manager.close()
            elif kind == "recognize":
                result.update(_recognize(request, root, engine, name))
            else:
                raise ValueError("unknown check")
    except Exception as exc:
        # Build diagnostics only: no raw audio or exception message is exposed.
        import traceback
        result.update(error_type=type(exc).__name__, trace=traceback.format_exc())
    Path(result_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


def _recognize(request, root, engine, name):
    import threading
    import wave
    from .local_speech_provider import LocalSpeechRuntime
    with wave.open(request["audio"], "rb") as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
            raise ValueError("expected mono 16 kHz PCM")
        pcm = audio.readframes(audio.getnframes())
    done = threading.Event()
    states, texts = [], []
    def on_status(owner, state):
        states.append(state)
        if state in ("success", "failed", "unavailable", "audio_empty"):
            done.set()
    def on_text(owner, text, target):
        texts.append(text)
        return True
    runtime = LocalSpeechRuntime(root, on_status=on_status, on_text=on_text, logger=None, engine=engine)
    child = None
    try:
        owner = object()
        settings = {"faster_whisper_model": name}
        if not runtime.submit(owner, pcm, settings):
            raise RuntimeError("submission rejected")
        if not done.wait(180):
            raise TimeoutError("model check timeout")
        if runtime._process_model is not None:
            child = runtime._process_model.process
        runtime.close(timeout=5)
        exited = child is None or not child.is_alive()
        return {"ok": bool(texts) and exited, "states": states, "texts": texts, "child_exited": exited}
    finally:
        runtime.close(timeout=5)


def _qml(request):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from . import qt_settings_app as gui
    classes = gui._load_qt_classes()
    classes["QQuickStyle"].setStyle("FluentWinUI3")
    app = classes["QGuiApplication"].instance() or classes["QGuiApplication"]([])
    from PySide6.QtGui import QFontDatabase
    QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"))
    gui.startup_windows.rebind_owned_frozen_startup = lambda: None
    gui.single_instance.bridge_instance_running = lambda: False
    gui.windows_diagnostics.run_diagnostics = lambda **kwargs: None
    ButtonModel = classes["ButtonMappingModel"]
    Controller = classes["SettingsController"]
    Diagnostics = classes["DiagnosticsController"]
    model = ButtonModel()
    controller = Controller(model, start_hidden=True, start_bridge=False)
    controller._launch_bridge_on_app_start = False
    controller._replace_voice_program_settings({"provider": request.get("provider", "fun_asr_nano")})
    diagnostics = Diagnostics(controller, gui.config.config_root(), auto_refresh=False)
    register = classes["qmlRegisterSingletonInstance"]
    for cls, name, instance in ((Controller, "SettingsController", controller),
        (ButtonModel, "ButtonMappingModel", model), (Diagnostics, "DiagnosticsController", diagnostics)):
        register(cls, "OvbRc003Settings", 1, 0, name, instance)
    engine = classes["QQmlApplicationEngine"]()
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
    qml_dir = gui._qml_directory()
    engine.addImportPath(str(qml_dir))
    engine.load(classes["QUrl"].fromLocalFile(str(qml_dir / "main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("main QML did not load")
    window = engine.rootObjects()[0]
    window.setProperty("width", 900)
    window.setProperty("height", 780)
    window.show()
    from PySide6.QtCore import QObject
    tab = window.findChild(QObject, "tabBar")
    tab.setProperty("currentIndex", 2)
    for _ in range(12):
        app.processEvents()
        window.grabWindow()
    snapshot = request.get("screenshot")
    if snapshot:
        window.grabWindow().save(snapshot)
    def find(root, name):
        children = list(root.children())
        child_items = getattr(root, "childItems", None)
        if callable(child_items):
            children.extend(item for item in child_items() if item not in children)
        for child in children:
            if child.objectName() == name:
                return child
            found = find(child, name)
            if found is not None:
                return found
        return None

    buttons = find(window, "downloadModel_fun_asr_nano") is not None
    window.hide()
    controller._model_download_manager.close()
    gui._shutdown_diagnostics_workers()
    return {"ok": buttons and not warnings, "download_buttons": buttons, "warnings": warnings}
